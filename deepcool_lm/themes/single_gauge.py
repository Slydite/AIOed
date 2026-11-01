"""
Theme: Single Gauge Hero
Focus on a single primary metric with prominent typography and secondary stats.
"""

import time
from PIL import Image, ImageDraw
from deepcool_lm.themes.theme_base import BaseTheme, get_font, get_accent_color, frame_to_rgb565


class SingleGaugeTheme(BaseTheme):
    id = "single_gauge"
    name = "Focus Hero Gauge"
    description = "Bold hero gauge for a primary metric (e.g. CPU Power or Temp) with secondary cards."

    @classmethod
    def get_supported_slots(cls) -> list[dict]:
        from deepcool_lm.themes.theme_base import METRIC_DEFINITIONS
        return [
            {
                "id": "hero_metric",
                "name": "Hero Metric",
                "default": "cpu_power",
                "options": list(METRIC_DEFINITIONS.keys())
            },
            {
                "id": "sec1",
                "name": "Sub Metric 1",
                "default": "cpu_temp",
                "options": list(METRIC_DEFINITIONS.keys())
            },
            {
                "id": "sec2",
                "name": "Sub Metric 2",
                "default": "gpu_temp",
                "options": list(METRIC_DEFINITIONS.keys())
            },
            {
                "id": "sec3",
                "name": "Sub Metric 3",
                "default": "ram_load",
                "options": list(METRIC_DEFINITIONS.keys())
            }
        ]

    def render(self, stats: dict, orientation: int = 180, config: dict = None) -> tuple[bytes, Image.Image]:
        if config is None:
            config = {}

        hero_key = config.get("hero_metric", "cpu_power")
        sec1_key = config.get("sec1", "cpu_temp")
        sec2_key = config.get("sec2", "gpu_temp")
        sec3_key = config.get("sec3", "ram_load")
        temp_unit = config.get("temp_unit", "C")

        f_hero_title = get_font("segoeuib.ttf", 13)
        f_hero_val = get_font("segoeuib.ttf", 46)
        f_hero_unit = get_font("segoeui.ttf", 20)
        f_sec_title = get_font("segoeui.ttf", 10)
        f_sec_val = get_font("segoeuib.ttf", 13)

        img = Image.new("RGB", (320, 240), color=(10, 12, 18))
        draw = ImageDraw.Draw(img)

        # Hero Card (Y: 10..152)
        val_str, unit_str, pct, title = self.format_metric(hero_key, stats, temp_unit)
        accent = get_accent_color(pct)

        draw.rounded_rectangle([10, 10, 310, 154], radius=10, fill=(16, 20, 30), outline=(32, 40, 58), width=1)
        draw.text((24, 20), title, fill=(160, 170, 190), font=f_hero_title)

        # Time in top right
        t_str = time.strftime("%H:%M:%S")
        draw.text((230, 20), t_str, fill=(110, 120, 140), font=get_font("segoeui.ttf", 12))

        # Hero Value
        draw.text((24, 46), val_str, fill=(255, 255, 255), font=f_hero_val)
        bbox = f_hero_val.getbbox(val_str)
        w_val = (bbox[2] - bbox[0]) if bbox else 100
        draw.text((32 + w_val, 66), unit_str, fill=accent, font=f_hero_unit)

        # Dynamic Wide Bar
        bar_x = 24
        bar_y = 126
        bar_w = 272
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 12], radius=6, fill=(28, 36, 52))
        fill_w = int(bar_w * (pct / 100.0))
        if fill_w > 6:
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + 12], radius=6, fill=accent)

        # 3 Sub-Cards (Y: 162..230)
        subs = [
            (10, sec1_key),
            (113, sec2_key),
            (217, sec3_key),
        ]
        sub_w = 93
        for x, key in subs:
            s_val, s_unit, s_pct, s_title = self.format_metric(key, stats, temp_unit)
            s_acc = get_accent_color(s_pct)

            draw.rounded_rectangle([x, 162, x + sub_w, 230], radius=8, fill=(16, 20, 30), outline=(32, 40, 58), width=1)
            draw.text((x + 10, 170), s_title[:10], fill=(130, 140, 160), font=f_sec_title)
            draw.text((x + 10, 192), f"{s_val}{s_unit}", fill=s_acc, font=f_sec_val)

        preview_img = img.copy()
        if orientation == 180:
            lcd_img = img.rotate(180)
        else:
            lcd_img = img

        return frame_to_rgb565(lcd_img), preview_img

