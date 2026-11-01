"""
Windows System Tray Icon for DeepCool LM360 Controller.
Provides instant taskbar access to dashboard, modes, rotation, and brightness.
"""

import logging
import os
import webbrowser
from PIL import Image
import pystray
from pystray import MenuItem as item

logger = logging.getLogger("deepcool_lm.tray")


class TrayIconManager:
    def __init__(self, service, port: int = 5220, icon_path: str = "icon.ico"):
        self.service = service
        self.port = port
        self.icon_path = os.path.abspath(icon_path)
        self._tray = None

    def _get_icon_image(self):
        if os.path.exists(self.icon_path):
            try:
                return Image.open(self.icon_path)
            except Exception:
                pass
        img = Image.new("RGB", (64, 64), color=(14, 16, 22))
        return img

    def _open_dashboard(self):
        webbrowser.open(f"http://localhost:{self.port}")

    def _set_mode(self, mode: str):
        self.service.set_mode(mode)

    def _is_mode(self, mode: str):
        return lambda item: self.service.config.get("mode") == mode

    def _set_orient(self, deg: int):
        self.service.set_orientation(deg)

    def _is_orient(self, deg: int):
        return lambda item: self.service.config.get("orientation") == deg

    def _set_brightness(self, percent: int):
        self.service.set_brightness(percent)

    def _is_brightness(self, percent: int):
        return lambda item: abs(self.service.usb.brightness_pct - percent) <= 10

    def _on_exit(self, icon, item):
        logger.info("Tray Exit requested.")
        icon.stop()
        self.service.stop()

    def run(self):
        """Runs the tray icon event loop (blocks calling thread)."""
        image = self._get_icon_image()

        brightness_menu = pystray.Menu(
            item("100%", lambda: self._set_brightness(100), checked=self._is_brightness(100)),
            item("75%", lambda: self._set_brightness(75), checked=self._is_brightness(75)),
            item("50%", lambda: self._set_brightness(50), checked=self._is_brightness(50)),
            item("25%", lambda: self._set_brightness(25), checked=self._is_brightness(25)),
            item("10%", lambda: self._set_brightness(10), checked=self._is_brightness(10)),
            pystray.Menu.SEPARATOR,
            item("Increase (+10%)", lambda: self.service.brightness_up()),
            item("Decrease (-10%)", lambda: self.service.brightness_down()),
        )

        menu = pystray.Menu(
            item("AIOed Controller", self._open_dashboard, default=True),
            pystray.Menu.SEPARATOR,
            item("Hardware Monitor", lambda: self._set_mode("monitor"), checked=self._is_mode("monitor")),
            item("GIF / Video Loop", lambda: self._set_mode("media"), checked=self._is_mode("media")),
            item("Text Banner", lambda: self._set_mode("text"), checked=self._is_mode("text")),
            item("Display Standby", lambda: self._set_mode("off"), checked=self._is_mode("off")),
            pystray.Menu.SEPARATOR,
            item("Orientation: 180° Inverted", lambda: self._set_orient(180), checked=self._is_orient(180)),
            item("Orientation: 0° Normal", lambda: self._set_orient(0), checked=self._is_orient(0)),
            pystray.Menu.SEPARATOR,
            item("Brightness", brightness_menu),
            pystray.Menu.SEPARATOR,
            item("Open Dashboard (Web)", self._open_dashboard),
            item("Exit", self._on_exit)
        )

        self._tray = pystray.Icon("AIOed_LM360", image, "AIOed - DeepCool LM360", menu)
        self._tray.run()

    def stop(self):
        if self._tray:
            self._tray.stop()
