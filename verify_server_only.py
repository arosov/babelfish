import asyncio
import logging
import sys
from babelfish_stt.config_manager import ConfigManager
from babelfish_stt.server import BabelfishServer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

async def main():
    config_manager = ConfigManager()
    server = BabelfishServer(config_manager)
    print(f"Starting server on port {config_manager.config.server.port}")
    await server.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
