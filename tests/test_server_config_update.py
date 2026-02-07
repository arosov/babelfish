import asyncio
import pytest
import json
import os
import ssl
from babelfish_stt.server import BabelfishServer
from babelfish_stt.config_manager import ConfigManager
from pywebtransport import WebTransportClient, ClientConfig
from pywebtransport.types import EventType

@pytest.mark.asyncio
async def test_server_update_config_via_webtransport(tmp_path):
    config_file = tmp_path / "config.json"
    cm = ConfigManager(config_path=str(config_file))
    cm.config.server.port = 4446
    cm.config.server.host = "127.0.0.1"
    
    server = BabelfishServer(cm)
    server_task = asyncio.create_task(server.start())
    
    session = None
    client_ctx = WebTransportClient(config=ClientConfig(verify_mode=ssl.CERT_NONE))
    try:
        async with client_ctx as client:
            # Retry connection logic
            for _ in range(20):
                try:
                    session = await client.connect(url="https://127.0.0.1:4446/config")
                    break
                except Exception:
                    await asyncio.sleep(0.1)
            
            if not session:
                pytest.fail("Failed to connect to server")

            # Client initiates control stream
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

                # 1. Receive initial config
                line = await asyncio.wait_for(reader.readline(), timeout=2.0)
                msg = json.loads(line.decode('utf-8'))
                assert msg["type"] == "config"
                assert msg["data"]["ui"]["verbose"] is False

                # 2. Send update_config message
                update_msg = {
                    "type": "update_config",
                    "data": {
                        "ui": {
                            "verbose": True
                        }
                    }
                }
                # We need to send it with a newline delimiter too
                await stream.write_all(data=json.dumps(update_msg).encode('utf-8') + b"\n")

                # 3. Receive broadcast back with updated config
                # We expect it to fail here because the server doesn't handle the update yet
                line2 = await asyncio.wait_for(reader.readline(), timeout=5.0)
                msg2 = json.loads(line2.decode('utf-8'))
                
                assert msg2["type"] == "config"
                assert msg2["data"]["ui"]["verbose"] is True
                
                # Also verify in config manager
                assert cm.config.ui.verbose is True
                
                # 4. Send invalid update (wrong type)
                invalid_msg = {
                    "type": "update_config",
                    "data": {
                        "ui": {
                            "verbose": "not_a_bool" 
                        }
                    }
                }
                await stream.write_all(data=json.dumps(invalid_msg).encode('utf-8') + b"\n")
                
                # 5. Receive error message
                line3 = await asyncio.wait_for(reader.readline(), timeout=2.0)
                msg3 = json.loads(line3.decode('utf-8'))
                
                assert msg3["type"] == "error"
                assert "validation error" in msg3["message"].lower() or "input should be a valid boolean" in msg3["message"].lower()

                read_task.cancel()
                
    finally:
        if session:
            await session.close()
        server_task.cancel()
        try:
            await server_task
        except (asyncio.CancelledError, Exception):
            pass
        
        for f in ["localhost.crt", "localhost.key"]:
            if os.path.exists(f):
                os.remove(f)