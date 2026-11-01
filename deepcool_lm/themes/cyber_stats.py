"""
Theme: Cyber Large Stats
High-contrast, large-font HUD displaying CPU, GPU, and RAM stats with dynamic value-based color-shifting
and luminous breathing neon accents.
"""

import math
import time
from PIL import Image, ImageDraw
from deepcool_lm.themes.theme_base import BaseTheme, get_font, frame_to_rgb565


def get_temp_color(temp_c: float) -> tuple[int, int, int]:
    """Dynamic temperature coloring: Cyan -> Green -> Yellow -> Orange -> Alert Red."""
    if temp_c < 50:
        return (0, 240, 255)       # Electric cyan (Cool / Idle)
    elif temp_c < 65:
        return (40, 255, 130)      # Vivid neon green (Normal)
    elif temp_c < 75:
        return (255, 220, 0)       # Cyber yellow (Warm)
    elif temp_c < 85:
        return (255, 120, 15)      # Hot orange (Hot)
    else:
        return (255, 30, 60)       # Critical red (Heavy Load / Throttle alert)


def get_load_color(load_pct: float) -> tuple[int, int, int]:
    """Dynamic usage/load coloring: Cyan -> Green -> Orange -> Red."""
    if load_pct < 30:
        return (0, 240, 255)       # Electric cyan (Light)
    elif load_pct < 65:
        return (40, 255, 130)      # Neon green (Moderate)
    elif load_pct < 85:
        return (255, 185, 15)      # Amber orange (High)
    else:
        return (255, 30, 60)       # Critical red (Heavy / Full load)


def get_power_color(watts: float, max_w: float = 150.0) -> tuple[int, int, int]:
    """Dynamic power coloring scaled by max TDP."""
    pct = (watts / max_w) * 100.0 if max_w > 0 else 0.0
    if pct < 35:
        return (0, 240, 255)       # Cool cyan
    elif pct < 65:
        return (40, 255, 130)      # Neon green
    elif pct < 85:
        return (255, 220, 0)       # Golden yellow
    else:
        return (255, 35, 60)       # Alert red


class CyberStatsTheme(BaseTheme):
    id = "cyber_stats"
    name = "Cyber Large Stats"
    description = "Large high-contrast display with CPU, GPU & RAM stats and dynamic color thresholds."

    @classmethod
    def get_supported_slots(cls) -> list[dict]:
        return []

    def render(self, stats: dict, orientation: int = 180, config: dict = None) -> tuple[bytes, Image.Image]:
        if config is None:
            config = {}

        temp_unit = config.get("temp_unit", "C")
        t_now = time.perf_counter()

        # Canvas
        img = Image.new("RGB", (320, 240), color=(6, 8, 13))
        draw = ImageDraw.Draw(img)

        # Fonts
        f_label = get_font("Orbitron-Bold.ttf", 11)
        f_num = get_font("Orbitron-Bold.ttf", 23)
        f_sub = get_font("ShareTechMono-Regular.ttf", 12)
        f_ram_num = get_font("Orbitron-Bold.ttf", 26)

        # Pulse for breathing accent pillar
        pulse = 0.72 + 0.28 * math.sin(t_now * 3.0)

        # 1. CPU Telemetry
        cpu_load = max(0.0, float(stats.get("cpu_load", 0.0)))
        cpu_pwr = max(0.0, float(stats.get("cpu_power", 0.0)))
        cpu_temp_c = float(stats.get("cpu_temp", 0.0))
        cpu_clock = stats.get("cpu_clock", 0.0)
        cpu_sub = f"{cpu_clock/1000.0:.2f} GHz" if cpu_clock > 0 else ""

        # 2. GPU Telemetry
        gpu_load = max(0.0, float(stats.get("gpu_load", 0.0)))
        gpu_pwr = max(0.0, float(stats.get("gpu_power", 0.0)))
        gpu_temp_c = float(stats.get("gpu_temp", 0.0))
        gpu_clock = stats.get("gpu_clock", 0.0)
        gpu_sub = f"{int(gpu_clock)} MHz" if gpu_clock > 0 else ""

        # 3. RAM Telemetry
        ram_load = max(0.0, float(stats.get("ram_load", 0.0)))
        ram_used = stats.get("ram_used_gb", 0.0)
        ram_tot = stats.get("ram_total_gb", 32.0)
        ram_sub = f"{ram_used:.1f} / {ram_tot:.0f} GB" if ram_tot > 0 else ""

        cards = [
            {
                "title": "CPU",
                "y": 6,
                "h": 72,
                "load": cpu_load,
                "pwr": cpu_pwr,
                "temp_c": cpu_temp_c,
                "max_pwr": 160.0,
                "sub": cpu_sub
            },
            {
                "title": "GPU",
                "y": 84,
                "h": 72,
                "load": gpu_load,
                "pwr": gpu_pwr,
                "temp_c": gpu_temp_c,
                "max_pwr": 280.0,
                "sub": gpu_sub
            },
            {
                "title": "RAM LOAD",
                "y": 162,
                "h": 72,
                "load": ram_load,
                "pwr": None,
                "temp_c": None,
                "max_pwr": 100.0,
                "sub": ram_sub
            }
        ]

        for c in cards:
            y = c["y"]
            h = c["h"]

            # Card background
            draw.rounded_rectangle([6, y, 314, y + h], radius=7, fill=(11, 15, 22), outline=(24, 32, 45), width=1)

            # Left breathing glow accent pillar
            main_color = get_temp_color(c["temp_c"]) if c["temp_c"] is not None else get_load_color(c["load"])
            glow_pillar = (int(main_color[0] * pulse), int(main_color[1] * pulse), int(main_color[2] * pulse))
            draw.rounded_rectangle([10, y + 8, 13, y + h - 8], radius=2, fill=glow_pillar)

            # Card Header: Title + Telemetry Subtext
            draw.text((22, y + 7), c["title"], fill=(155, 175, 205), font=f_label)
            if c["sub"]:
                draw.text((215, y + 7), c["sub"], fill=(90, 110, 135), font=f_sub)

            # Card Content: Big Numbers
            if c["pwr"] is not None:
                load_val = int(round(c["load"]))
                pwr_val = int(round(c["pwr"]))

                if temp_unit == "F":
                    temp_disp = int(round((c["temp_c"] * 9/5) + 32))
                    temp_unit_str = "°F"
                else:
                    temp_disp = int(round(c["temp_c"]))
                    temp_unit_str = "°C"

                load_c = get_load_color(c["load"])
                pwr_c = get_power_color(c["pwr"], c["max_pwr"])
                temp_c = get_temp_color(c["temp_c"])

                load_txt = f"{load_val}%"
                pwr_txt = f"{pwr_val} W"
                temp_txt = f"{temp_disp}{temp_unit_str}"

                sep = " | "
                sep_c = (50, 62, 82)

                cur_x = 22
                # Load segment with soft luminous shadow
                draw.text((cur_x + 1, y + 30), load_txt, fill=(load_c[0]//5, load_c[1]//5, load_c[2]//5), font=f_num)
                draw.text((cur_x, y + 29), load_txt, fill=load_c, font=f_num)
                b = draw.textbbox((0, 0), load_txt, font=f_num)
                cur_x += (b[2] - b[0]) + 5

                # Divider 1
                draw.text((cur_x, y + 29), sep, fill=sep_c, font=f_num)
                b = draw.textbbox((0, 0), sep, font=f_num)
                cur_x += (b[2] - b[0]) + 5

                # Power segment with soft luminous shadow
                draw.text((cur_x + 1, y + 30), pwr_txt, fill=(pwr_c[0]//5, pwr_c[1]//5, pwr_c[2]//5), font=f_num)
                draw.text((cur_x, y + 29), pwr_txt, fill=pwr_c, font=f_num)
                b = draw.textbbox((0, 0), pwr_txt, font=f_num)
                cur_x += (b[2] - b[0]) + 5

                # Divider 2
                draw.text((cur_x, y + 29), sep, fill=sep_c, font=f_num)
                b = draw.textbbox((0, 0), sep, font=f_num)
                cur_x += (b[2] - b[0]) + 5

                # Temp segment with soft luminous shadow
                draw.text((cur_x + 1, y + 30), temp_txt, fill=(temp_c[0]//5, temp_c[1]//5, temp_c[2]//5), font=f_num)
                draw.text((cur_x, y + 29), temp_txt, fill=temp_c, font=f_num)

            else:
                # RAM Load: Massive font
                ram_val = int(round(c["load"]))
                ram_c = get_load_color(c["load"])
                ram_txt = f"{ram_val} %"

                draw.text((23, y + 28), ram_txt, fill=(ram_c[0]//5, ram_c[1]//5, ram_c[2]//5), font=f_ram_num)
                draw.text((22, y + 27), ram_txt, fill=ram_c, font=f_ram_num)

                # Glowing progress bar
                bar_x = 135
                bar_y = y + 38
                bar_w = 165
                bar_h = 10
                draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=4, fill=(20, 26, 38))
                fill_w = int(bar_w * (c["load"] / 100.0))
                if fill_w > 4:
                    draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=4, fill=ram_c)

        preview_img = img.copy()
        if orientation == 180:
            lcd_img = img.rotate(180)
        else:
            lcd_img = img

        return frame_to_rgb565(lcd_img), preview_img

