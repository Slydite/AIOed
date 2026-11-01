"""
Theme: Retro Matrix / Terminal HUD
Monospace hacker HUD with phosphor glow and ASCII telemetry monitors.
"""

import time
from PIL import Image, ImageDraw
from deepcool_lm.themes.theme_base import BaseTheme, get_font, frame_to_rgb565


class RetroMatrixTheme(BaseTheme):
    id = "retro_matrix"
    name = "Retro Terminal HUD"
    description = "Phosphor green monospace terminal with ASCII telemetry bars."

    @classmethod
    def get_supported_slots(cls) -> list[dict]:
        from deepcool_lm.themes.theme_base import METRIC_DEFINITIONS
        return [
            {
                "id": "slot1",
                "name": "Row 1 Metric",
                "default": "cpu_temp",
                "options": list(METRIC_DEFINITIONS.keys())
            },
            {
                "id": "slot2",
                "name": "Row 2 Metric",
                "default": "cpu_power",
                "options": list(METRIC_DEFINITIONS.keys())
            },
            {
                "id": "slot3",
                "name": "Row 3 Metric",
                "default": "gpu_temp",
                "options": list(METRIC_DEFINITIONS.keys())
            },
            {
                "id": "slot4",
                "name": "Row 4 Metric",
                "default": "gpu_power",
                "options": list(METRIC_DEFINITIONS.keys())
            }
        ]

    def render(self, stats: dict, orientation: int = 180, config: dict = None) -> tuple[bytes, Image.Image]:
        if config is None:
            config = {}

        m1 = config.get("slot1", "cpu_temp")
        m2 = config.get("slot2", "cpu_power")
        m3 = config.get("slot3", "gpu_temp")
        m4 = config.get("slot4", "gpu_power")
        temp_unit = config.get("temp_unit", "C")

        f_mono = get_font("consola.ttf", 13)
        f_mono_bold = get_font("consolab.ttf", 14)

        img = Image.new("RGB", (320, 240), color=(5, 12, 8))
        draw = ImageDraw.Draw(img)

        # Matrix phosphor colors
        c_green = (50, 255, 120)
        c_dim = (25, 120, 60)
        c_dark = (12, 45, 25)

        # Terminal border
        draw.rectangle([4, 4, 315, 235], outline=c_dim, width=1)
        draw.rectangle([6, 6, 313, 233], outline=c_dark, width=1)

        # Terminal Header
        draw.text((12, 10), "SYS_MON://DEEPCOOL_LM360", fill=c_green, font=f_mono_bold)
        t_str = time.strftime("%H:%M:%S")
        draw.text((230, 10), f"[{t_str}]", fill=c_dim, font=f_mono)
        draw.line([8, 28, 311, 28], fill=c_dim, width=1)

        # 4 Rows of metrics
        rows = [m1, m2, m3, m4]
        y_starts = [36, 84, 132, 180]

        for metric_key, y in zip(rows, y_starts):
            val_str, unit_str, pct, title = self.format_metric(metric_key, stats, temp_unit)

            # Label + Value
            label_text = f"> {title[:10]:<10}: {val_str:>5} {unit_str:<3}"
            draw.text((12, y), label_text, fill=c_green, font=f_mono)

            # Terminal Bar: [==========.....]
            bar_w = 296
            bar_h = 10
            bar_y = y + 20
            draw.rectangle([12, bar_y, 12 + bar_w, bar_y + bar_h], outline=c_dim, width=1)

            fill_w = int((bar_w - 4) * (pct / 100.0))
            if fill_w > 0:
                draw.rectangle([14, bar_y + 2, 14 + fill_w, bar_y + bar_h - 2], fill=c_green)

        preview_img = img.copy()
        if orientation == 180:
            lcd_img = img.rotate(180)
        else:
            lcd_img = img

        return frame_to_rgb565(lcd_img), preview_img

