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

# 1. Lock working directory to the project directory regardless of caller
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

# 2. Redirect sys.stdout and sys.stderr under pythonw.exe so unhandled prints/streams never crash
LOG_FILE = os.path.join(PROJECT_DIR, "aioed.log")
has_console = sys.stdout is not None and hasattr(sys.stdout, "write")

_log_file_handle = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
if sys.stdout is None:
    sys.stdout = _log_file_handle
if sys.stderr is None:
    sys.stderr = _log_file_handle

log_handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
if has_console:
    log_handlers.append(logging.StreamHandler())

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=log_handlers
)
logger = logging.getLogger("deepcool_lm")


def _handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logger.critical("Uncaught exception in main process:", exc_info=(exc_type, exc_value, exc_traceback))


def _handle_thread_exception(args):
    if issubclass(args.exc_type, KeyboardInterrupt):
        return
    thread_name = getattr(args.thread, "name", "unknown")
    logger.critical(f"Uncaught exception in background thread '{thread_name}':", exc_info=(args.exc_type, args.exc_value, args.exc_traceback))


sys.excepthook = _handle_exception
threading.excepthook = _handle_thread_exception

# 3. Enforce single-instance execution via Windows named Mutex
_single_instance_mutex = None
if sys.platform == "win32":
    try:
        import ctypes
        _single_instance_mutex = ctypes.windll.kernel32.CreateMutexW(
            None, False, "Local\\AIOed_LM360_SingleInstanceMutex"
        )
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            logger.info("AIOed LM360 service is already running. Exiting duplicate instance.")
            sys.exit(0)
    except Exception as e:
        logger.warning(f"Could not initialize single instance mutex: {e}")

from deepcool_lm.config import ConfigManager
from deepcool_lm.media_manager import MediaManager
from deepcool_lm.service import DisplayService
from deepcool_lm.server import create_app
from deepcool_lm.tray import TrayIconManager


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
    parser.add_argument("--host", default="127.0.0.1", help="Web dashboard bind address (default: 127.0.0.1, local only)")
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
        args=(app, args.host, port),
        daemon=True,
        name="UvicornServerThread"
    )
    server_thread.start()
    logger.info(f"Web Dashboard ready at: http://localhost:{port}")

    if args.open_browser:
        webbrowser.open(f"http://localhost:{port}")

    # Run system tray or wait
    if not args.no_tray:
        try:
            tray = TrayIconManager(service, port=port)
            tray.run()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received.")
        except Exception as e:
            logger.warning(f"System tray encountered an issue: {e}")

        # If tray event loop ended (e.g. Explorer restart, taskbar reload) but user did not exit, keep running!
        if service._running:
            logger.info("System tray loop concluded; continuing in background daemon mode...")
            try:
                while service._running:
                    time.sleep(1.0)
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received.")
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
    try:
        main()
    except Exception:
        logger.exception("Fatal unhandled exception in main:")
        sys.exit(1)

