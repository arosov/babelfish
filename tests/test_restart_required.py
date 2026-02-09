import asyncio
import pytest
import json
import ssl
from babelfish_stt.server import BabelfishServer
from babelfish_stt.config_manager import ConfigManager
from pywebtransport import WebTransportClient, ClientConfig

@pytest.mark.asyncio
async def test_server_restart_required_signal(tmp_path):
    config_file = tmp_path / "config.json"
    cm = ConfigManager(config_path=str(config_file))
    cm.config.server.port = 4447
    cm.config.server.host = "127.0.0.1"
    
    server = BabelfishServer(cm)
    cm.register(server)
    server_task = asyncio.create_task(server.start())
    
    session = None
    client_ctx = WebTransportClient(config=ClientConfig(verify_mode=ssl.CERT_NONE))
    try:
        async with client_ctx as client:
            # Retry connection logic
            for _ in range(20):
                try:
                    session = await client.connect(url="https://127.0.0.1:4447/config")
                    break
                except Exception:
                    await asyncio.sleep(0.1)
            
            if not session:
                pytest.fail("Failed to connect to server")

            async with await session.create_bidirectional_stream() as stream:
                reader = asyncio.StreamReader()
                async def pipe_to_reader():
                    while not stream.is_closed:
                        try:
                            chunk = await stream.read(max_bytes=4096)
                            if not chunk:
                                break
                            reader.feed_data(chunk)
                        except Exception:
                            break
                    reader.feed_eof()
                
                read_task = asyncio.create_task(pipe_to_reader())

                # 1. Receive initial config, restart_required should be False
                line = await asyncio.wait_for(reader.readline(), timeout=2.0)
                msg = json.loads(line.decode('utf-8'))
                assert msg["restart_required"] is False

                # 2. Update hardware (critical change)
                update_msg = {
                    "type": "update_config",
                    "data": {
                        "hardware": {
                            "device": "cuda" if cm.config.hardware.device == "cpu" else "cpu"
                        }
                    }
                }
                await stream.write_all(data=json.dumps(update_msg).encode('utf-8') + b"\n")

                # 3. Receive update, restart_required should now be True
                line2 = await asyncio.wait_for(reader.readline(), timeout=2.0)
                msg2 = json.loads(line2.decode('utf-8'))
                assert msg2["restart_required"] is True
                assert server.restart_required is True

                # 4. Revert to original hardware
                revert_msg = {
                    "type": "update_config",
                    "data": {
                        "hardware": {
                            "device": cm.config.hardware.device # It was updated in cm already
                        }
                    }
                }
                # Actually, cm.config.hardware.device is already the NEW value.
                # We want to revert to server.initial_config.hardware.device
                revert_msg["data"]["hardware"]["device"] = server.initial_config.hardware.device
                
                await stream.write_all(data=json.dumps(revert_msg).encode('utf-8') + b"\n")
                
                # 5. Receive update, restart_required should be False again
                line3 = await asyncio.wait_for(reader.readline(), timeout=2.0)
                msg3 = json.loads(line3.decode('utf-8'))
                assert msg3["restart_required"] is False
                assert server.restart_required is False

                read_task.cancel()
    finally:
        if session:
            await session.close()
        server_task.cancel()
        try:
            await server_task
        except (asyncio.CancelledError, Exception):
            pass