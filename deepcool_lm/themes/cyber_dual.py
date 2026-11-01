"""
Theme: Cyber Dual Card
Modern dark HUD with two customizable metric cards (Slot 1 and Slot 2).
"""

import time
from PIL import Image, ImageDraw
from deepcool_lm.themes.theme_base import BaseTheme, get_font, get_accent_color, frame_to_rgb565


class CyberDualTheme(BaseTheme):
    id = "cyber_dual"
    name = "Cyber Dual Cards"
    description = "Futuristic dual-card display with live clock and dynamic accent bars."

    def render(self, stats: dict, orientation: int = 180, config: dict = None) -> tuple[bytes, Image.Image]:
        if config is None:
            config = {}

        slot1_metric = config.get("slot1", "cpu_temp")
        slot2_metric = config.get("slot2", "gpu_temp")
        temp_unit = config.get("temp_unit", "C")

        # Fonts
        f_header = get_font("segoeui.ttf", 12)
        f_title = get_font("segoeuib.ttf", 13)
        f_large = get_font("segoeuib.ttf", 36)
        f_unit = get_font("segoeui.ttf", 16)
        f_sub = get_font("segoeui.ttf", 13)

        # Base canvas
        img = Image.new("RGB", (320, 240), color=(12, 14, 20))
        draw = ImageDraw.Draw(img)

        # Top Header Bar (Y: 0..26)
        draw.rectangle([0, 0, 320, 26], fill=(18, 22, 30))
        draw.line([0, 26, 320, 26], fill=(30, 36, 48), width=1)
        draw.text((12, 5), "DEEPCOOL LM360", fill=(0, 225, 185), font=f_header)
        t_str = time.strftime("%H:%M:%S")
        draw.text((254, 5), t_str, fill=(140, 145, 160), font=f_header)

        # Render Card 1 (Slot 1: Y 32..128)
        self._render_card(draw, 32, slot1_metric, stats, temp_unit, f_title, f_large, f_unit, f_sub)

        # Render Card 2 (Slot 2: Y 136..232)
        self._render_card(draw, 136, slot2_metric, stats, temp_unit, f_title, f_large, f_unit, f_sub)

        # Keep upright copy for Web UI preview
        preview_img = img.copy()

        # Apply hardware orientation
        if orientation == 180:
            lcd_img = img.rotate(180)
        else:
            lcd_img = img

        return frame_to_rgb565(lcd_img), preview_img

    def _render_card(self, draw: ImageDraw.ImageDraw, y_top: int, metric_key: str, stats: dict,
                     temp_unit: str, f_title, f_large, f_unit, f_sub):
        val_str, unit_str, pct, title = self.format_metric(metric_key, stats, temp_unit)
        accent = get_accent_color(pct)

        # Background card
        draw.rounded_rectangle(
            [10, y_top, 310, y_top + 96],
            radius=8,
            fill=(18, 22, 32),
            outline=(36, 44, 62),
            width=1
        )

        # Left subtle colored indicator pill
        draw.rounded_rectangle([15, y_top + 14, 18, y_top + 34], radius=2, fill=accent)

        # Metric Title
        draw.text((26, y_top + 14), title, fill=(160, 168, 185), font=f_title)

        # Large Value
        draw.text((26, y_top + 32), val_str, fill=(255, 255, 255), font=f_large)

        # Unit next to value
        bbox = f_large.getbbox(val_str)
        val_w = (bbox[2] - bbox[0]) if bbox else 60
        draw.text((32 + val_w, y_top + 48), unit_str, fill=accent, font=f_unit)

        # Secondary info on the right side
        if "cpu" in metric_key:
            sub_text = f"Clock: {stats.get('cpu_clock', 0)/1000:.2f} GHz"
        elif "gpu" in metric_key:
            sub_text = f"Clock: {int(stats.get('gpu_clock', 0))} MHz"
        elif "ram" in metric_key:
            sub_text = f"{stats.get('ram_used_gb', 0):.1f}/{stats.get('ram_total_gb', 32):.0f} GB"
        else:
            sub_text = f"Load: {stats.get('cpu_load', 0):.0f}%"

        draw.text((180, y_top + 16), sub_text, fill=(125, 135, 155), font=f_sub)

        # Progress Bar (Y: y_top + 78, Height: 8)
        bar_x = 24
        bar_w = 272
        bar_y = y_top + 78
        draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + 8], radius=4, fill=(28, 35, 50))
        fill_w = int(bar_w * (pct / 100.0))
        if fill_w > 4:
            draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + 8], radius=4, fill=accent)

