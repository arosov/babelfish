import asyncio
import logging
from babelfish_stt.server import BabelfishServer
from babelfish_stt.config_manager import ConfigManager

# Configure logging to match main app
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("server.log", mode='w')
    ]
)

async def main():
    cm = ConfigManager()
    # Ensure we use the production defaults
    cm.config.server.host = "127.0.0.1"
    cm.config.server.port = 8123
    
    server = BabelfishServer(cm)
    print(f"Starting STANDALONE server on {cm.config.server.host}:{cm.config.server.port}...")
    print("This runs in the MAIN THREAD. Please connect your client now.")
    
    await server.start()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\\nStopped.")