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
async def test_server_send_config_on_connect(tmp_path):
    config_file = tmp_path / "config.json"
    cm = ConfigManager(config_path=str(config_file))
    cm.config.server.port = 4444
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
                    session = await client.connect(url="https://127.0.0.1:4444/config")
                    break
                except Exception:
                    await asyncio.sleep(0.1)
            
            if not session:
                pytest.fail("Failed to connect to server")

            # Client initiates control stream
            async with await session.create_bidirectional_stream() as stream:
                # Read initial config (first line)
                # We need a robust reader that handles partial reads until newline
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
                
                asyncio.create_task(pipe_to_reader())
                
                line = await asyncio.wait_for(reader.readline(), timeout=2.0)
                msg = json.loads(line.decode('utf-8'))
                
                assert msg["type"] == "config"
                assert msg["data"]["hardware"]["device"] == "auto"
                
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

@pytest.mark.asyncio
async def test_server_broadcast_config(tmp_path):
    config_file = tmp_path / "config.json"
    cm = ConfigManager(config_path=str(config_file))
    cm.config.server.port = 4445
    server = BabelfishServer(cm)
    server_task = asyncio.create_task(server.start())
    
    session = None
    client_ctx = WebTransportClient(config=ClientConfig(verify_mode=ssl.CERT_NONE))
    try:
        async with client_ctx as client:
            for _ in range(20):
                try:
                    session = await client.connect(url="https://127.0.0.1:4445/config")
                    break
                except Exception:
                    await asyncio.sleep(0.1)
            
            if not session:
                pytest.fail("Failed to connect to server")

            # Client initiates persistent control stream
            async with await session.create_bidirectional_stream() as stream:
                reader = asyncio.StreamReader()
                async def pipe_to_reader():
                    while not stream.is_closed:
                        try:
                            # Read with a timeout to allow checking stream.is_closed periodically
                            # or rely on read returning empty bytes on close
                            chunk = await stream.read(max_bytes=4096)
                            if not chunk:
                                break
                            reader.feed_data(chunk)
                        except Exception:
                            break
                    reader.feed_eof()
                
                read_task = asyncio.create_task(pipe_to_reader())

                # 1. Receive initial config
                line1 = await asyncio.wait_for(reader.readline(), timeout=2.0)
                msg1 = json.loads(line1.decode('utf-8'))
                assert msg1["type"] == "config"

                # 2. Trigger broadcast
                cm.config.ui.verbose = True
                await server.broadcast_config()

                # 3. Receive update on SAME stream
                line2 = await asyncio.wait_for(reader.readline(), timeout=2.0)
                msg2 = json.loads(line2.decode('utf-8'))
                assert msg2["data"]["ui"]["verbose"] is True
                
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