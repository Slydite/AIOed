"""
Base theme class and rendering utilities for DeepCool LM360 LCD (320x240).
"""

from abc import ABC, abstractmethod
import os
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = r"C:\Windows\Fonts"

# Cache loaded fonts
_FONT_CACHE = {}


def get_font(name: str = "segoeui.ttf", size: int = 14) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    key = (name, size)
    if key not in _FONT_CACHE:
        assets_path = os.path.join("assets", "fonts", name)
        font_path = os.path.join(FONTS_DIR, name)
        target = assets_path if os.path.exists(assets_path) else font_path
        try:
            if os.path.exists(target):
                _FONT_CACHE[key] = ImageFont.truetype(target, size)
            elif os.path.exists(font_path):
                _FONT_CACHE[key] = ImageFont.truetype(font_path, size)
            else:
                _FONT_CACHE[key] = ImageFont.load_default()
        except Exception:
            _FONT_CACHE[key] = ImageFont.load_default()
    return _FONT_CACHE[key]


def frame_to_rgb565(img_rgb: Image.Image) -> bytes:
    """Fast numpy RGB to RGB565 little-endian byte array."""
    arr = np.asarray(img_rgb)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    rgb565 = (r << 11) | (g << 5) | b
    return rgb565.tobytes()


def get_accent_color(percent: float) -> tuple[int, int, int]:
    """Dynamic color from cool teal -> energetic yellow -> warning orange -> critical red."""
    if percent < 55:
        return (0, 225, 185)       # Cyan/Teal
    elif percent < 75:
        return (255, 205, 45)      # Amber/Yellow
    elif percent < 88:
        return (255, 130, 35)      # Orange
    else:
        return (255, 60, 60)       # Red


METRIC_DEFINITIONS = {
    "cpu_temp": {"name": "CPU Temperature", "short": "CPU TEMP", "default_unit": "°C", "max_val": 100.0},
    "cpu_power": {"name": "CPU Power", "short": "CPU POWER", "default_unit": "W", "max_val": 150.0},
    "cpu_load": {"name": "CPU Usage", "short": "CPU LOAD", "default_unit": "%", "max_val": 100.0},
    "cpu_clock": {"name": "CPU Frequency", "short": "CPU FREQ", "default_unit": "GHz", "max_val": 6.0},
    "gpu_temp": {"name": "GPU Temperature", "short": "GPU TEMP", "default_unit": "°C", "max_val": 100.0},
    "gpu_power": {"name": "GPU Power", "short": "GPU POWER", "default_unit": "W", "max_val": 300.0},
    "gpu_load": {"name": "GPU Usage", "short": "GPU LOAD", "default_unit": "%", "max_val": 100.0},
    "gpu_clock": {"name": "GPU Frequency", "short": "GPU FREQ", "default_unit": "MHz", "max_val": 3000.0},
    "ram_load": {"name": "RAM Usage", "short": "RAM LOAD", "default_unit": "%", "max_val": 100.0},
    "ram_used": {"name": "RAM Used", "short": "RAM USED", "default_unit": "GB", "max_val": 64.0},
    "fps_avg": {"name": "Game FPS (avg)", "short": "FPS AVG", "default_unit": "FPS", "max_val": 240.0},
    "fps_1pct": {"name": "Game FPS (1% low)", "short": "FPS 1%", "default_unit": "FPS", "max_val": 240.0},
    "disk_temp": {"name": "Disk Temperature", "short": "DISK TEMP", "default_unit": "°C", "max_val": 80.0},
}


class BaseTheme(ABC):
    """Abstract base class for all LM360 display themes."""

    id: str = "base"
    name: str = "Base Theme"
    description: str = "Base LCD Theme"

    @classmethod
    def get_supported_slots(cls) -> list[dict]:
        """Return configurable slots for this theme."""
        return [
            {
                "id": "slot1",
                "name": "Slot 1 (Top)",
                "default": "cpu_temp",
                "options": list(METRIC_DEFINITIONS.keys())
            },
            {
                "id": "slot2",
                "name": "Slot 2 (Bottom)",
                "default": "gpu_temp",
                "options": list(METRIC_DEFINITIONS.keys())
            }
        ]

    @abstractmethod
    def render(self, stats: dict, orientation: int = 180, config: dict = None) -> tuple[bytes, Image.Image]:
        """
        Renders the theme.
        Returns:
            rgb565_bytes: bytes (153600)
            preview_image: PIL Image (320x240 RGB upright preview for Web UI)
        """
        pass

    def format_metric(self, metric_key: str, stats: dict, temp_unit: str = "C") -> tuple[str, str, float, str]:
        """
        Returns (val_str, unit_str, percent_0_100, short_title).
        """
        meta = METRIC_DEFINITIONS.get(metric_key, {"short": metric_key.upper(), "default_unit": "", "max_val": 100.0})
        title = meta["short"]

        if metric_key == "cpu_temp":
            val_c = stats.get("cpu_temp", 0.0)
            pct = max(0.0, min(100.0, val_c))
            if temp_unit == "F":
                return f"{int(round((val_c * 9/5) + 32))}", "°F", pct, title
            return f"{int(round(val_c))}", "°C", pct, title

        elif metric_key == "cpu_power":
            val = stats.get("cpu_power", 0.0)
            pct = max(0.0, min(100.0, (val / meta["max_val"]) * 100.0))
            return f"{val:.1f}", "W", pct, title

        elif metric_key == "cpu_load":
            val = stats.get("cpu_load", 0.0)
            return f"{val:4.1f}", "%", max(0.0, min(100.0, val)), title

        elif metric_key == "cpu_clock":
            mhz = stats.get("cpu_clock", 0.0)
            ghz = mhz / 1000.0
            pct = max(0.0, min(100.0, (ghz / meta["max_val"]) * 100.0))
            return f"{ghz:.2f}", "GHz", pct, title

        elif metric_key == "gpu_temp":
            val_c = stats.get("gpu_temp", 0.0)
            pct = max(0.0, min(100.0, val_c))
            if temp_unit == "F":
                return f"{int(round((val_c * 9/5) + 32))}", "°F", pct, title
            return f"{int(round(val_c))}", "°C", pct, title

        elif metric_key == "gpu_power":
            val = stats.get("gpu_power", 0.0)
            pct = max(0.0, min(100.0, (val / meta["max_val"]) * 100.0))
            return f"{val:.1f}", "W", pct, title

        elif metric_key == "gpu_load":
            val = stats.get("gpu_load", 0.0)
            return f"{val:4.1f}", "%", max(0.0, min(100.0, val)), title

        elif metric_key == "gpu_clock":
            mhz = stats.get("gpu_clock", 0.0)
            pct = max(0.0, min(100.0, (mhz / meta["max_val"]) * 100.0))
            return f"{int(round(mhz))}", "MHz", pct, title

        elif metric_key == "ram_load":
            val = stats.get("ram_load", 0.0)
            return f"{val:4.1f}", "%", max(0.0, min(100.0, val)), title

        elif metric_key == "ram_used":
            used = stats.get("ram_used_gb", 0.0)
            tot = stats.get("ram_total_gb", 32.0)
            pct = (used / tot * 100.0) if tot > 0 else 0.0
            return f"{used:.1f}", f"/{tot:.0f}G", max(0.0, min(100.0, pct)), title

        elif metric_key in ("fps_avg", "fps_1pct"):
            val = stats.get(metric_key, 0.0)
            pct = max(0.0, min(100.0, (val / meta["max_val"]) * 100.0))
            return f"{val:.0f}", "FPS", pct, title

        elif metric_key == "disk_temp":
            val_c = stats.get("disk_temp", 0.0)
            pct = max(0.0, min(100.0, val_c))
            return f"{int(round(val_c))}", "°C", pct, title

        return "N/A", "", 0.0, title

