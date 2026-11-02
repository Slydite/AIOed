"""
Configuration manager for DeepCool LM360 service.
Persists settings to config.json.
"""

import copy
import json
import logging
import os
import threading
import winreg

logger = logging.getLogger("deepcool_lm.config")

CONFIG_FILE = "config.json"
STARTUP_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "AIOed_LM360"

DEFAULT_CONFIG = {
    "mode": "monitor",           # "monitor", "media", "text", "off"
    "orientation": 180,          # 180 (cooler mounted upside down) or 0
    "active_theme": "cyber_stats",
    "temp_unit": "C",            # "C" or "F"
    "brightness": 100,           # hardware backlight PWM, 0..100%
    "active_media_id": None,
    "playback_fps_cap": 30,
    "web_port": 5220,
    "autostart": False,
    "media_storage_dir": "media_store",
    "text_mode_config": {
        "text": "DEEPCOOL LM360",
        "subtext": "{time}  ●  LIQUID COOLED",
        "font": "orbitron",
        "font_size": 32,
        "sub_font_size": 14,
        "text_y": -1,
        "subtext_y": -1,
        "text_align": "center",
        "sub_align": "center",
        "effect": "neon_pulse",
        "color": "#00FFCC",
        "sub_color": "#0088FF",
        "glow_color": "#0077FF",
        "bg_color": "#070A12",
        "bg_style": "grid",
        "speed": 1.0
    },
    "theme_configs": {
        "cyber_dual": {
            "slot1": "cpu_power",
            "slot2": "gpu_temp"
        },
        "white_edition": {
            "slot1": "cpu_power",
            "slot2": "gpu_temp"
        },
        "single_gauge": {
            "hero_metric": "cpu_power",
            "sec1": "cpu_temp",
            "sec2": "gpu_temp",
            "sec3": "ram_load"
        },
        "retro_matrix": {
            "slot1": "cpu_temp",
            "slot2": "cpu_power",
            "slot3": "gpu_temp",
            "slot4": "gpu_power"
        }
    }
}


class ConfigManager:
    """Thread-safe configuration manager."""

    def __init__(self, filepath: str = CONFIG_FILE):
        self.filepath = os.path.abspath(filepath)
        self._lock = threading.Lock()
        self.data = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self):
        with self._lock:
            if os.path.exists(self.filepath):
                try:
                    with open(self.filepath, "r", encoding="utf-8") as f:
                        loaded = json.load(f)
                    for k, v in loaded.items():
                        if isinstance(v, dict) and k in self.data and isinstance(self.data[k], dict):
                            self.data[k].update(v)
                        else:
                            self.data[k] = v
                except Exception as e:
                    logger.warning(f"Error loading config from {self.filepath}: {e}")
            else:
                self._save_unlocked()

        # Synchronize Windows autostart on load if enabled
        if self.data.get("autostart"):
            self.set_autostart(True)

    def save(self):
        with self._lock:
            self._save_unlocked()

    def _save_unlocked(self):
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving config to {self.filepath}: {e}")

    def get(self, key: str, default=None):
        with self._lock:
            return self.data.get(key, default)

    def set(self, key: str, value):
        with self._lock:
            self.data[key] = value
            self._save_unlocked()

    def update_dict(self, updates: dict):
        with self._lock:
            for k, v in updates.items():
                if isinstance(v, dict) and k in self.data and isinstance(self.data[k], dict):
                    self.data[k].update(v)
                else:
                    self.data[k] = v
            self._save_unlocked()

    def get_theme_config(self, theme_id: str) -> dict:
        with self._lock:
            t_configs = self.data.get("theme_configs", {})
            cfg = dict(t_configs.get(theme_id, {}))
            cfg["temp_unit"] = self.data.get("temp_unit", "C")
            return cfg

    def set_theme_slot(self, theme_id: str, slot_id: str, metric: str):
        with self._lock:
            if "theme_configs" not in self.data:
                self.data["theme_configs"] = {}
            if theme_id not in self.data["theme_configs"]:
                self.data["theme_configs"][theme_id] = {}
            self.data["theme_configs"][theme_id][slot_id] = metric
            self._save_unlocked()

    def set_autostart(self, enable: bool) -> bool:
        """Register or unregister from Windows startup registry and Startup folder."""
        with self._lock:
            self.data["autostart"] = enable
            self._save_unlocked()

        try:
            # 1. Update Windows Registry Run key
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REG_KEY, 0, winreg.KEY_SET_VALUE)
            if enable:
                vbs_path = os.path.abspath("run_background.vbs")
                cmd = f'wscript.exe "{vbs_path}"'
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
                # Purge conflicting official DeepCool software from startup
                try:
                    winreg.DeleteValue(key, "DeepCool")
                except FileNotFoundError:
                    pass
            else:
                for name in (APP_NAME, "DeepCoolLM360Display"):
                    try:
                        winreg.DeleteValue(key, name)
                    except FileNotFoundError:
                        pass
            winreg.CloseKey(key)

            # 2. Update Windows Startup folder shortcut
            appdata = os.environ.get("APPDATA")
            if appdata:
                startup_dir = os.path.join(appdata, r"Microsoft\Windows\Start Menu\Programs\Startup")
                startup_lnk = os.path.join(startup_dir, "AIOed Background Service.lnk")
                if enable:
                    vbs_create = os.path.abspath("create_shortcuts.vbs")
                    if os.path.exists(vbs_create):
                        os.system(f'cscript //nologo "{vbs_create}" >nul 2>&1')
                else:
                    if os.path.exists(startup_lnk):
                        try:
                            os.remove(startup_lnk)
                        except Exception:
                            pass
            return True
        except Exception as e:
            logger.warning(f"Failed to update Windows autostart: {e}")
            return False
