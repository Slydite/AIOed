"""
Core Background Service for DeepCool LM360 LCD.
Orchestrates hardware USB transmission, telemetry rendering, media streaming,
and state management with ultra-low resource footprint and zero lag.
"""

import io
import logging
import threading
import time
import ctypes
from PIL import Image

try:
    _winmm = ctypes.WinDLL('winmm')
except Exception:
    _winmm = None

from deepcool_lm.usb_driver import LM360UsbDriver
from deepcool_lm.sensor_bridge import SensorBridge
from deepcool_lm.media_manager import MediaManager
from deepcool_lm.config import ConfigManager
from deepcool_lm.themes.theme_registry import get_theme, list_themes, get_available_metrics
from deepcool_lm.text_animator import TextAnimator, FONTS_REGISTRY, EFFECTS

logger = logging.getLogger("deepcool_lm.service")


class DisplayService:
    """Main daemon controlling the LM360 LCD display."""

    def __init__(self, config: ConfigManager, media_mgr: MediaManager):
        self.config = config
        self.media_mgr = media_mgr
        self.text_animator = TextAnimator(self.config)
        saved_brightness = self.config.get("brightness", 100)
        saved_orientation = self.config.get("orientation", 180)
        self.usb = LM360UsbDriver(initial_brightness=saved_brightness, orientation=saved_orientation)
        self.sensors = SensorBridge()

        self._running = False
        self._thread = None
        self._wake_event = threading.Event()

        self._lock = threading.Lock()
        self._latest_preview_img = None
        self._preview_jpeg_cache = None
        self._last_media_preview_time = 0.0

        # Statistics
        self.fps_counter = 0.0
        self._frames_this_sec = 0
        self._last_fps_calc = time.perf_counter()

    def start(self):
        """Start USB driver, sensor bridge, and display rendering loop."""
        if self._running:
            return
        logger.info("Starting DeepCool LM360 Display Service...")

        if _winmm:
            try:
                _winmm.timeBeginPeriod(1)
            except Exception:
                pass

        # Start sensor bridge
        self.sensors.start()

        # Connect USB device
        self.usb.connect()

        self._running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True, name="LM360DisplayThread")
        self._thread.start()
        logger.info("LM360 Display Service successfully started.")

    def stop(self):
        """Clean shutdown of service threads and hardware."""
        logger.info("Stopping DeepCool LM360 Display Service...")
        self._running = False
        self._wake_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)

        self.sensors.stop()
        self.usb.close()

        if _winmm:
            try:
                _winmm.timeEndPeriod(1)
            except Exception:
                pass

        logger.info("DeepCool LM360 Display Service stopped.")

    def _render_loop(self):
        """High-precision adaptive loop handling Monitor, Media Loop, and Power Off."""
        current_streamer = None
        current_streamer_id = None
        current_streamer_orient = None
        media_start_time = time.perf_counter()

        while self._running:
            mode = self.config.get("mode", "monitor")
            orientation = self.config.get("orientation", 180)

            # High precision FPS counter
            t_now = time.perf_counter()
            self._frames_this_sec += 1
            if t_now - self._last_fps_calc >= 1.0:
                self.fps_counter = round(self._frames_this_sec / (t_now - self._last_fps_calc), 1)
                self._frames_this_sec = 0
                self._last_fps_calc = t_now

            try:
                if mode == "off":
                    self.usb.screen_off()
                    with self._lock:
                        self._latest_preview_img = Image.new("RGB", (320, 240), color=(0, 0, 0))
                        self._preview_jpeg_cache = None
                    self._wake_event.wait(timeout=5.0)
                    self._wake_event.clear()
                    continue

                elif mode == "media":
                    active_media_id = self.config.get("active_media_id")
                    if not active_media_id:
                        all_m = self.media_mgr.list_media()
                        if all_m:
                            active_media_id = all_m[0]["id"]
                            self.config.set("active_media_id", active_media_id)

                    if not active_media_id:
                        time.sleep(0.5)
                        continue

                    # Streamer switch check
                    if current_streamer is None or current_streamer_id != active_media_id or current_streamer_orient != orientation:
                        if current_streamer:
                            current_streamer.close()
                        current_streamer = self.media_mgr.get_streamer(active_media_id, orientation)
                        current_streamer_id = active_media_id
                        current_streamer_orient = orientation
                        media_start_time = time.perf_counter()

                    if current_streamer is None:
                        time.sleep(0.5)
                        continue

                    # Clock-synchronized frame selection:
                    # Maps real elapsed seconds directly to target frame index.
                    # Guarantees 100% native playback speed with ZERO slow-motion drift!
                    fps = current_streamer.fps
                    now = time.perf_counter()
                    elapsed = now - media_start_time
                    frame_idx = int(elapsed * fps) % current_streamer.frame_count

                    raw_frame = current_streamer.get_frame(frame_idx)
                    self.usb.send_frame(raw_frame)

                    # Update preview (every 0.04s = ~25 FPS) for ultra-smooth UI video mirror
                    if now - self._last_media_preview_time >= 0.04:
                        self._last_media_preview_time = now
                        self._update_preview_from_rgb565(raw_frame, orientation)

                    # Calculate high-precision sleep until next scheduled frame deadline
                    next_deadline = media_start_time + ((int(elapsed * fps) + 1) / fps)
                    time_to_wait = next_deadline - time.perf_counter()

                    if time_to_wait > 0.001:
                        self._wake_event.wait(timeout=time_to_wait)
                        if self._wake_event.is_set():
                            self._wake_event.clear()

                elif mode == "text":
                    if current_streamer:
                        current_streamer.close()
                        current_streamer = None
                        current_streamer_id = None

                    stats = self.sensors.get_stats()
                    t_frame_start = time.perf_counter()
                    raw_frame, preview_img = self.text_animator.render(t_frame_start, orientation=orientation, stats=stats)
                    self.usb.send_frame(raw_frame)

                    with self._lock:
                        self._latest_preview_img = preview_img
                        self._preview_jpeg_cache = None

                    # Run text animation at smooth 25 FPS
                    time_to_wait = 0.04 - (time.perf_counter() - t_frame_start)
                    if time_to_wait > 0.001:
                        self._wake_event.wait(timeout=time_to_wait)
                        if self._wake_event.is_set():
                            self._wake_event.clear()

                elif mode == "monitor":
                    if current_streamer:
                        current_streamer.close()
                        current_streamer = None
                        current_streamer_id = None

                    theme_id = self.config.get("active_theme", "cyber_dual")
                    theme_inst = get_theme(theme_id)
                    theme_cfg = self.config.get_theme_config(theme_id)
                    stats = self.sensors.get_stats()

                    raw_frame, preview_img = theme_inst.render(stats, orientation=orientation, config=theme_cfg)
                    self.usb.send_frame(raw_frame)

                    with self._lock:
                        self._latest_preview_img = preview_img
                        self._preview_jpeg_cache = None

                    self._wake_event.wait(timeout=0.9)
                    if self._wake_event.is_set():
                        self._wake_event.clear()

            except Exception as e:
                logger.warning(f"Error in display loop: {e}")
                time.sleep(0.5)

        if current_streamer:
            current_streamer.close()

    def _update_preview_from_rgb565(self, packet_bytes: bytes, orientation: int):
        """Converts raw frame back to preview image for web dashboard."""
        try:
            # Skip 13-byte header if present
            if len(packet_bytes) == 153613:
                pixel_bytes = packet_bytes[13:]
            else:
                pixel_bytes = packet_bytes

            import numpy as np
            words = np.frombuffer(pixel_bytes, dtype=np.uint16).reshape((240, 320))
            r = ((words >> 11) & 0x1F) << 3
            g = ((words >> 5) & 0x3F) << 2
            b = (words & 0x1F) << 3
            rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
            img = Image.fromarray(rgb, "RGB")
            if orientation == 180:
                img = img.rotate(180)

            with self._lock:
                self._latest_preview_img = img
                self._preview_jpeg_cache = None
        except Exception:
            pass

    def get_preview_jpeg(self) -> bytes:
        """Returns compressed JPEG bytes of the current screen for live web preview."""
        with self._lock:
            if self._preview_jpeg_cache:
                return self._preview_jpeg_cache

            if self._latest_preview_img is None:
                img = Image.new("RGB", (320, 240), color=(14, 16, 22))
            else:
                img = self._latest_preview_img

            bio = io.BytesIO()
            img.save(bio, "JPEG", quality=80)
            self._preview_jpeg_cache = bio.getvalue()
            return self._preview_jpeg_cache

    def wake(self):
        """Signal immediate redraw after settings change."""
        self._wake_event.set()

    # Public API handlers
    def set_mode(self, mode: str):
        if mode in ("monitor", "media", "text", "off"):
            self.config.set("mode", mode)
            self.wake()

    def set_orientation(self, deg: int):
        if deg in (0, 180):
            self.config.set("orientation", deg)
            self.usb.orientation_deg = deg
            if self.usb.is_connected:
                self.usb.set_hardware_settings(self.usb.brightness_pct, deg)
            self.wake()

    def set_text_config(self, cfg: dict):
        self.text_animator.set_config(cfg)
        self.wake()

    def get_text_config(self) -> dict:
        return self.text_animator.get_config()

    def bake_text(self, duration_sec: float = 4.0, fps: int = 24, name: str = None) -> str:
        stats = self.sensors.get_stats()
        item_id = self.text_animator.bake_to_media(self.media_mgr, duration_sec=duration_sec, fps=fps, name=name, stats=stats)
        return item_id

    def set_theme(self, theme_id: str):
        self.config.set("active_theme", theme_id)
        self.wake()

    def set_theme_slot(self, theme_id: str, slot_id: str, metric: str):
        self.config.set_theme_slot(theme_id, slot_id, metric)
        self.wake()

    def set_media(self, media_id: str):
        self.config.set("active_media_id", media_id)
        self.config.set("mode", "media")
        self.wake()

    def set_temp_unit(self, unit: str):
        if unit.upper() in ("C", "F"):
            self.config.set("temp_unit", unit.upper())
            self.wake()

    def set_brightness(self, percent: int):
        val = int(percent)
        if 1 <= val <= 5:
            val = val * 20
        target = max(0, min(100, val))
        self.usb.set_brightness(target)
        self.config.set("brightness", target)

    def brightness_up(self, step: int = 10):
        new_val = min(100, self.usb.brightness_pct + step)
        self.set_brightness(new_val)

    def brightness_down(self, step: int = 10):
        new_val = max(10, self.usb.brightness_pct - step)
        self.set_brightness(new_val)

    def set_media_storage_dir(self, new_dir: str, move_existing: bool = False) -> dict:
        res = self.media_mgr.set_storage_dir(new_dir, move_existing=move_existing)
        self.config.set("media_storage_dir", new_dir)
        self.wake()
        return res

    def get_status(self) -> dict:
        """Full status snapshot for web interface."""
        stats = self.sensors.get_stats()
        theme_id = self.config.get("active_theme", "cyber_dual")
        theme_cfg = self.config.get_theme_config(theme_id)
        b_pct = self.usb.brightness_pct

        return {
            "mode": self.config.get("mode", "monitor"),
            "orientation": self.config.get("orientation", 180),
            "active_theme": theme_id,
            "theme_config": theme_cfg,
            "active_media_id": self.config.get("active_media_id"),
            "temp_unit": self.config.get("temp_unit", "C"),
            "brightness": b_pct,
            "brightness_percent": b_pct,
            "autostart": self.config.get("autostart", False),
            "usb_connected": self.usb.is_connected,
            "sensor_source": stats.get("source", "psutil"),
            "fps": self.fps_counter,
            "sensors": stats,
            "available_themes": list_themes(),
            "available_metrics": get_available_metrics(),
            "media_list": self.media_mgr.list_media(),
            "media_storage_dir": self.media_mgr.storage_dir,
            "text_config": self.text_animator.get_config(),
            "available_fonts": [{"id": k, "name": v["name"]} for k, v in FONTS_REGISTRY.items()],
            "available_effects": EFFECTS
        }
