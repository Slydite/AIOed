"""
DeepCool LM360 Controller - Main Entry Point.
Runs the ultra-low resource background service, web dashboard, and system tray.
"""

import argparse
import logging
import os
import sys
import threading
import time
import webbrowser
import uvicorn

from deepcool_lm.config import ConfigManager
from deepcool_lm.media_manager import MediaManager
from deepcool_lm.service import DisplayService
from deepcool_lm.server import create_app
from deepcool_lm.tray import TrayIconManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("deepcool_lm")


def run_server(app, host: str, port: int):
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(config)
    server.run()


def main():
    parser = argparse.ArgumentParser(description="DeepCool LM360 White LCD Display Controller")
    parser.add_argument("--port", type=int, default=5220, help="Web dashboard port (default: 5220)")
    parser.add_argument("--no-tray", action="store_true", help="Run without system tray icon")
    parser.add_argument("--open-browser", action="store_true", help="Open web dashboard in browser on start")
    parser.add_argument("--orientation", type=int, choices=[0, 180], help="Display orientation (default: 180)")
    args = parser.parse_args()

    logger.info("Initializing DeepCool LM360 Display Controller...")

    # Load configuration
    cfg = ConfigManager("config.json")
    if args.orientation is not None:
        cfg.set("orientation", args.orientation)
    port = args.port or cfg.get("web_port", 5220)

    # Initialize media manager and auto-import existing DeepCool media
    media_mgr = MediaManager("media_store")
    try:
        media_mgr.auto_import_deepcool_roaming()
    except Exception as e:
        logger.warning(f"Error during DeepCool media auto-import: {e}")

    # Initialize display service
    service = DisplayService(cfg, media_mgr)
    service.start()

    # Create FastAPI app
    app = create_app(service, web_dir="web")

    # Start web server in background thread
    server_thread = threading.Thread(
        target=run_server,
        args=(app, "0.0.0.0", port),
        daemon=True,
        name="UvicornServerThread"
    )
    server_thread.start()
    logger.info(f"Web Dashboard ready at: http://localhost:{port}")

    if args.open_browser:
        webbrowser.open(f"http://localhost:{port}")

    # Run system tray or wait
    if not args.no_tray:
        tray = TrayIconManager(service, port=port)
        try:
            tray.run()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        finally:
            service.stop()
    else:
        logger.info("Running in headless daemon mode. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            logger.info("Shutting down headless daemon...")
        finally:
            service.stop()


if __name__ == "__main__":
    main()

