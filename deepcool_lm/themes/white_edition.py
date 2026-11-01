"""
Theme: White Edition
Clean, premium aesthetic tailored for the DeepCool LM360 White edition cooler.
Frost white styling with ice-blue and mint accents.
"""

import time
from PIL import Image, ImageDraw
from deepcool_lm.themes.theme_base import BaseTheme, get_font, frame_to_rgb565


class WhiteEditionTheme(BaseTheme):
    id = "white_edition"
    name = "White Edition"
    description = "Sleek frosty minimal theme designed specifically for the LM360 White cooler."

    @classmethod
    def get_supported_slots(cls) -> list[dict]:
        from deepcool_lm.themes.theme_base import METRIC_DEFINITIONS
        return [
            {
                "id": "slot1",
                "name": "Slot 1 (Left Card)",
                "default": "cpu_temp",
                "options": list(METRIC_DEFINITIONS.keys())
            },
            {
                "id": "slot2",
                "name": "Slot 2 (Right Card)",
                "default": "gpu_temp",
                "options": list(METRIC_DEFINITIONS.keys())
            }
        ]

    def render(self, stats: dict, orientation: int = 180, config: dict = None) -> tuple[bytes, Image.Image]:
        if config is None:
            config = {}

        slot1_metric = config.get("slot1", "cpu_temp")
        slot2_metric = config.get("slot2", "gpu_temp")
        temp_unit = config.get("temp_unit", "C")

        f_header = get_font("segoeui.ttf", 11)
        f_title = get_font("segoeuib.ttf", 12)
        f_large = get_font("segoeuib.ttf", 34)
        f_unit = get_font("segoeui.ttf", 15)
        f_foot = get_font("segoeui.ttf", 11)

        # Deep frost dark canvas
        img = Image.new("RGB", (320, 240), color=(16, 18, 24))
        draw = ImageDraw.Draw(img)

        # Subtle white-edition top bar
        draw.rectangle([0, 0, 320, 28], fill=(24, 28, 38))
        draw.text((12, 6), "LM360 WHITE EDITION", fill=(240, 245, 255), font=f_header)
        t_str = time.strftime("%H:%M")
        draw.text((276, 6), t_str, fill=(160, 175, 195), font=f_header)

        # Left Column Card (X: 10..155, Y: 36..185)
        self._render_column_card(draw, 10, 36, 145, 150, slot1_metric, stats, temp_unit,
                                 f_title, f_large, f_unit, (120, 215, 255))

        # Right Column Card (X: 165..310, Y: 36..185)
        self._render_column_card(draw, 165, 36, 145, 150, slot2_metric, stats, temp_unit,
                                 f_title, f_large, f_unit, (120, 255, 205))

        # Bottom Quick Status Bar (Y: 195..232)
        draw.rounded_rectangle([10, 194, 310, 232], radius=6, fill=(24, 28, 38), outline=(45, 55, 75), width=1)
        cpu_ghz = stats.get("cpu_clock", 0) / 1000.0
        ram_pct = stats.get("ram_load", 0)
        draw.text((22, 204), f"CPU: {stats.get('cpu_load', 0):.0f}% ({cpu_ghz:.2f}GHz)", fill=(200, 210, 230), font=f_foot)
        draw.text((180, 204), f"RAM: {ram_pct:.0f}% ({stats.get('ram_used_gb', 0):.1f}GB)", fill=(200, 210, 230), font=f_foot)

        preview_img = img.copy()
        if orientation == 180:
            lcd_img = img.rotate(180)
        else:
            lcd_img = img

        return frame_to_rgb565(lcd_img), preview_img

    def _render_column_card(self, draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
                            metric_key: str, stats: dict, temp_unit: str, f_title, f_large, f_unit, accent):
        val_str, unit_str, pct, title = self.format_metric(metric_key, stats, temp_unit)

        # Frosted card background with ice border
        draw.rounded_rectangle([x, y, x + w, y + h], radius=8, fill=(22, 26, 36), outline=(60, 75, 100), width=1)

        # Title
        draw.text((x + 14, y + 14), title, fill=(170, 185, 210), font=f_title)

        # Large Value
        draw.text((x + 14, y + 42), val_str, fill=(255, 255, 255), font=f_large)

        # Unit badge
        bbox = f_large.getbbox(val_str)
        val_w = (bbox[2] - bbox[0]) if bbox else 45
        draw.text((x + 18 + val_w, y + 54), unit_str, fill=accent, font=f_unit)

        # Circular or horizontal gauge bar
        bar_x = x + 14
        bar_y = y + 104
        bar_w = w - 28
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 10], radius=5, fill=(35, 42, 58))
        fill_w = int(bar_w * (pct / 100.0))
        if fill_w > 5:
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + 10], radius=5, fill=accent)

        # Percent text below bar
        f_small = get_font("segoeui.ttf", 11)
        draw.text((bar_x, bar_y + 16), f"{pct:.0f}% capacity", fill=(140, 155, 180), font=f_small)

