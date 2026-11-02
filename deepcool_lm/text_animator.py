"""
Text Animator & Banner Studio for DeepCool LM360 LCD.
Provides real-time multi-element text animations with per-element X & Y positioning,
font sizing, custom fonts, telemetry tags, individual effect pipelines,
custom background colors, and one-click video/loop baking.
"""

import os
import math
import time
import colorsys
import json
import uuid
import numpy as np
from PIL import Image, ImageDraw, ImageFont

WIDTH = 320
HEIGHT = 240
FRAME_BYTES = WIDTH * HEIGHT * 2

FONTS_REGISTRY = {
    "orbitron": {
        "name": "Orbitron (Cyberpunk)",
        "file": "assets/fonts/Orbitron-Bold.ttf",
        "fallback": "C:/Windows/Fonts/bahnschrift.ttf"
    },
    "press_start": {
        "name": "Press Start 2P (8-Bit Arcade)",
        "file": "assets/fonts/PressStart2P-Regular.ttf",
        "fallback": "C:/Windows/Fonts/courbd.ttf"
    },
    "share_tech": {
        "name": "Share Tech Mono (Hacker)",
        "file": "assets/fonts/ShareTechMono-Regular.ttf",
        "fallback": "C:/Windows/Fonts/consolab.ttf"
    },
    "vt323": {
        "name": "VT323 (CRT Terminal)",
        "file": "assets/fonts/VT323-Regular.ttf",
        "fallback": "C:/Windows/Fonts/lucon.ttf"
    },
    "impact": {
        "name": "Impact (Heavy / Bold)",
        "file": "C:/Windows/Fonts/impact.ttf",
        "fallback": "C:/Windows/Fonts/arialbd.ttf"
    },
    "consolas": {
        "name": "Consolas (Monospace)",
        "file": "C:/Windows/Fonts/consolab.ttf",
        "fallback": "C:/Windows/Fonts/courbd.ttf"
    },
    "arial": {
        "name": "Arial Bold (Clean Modern)",
        "file": "C:/Windows/Fonts/arialbd.ttf",
        "fallback": "C:/Windows/Fonts/arial.ttf"
    },
    "bahnschrift": {
        "name": "Bahnschrift (Geometric)",
        "file": "C:/Windows/Fonts/bahnschrift.ttf",
        "fallback": "C:/Windows/Fonts/segoeuib.ttf"
    },
    "segoe": {
        "name": "Segoe UI Bold",
        "file": "C:/Windows/Fonts/segoeuib.ttf",
        "fallback": "C:/Windows/Fonts/arialbd.ttf"
    },
    "courier": {
        "name": "Courier New Bold (Retro)",
        "file": "C:/Windows/Fonts/courbd.ttf",
        "fallback": "C:/Windows/Fonts/consolab.ttf"
    },
    "comic": {
        "name": "Comic Sans Bold",
        "file": "C:/Windows/Fonts/comicbd.ttf",
        "fallback": "C:/Windows/Fonts/arial.ttf"
    }
}

EFFECTS = [
    {"id": "neon_pulse", "name": "Neon Pulse", "desc": "Glowing cyberpunk aura with breathing brightness"},
    {"id": "marquee", "name": "Marquee Ticker", "desc": "Smooth horizontal scrolling banner"},
    {"id": "rainbow_wave", "name": "RGB Rainbow Wave", "desc": "Flowing chromatic spectrum across letters"},
    {"id": "matrix_rain", "name": "Matrix Rain", "desc": "Falling digital code drops with glowing text"},
    {"id": "glitch", "name": "Cyber Glitch", "desc": "Hologram glitch with RGB channel split & scanlines"},
    {"id": "typewriter", "name": "Typewriter", "desc": "Sequential typing with blinking terminal cursor"},
    {"id": "sine_wave", "name": "Sine Wave", "desc": "Smooth undulating floating letter bounce"},
    {"id": "static", "name": "Static (No Effect)", "desc": "Crisp rendered typography with soft shadow"}
]


def hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    """Convert #RRGGBB or #RGB to (R, G, B)."""
    if not hex_str:
        return 0, 229, 163
    hex_str = hex_str.strip().lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    try:
        val = int(hex_str, 16)
        return (val >> 16) & 0xFF, (val >> 8) & 0xFF, val & 0xFF
    except Exception:
        return 0, 229, 163


def frame_to_rgb565(img_rgb: Image.Image) -> bytes:
    """Fast conversion from PIL RGB Image (320x240) to RGB565 little-endian bytes."""
    arr = np.asarray(img_rgb)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    rgb565 = (r << 11) | (g << 5) | b
    return rgb565.tobytes()


class TextAnimator:
    """Renders real-time dynamic text animations for LM360 screen with multi-element support."""

    def __init__(self, config_manager=None):
        self.config_manager = config_manager
        self._font_cache = {}
        self._matrix_drops = None
        self._last_matrix_update = 0.0

        self.default_config = {
            "elements": [
                {
                    "id": "elem_1",
                    "text": "DEEPCOOL LM360",
                    "font": "orbitron",
                    "font_size": 24,
                    "x": -1,
                    "y": 65,
                    "align": "center",
                    "color": "#00FFCC",
                    "glow_color": "#0077FF",
                    "effect": "neon_pulse"
                },
                {
                    "id": "elem_2",
                    "text": "{time}  ●  LIQUID COOLED",
                    "font": "orbitron",
                    "font_size": 14,
                    "x": -1,
                    "y": 150,
                    "align": "center",
                    "color": "#0088FF",
                    "glow_color": "#0077FF",
                    "effect": "neon_pulse"
                }
            ],
            "bg_color": "#070A12",
            "bg_style": "grid",
            "speed": 1.0
        }

    def get_config(self) -> dict:
        cfg = dict(self.default_config)
        if self.config_manager:
            stored = self.config_manager.get("text_mode_config", {})
            if "elements" in stored and isinstance(stored["elements"], list):
                cfg["elements"] = stored["elements"]
                for k in ("bg_color", "bg_style", "speed"):
                    if k in stored:
                        cfg[k] = stored[k]
                return cfg
            elif "text" in stored:
                # Migrate legacy flat format to elements list
                e1 = {
                    "id": "elem_1",
                    "text": stored.get("text", "DEEPCOOL LM360"),
                    "font": stored.get("font", "orbitron"),
                    "font_size": stored.get("font_size", 24),
                    "x": stored.get("text_x", -1),
                    "y": stored.get("text_y", 65),
                    "align": stored.get("text_align", "center"),
                    "color": stored.get("color", "#00FFCC"),
                    "glow_color": stored.get("glow_color", "#0077FF"),
                    "effect": stored.get("effect", "neon_pulse")
                }
                elements = [e1]
                if stored.get("subtext"):
                    e2 = {
                        "id": "elem_2",
                        "text": stored.get("subtext", "{time}  ●  LIQUID COOLED"),
                        "font": stored.get("font", "orbitron"),
                        "font_size": stored.get("sub_font_size", 14),
                        "x": stored.get("subtext_x", -1),
                        "y": stored.get("subtext_y", 150),
                        "align": stored.get("sub_align", "center"),
                        "color": stored.get("sub_color", "#0088FF"),
                        "glow_color": stored.get("glow_color", "#0077FF"),
                        "effect": stored.get("effect", "neon_pulse")
                    }
                    elements.append(e2)
                cfg["elements"] = elements
                for k in ("bg_color", "bg_style", "speed"):
                    if k in stored:
                        cfg[k] = stored[k]
                return cfg
        return cfg

    def set_config(self, new_cfg: dict):
        current = self.get_config()
        if "elements" in new_cfg and isinstance(new_cfg["elements"], list):
            current["elements"] = new_cfg["elements"]
            for k in ("bg_color", "bg_style", "speed"):
                if k in new_cfg:
                    current[k] = new_cfg[k]
        else:
            elems = current.get("elements", [])
            if not elems:
                elems = [dict(self.default_config["elements"][0])]
                current["elements"] = elems

            e1 = elems[0]
            if "text" in new_cfg and new_cfg["text"] is not None: e1["text"] = new_cfg["text"]
            if "font" in new_cfg and new_cfg["font"] is not None: e1["font"] = new_cfg["font"]
            if "font_size" in new_cfg and new_cfg["font_size"] is not None: e1["font_size"] = int(new_cfg["font_size"])
            if "text_x" in new_cfg and new_cfg["text_x"] is not None: e1["x"] = int(new_cfg["text_x"])
            if "text_y" in new_cfg and new_cfg["text_y"] is not None: e1["y"] = int(new_cfg["text_y"])
            if "text_align" in new_cfg and new_cfg["text_align"] is not None: e1["align"] = new_cfg["text_align"]
            if "color" in new_cfg and new_cfg["color"] is not None: e1["color"] = new_cfg["color"]
            if "glow_color" in new_cfg and new_cfg["glow_color"] is not None: e1["glow_color"] = new_cfg["glow_color"]
            if "effect" in new_cfg and new_cfg["effect"] is not None: e1["effect"] = new_cfg["effect"]

            if any(k in new_cfg and new_cfg[k] is not None for k in ("subtext", "sub_font_size", "subtext_x", "subtext_y", "sub_align", "sub_color")):
                if len(elems) < 2:
                    elems.append(dict(self.default_config["elements"][1]))
                e2 = elems[1]
                if "subtext" in new_cfg and new_cfg["subtext"] is not None: e2["text"] = new_cfg["subtext"]
                if "font" in new_cfg and new_cfg["font"] is not None: e2["font"] = new_cfg["font"]
                if "sub_font_size" in new_cfg and new_cfg["sub_font_size"] is not None: e2["font_size"] = int(new_cfg["sub_font_size"])
                if "subtext_x" in new_cfg and new_cfg["subtext_x"] is not None: e2["x"] = int(new_cfg["subtext_x"])
                if "subtext_y" in new_cfg and new_cfg["subtext_y"] is not None: e2["y"] = int(new_cfg["subtext_y"])
                if "sub_align" in new_cfg and new_cfg["sub_align"] is not None: e2["align"] = new_cfg["sub_align"]
                if "sub_color" in new_cfg and new_cfg["sub_color"] is not None: e2["color"] = new_cfg["sub_color"]
                if "glow_color" in new_cfg and new_cfg["glow_color"] is not None: e2["glow_color"] = new_cfg["glow_color"]
                if "effect" in new_cfg and new_cfg["effect"] is not None: e2["effect"] = new_cfg["effect"]

            for k in ("bg_color", "bg_style", "speed"):
                if k in new_cfg and new_cfg[k] is not None:
                    current[k] = new_cfg[k]

        if self.config_manager:
            self.config_manager.set("text_mode_config", current)

    def get_font(self, font_key: str, size: int) -> ImageFont.ImageFont:
        cache_key = (font_key, size)
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        font_info = FONTS_REGISTRY.get(font_key, FONTS_REGISTRY["orbitron"])
        fpath = font_info.get("file", "")
        fallback = font_info.get("fallback", "")

        font_obj = None
        if os.path.exists(fpath):
            try:
                font_obj = ImageFont.truetype(fpath, size)
            except Exception:
                pass

        if font_obj is None and os.path.exists(fallback):
            try:
                font_obj = ImageFont.truetype(fallback, size)
            except Exception:
                pass

        if font_obj is None:
            font_obj = ImageFont.load_default()

        self._font_cache[cache_key] = font_obj
        return font_obj

    def _replace_tags(self, text: str, stats: dict = None) -> str:
        """Substitutes dynamic variables like {time}, {date}, {cpu_temp}, etc."""
        if not text:
            return ""
        now = time.localtime()
        res = text.replace("{time}", time.strftime("%H:%M:%S", now))
        res = res.replace("{date}", time.strftime("%Y-%m-%d", now))

        if stats:
            cpu_t = stats.get("cpu_temp", 0)
            gpu_t = stats.get("gpu_temp", 0)
            cpu_l = stats.get("cpu_load", 0)
            gpu_l = stats.get("gpu_load", 0)
            cpu_p = stats.get("cpu_power", 0)
            gpu_p = stats.get("gpu_power", 0)
            ram_l = stats.get("ram_load", 0)
            clock = stats.get("cpu_clock", 0)
            res = res.replace("{cpu_temp}", f"{int(cpu_t)}°C")
            res = res.replace("{gpu_temp}", f"{int(gpu_t)}°C")
            res = res.replace("{cpu_load}", f"{int(cpu_l)}%")
            res = res.replace("{gpu_load}", f"{int(gpu_l)}%")
            res = res.replace("{cpu_power}", f"{int(cpu_p)}W")
            res = res.replace("{gpu_power}", f"{int(gpu_p)}W")
            res = res.replace("{ram_load}", f"{int(ram_l)}%")
            res = res.replace("{fps_1pct}", f"{int(stats.get('fps_1pct', 0))}")
            res = res.replace("{fps}", f"{int(stats.get('fps_avg', 0))}")
            res = res.replace("{cpu_clock}", f"{round(clock/1000.0, 2)}GHz" if clock > 0 else "")
        return res

    def _draw_bg(self, img: Image.Image, draw: ImageDraw.ImageDraw, bg_color: tuple, bg_style: str, t: float):
        """Draws stylized background patterns over the selected bg_color."""
        if bg_style == "solid":
            return

        elif bg_style == "grid":
            grid_r = min(255, bg_color[0] + 20) if bg_color[0] < 128 else max(0, bg_color[0] - 25)
            grid_g = min(255, bg_color[1] + 25) if bg_color[1] < 128 else max(0, bg_color[1] - 25)
            grid_b = min(255, bg_color[2] + 35) if bg_color[2] < 128 else max(0, bg_color[2] - 25)
            grid_color = (grid_r, grid_g, grid_b)
            for x in range(0, WIDTH, 24):
                draw.line([(x, 0), (x, HEIGHT)], fill=grid_color, width=1)
            for y in range(0, HEIGHT, 24):
                draw.line([(0, y), (WIDTH, y)], fill=grid_color, width=1)

        elif bg_style == "scanlines":
            sl_r = max(0, int(bg_color[0] * 0.7) - 5)
            sl_g = max(0, int(bg_color[1] * 0.7) - 5)
            sl_b = max(0, int(bg_color[2] * 0.7) - 5)
            line_color = (sl_r, sl_g, sl_b)
            for y in range(0, HEIGHT, 4):
                draw.line([(0, y), (WIDTH, y)], fill=line_color, width=1)

        elif bg_style == "dots":
            dot_r = min(255, bg_color[0] + 30) if bg_color[0] < 128 else max(0, bg_color[0] - 30)
            dot_g = min(255, bg_color[1] + 30) if bg_color[1] < 128 else max(0, bg_color[1] - 30)
            dot_b = min(255, bg_color[2] + 35) if bg_color[2] < 128 else max(0, bg_color[2] - 30)
            dot_color = (dot_r, dot_g, dot_b)
            for x in range(8, WIDTH, 16):
                for y in range(8, HEIGHT, 16):
                    draw.point((x, y), fill=dot_color)

    def _step_matrix(self, im, draw, speed, t):
        """Simulates falling green matrix digital code drops in background."""
        num_cols = WIDTH // 16
        if self._matrix_drops is None or len(self._matrix_drops) != num_cols:
            self._matrix_drops = [float(np.random.randint(-20, HEIGHT)) for _ in range(num_cols)]

        dt = t - self._last_matrix_update
        if dt > 0.03:
            for c in range(num_cols):
                self._matrix_drops[c] += speed * 6.0
                if self._matrix_drops[c] > HEIGHT + 40:
                    self._matrix_drops[c] = float(np.random.randint(-40, 0))
            self._last_matrix_update = t

        matrix_font = self.get_font("vt323", 16)
        chars = "0123456789ABCDEFΞΨΩЖБ"

        for c, drop_y in enumerate(self._matrix_drops):
            col_x = c * 16 + 4
            for trail_i in range(8):
                ch_y = int(drop_y - trail_i * 14)
                if 0 <= ch_y < HEIGHT:
                    ch = chars[(c * 7 + trail_i + int(t * 10)) % len(chars)]
                    if trail_i == 0:
                        fill = (220, 255, 220)
                    else:
                        brightness = max(15, 220 - trail_i * 28)
                        fill = (0, brightness, 20)
                    draw.text((col_x, ch_y), ch, font=matrix_font, fill=fill)

    def render(self, t: float, orientation: int = 180, stats: dict = None) -> tuple[bytes, Image.Image]:
        """Renders one animation frame at timestamp t. Returns (raw_packet_bytes, preview_pil_img)."""
        cfg = self.get_config()

        bg_rgb = hex_to_rgb(cfg.get("bg_color", "#070A12"))
        bg_style = cfg.get("bg_style", "grid")
        speed = float(cfg.get("speed", 1.0))
        elements = cfg.get("elements", [])

        # Base canvas
        im = Image.new("RGB", (WIDTH, HEIGHT), color=bg_rgb)
        draw = ImageDraw.Draw(im)

        # Check if any element uses matrix_rain
        has_matrix = any(e.get("effect") == "matrix_rain" for e in elements)
        if has_matrix:
            self._step_matrix(im, draw, speed, t)

        # Draw background pattern
        self._draw_bg(im, draw, bg_rgb, bg_style, t)

        # Render each element in sequence
        for elem in elements:
            raw_text = elem.get("text", "")
            if not raw_text:
                continue

            text = self._replace_tags(raw_text, stats)
            if not text:
                continue

            font_key = elem.get("font", "orbitron")
            font_size = max(8, min(72, int(elem.get("font_size", 24))))
            f_obj = self.get_font(font_key, font_size)

            # Measure text
            bbox = draw.textbbox((0, 0), text, font=f_obj)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]

            align = elem.get("align", "center")
            user_x = int(elem.get("x", -1))
            user_y = int(elem.get("y", -1))

            if user_x >= 0:
                x = user_x
            elif align == "left":
                x = 16
            elif align == "right":
                x = WIDTH - tw - 16
            else:
                x = (WIDTH - tw) // 2

            if user_y >= 0:
                y = user_y
            else:
                y = (HEIGHT - th) // 2

            color = hex_to_rgb(elem.get("color", "#00FFCC"))
            glow_color = hex_to_rgb(elem.get("glow_color", "#0077FF"))
            eff = elem.get("effect", "neon_pulse")

            # Render individual effect for this element
            im, draw = self._render_element_effect(
                im, draw, text, f_obj, x, y, tw, th, color, glow_color, eff, speed, t
            )

        preview_img = im.copy()
        final_img = im.rotate(180) if orientation == 180 else im
        raw_rgb565 = frame_to_rgb565(final_img)

        # Format DeepCool frame packet: 13-byte header + 153,600 bytes
        packet = bytearray(13 + len(raw_rgb565))
        packet[0] = 0xAA
        packet[1] = 0x01
        packet[2] = 0x00
        packet[3] = 0x22
        packet[4] = 0x00
        packet[5] = 0x58
        packet[13:] = raw_rgb565

        return bytes(packet), preview_img

    def _render_element_effect(self, im, draw, text, font, x, y, tw, th, color, glow_color, effect, speed, t):
        """Dispatches rendering of an individual text element with its own effect."""

        if effect == "neon_pulse":
            pulse = 0.65 + 0.35 * math.sin(t * speed * 3.2)
            g_r = min(255, int(glow_color[0] * pulse))
            g_g = min(255, int(glow_color[1] * pulse))
            g_b = min(255, int(glow_color[2] * pulse))

            # Halos
            for offset in (3, 2, 1):
                dim_glow = (g_r // (offset + 1), g_g // (offset + 1), g_b // (offset + 1))
                draw.text((x - offset, y), text, font=font, fill=dim_glow)
                draw.text((x + offset, y), text, font=font, fill=dim_glow)
                draw.text((x, y - offset), text, font=font, fill=dim_glow)
                draw.text((x, y + offset), text, font=font, fill=dim_glow)

            draw.text((x, y), text, font=font, fill=color)

        elif effect == "marquee":
            full_banner = f"{text}   ✦   "
            bbox = draw.textbbox((0, 0), full_banner, font=font)
            unit_w = bbox[2] - bbox[0]
            if unit_w <= 0:
                unit_w = 100

            scroll_px = int(t * speed * 75) % unit_w
            start_x = -scroll_px

            cur_x = start_x
            while cur_x < WIDTH + unit_w:
                draw.text((cur_x + 1, y + 1), full_banner, font=font, fill=glow_color)
                draw.text((cur_x, y), full_banner, font=font, fill=color)
                cur_x += unit_w

        elif effect == "rainbow_wave":
            cur_x = x
            for i, ch in enumerate(text):
                hue = (t * speed * 0.45 + i * 0.08) % 1.0
                r, g, b = [int(c * 255) for c in colorsys.hsv_to_rgb(hue, 1.0, 1.0)]

                dim_c = (r // 3, g // 3, b // 3)
                draw.text((cur_x - 1, y), ch, font=font, fill=dim_c)
                draw.text((cur_x + 1, y), ch, font=font, fill=dim_c)
                draw.text((cur_x, y - 1), ch, font=font, fill=dim_c)
                draw.text((cur_x, y + 1), ch, font=font, fill=dim_c)

                draw.text((cur_x, y), ch, font=font, fill=(r, g, b))
                ch_bbox = draw.textbbox((0, 0), ch, font=font)
                cur_x += (ch_bbox[2] - ch_bbox[0])

        elif effect == "matrix_rain":
            pad = 6
            draw.rectangle([(x - pad, y - pad), (x + tw + pad, y + th + pad)], fill=(4, 12, 6))
            draw.rectangle([(x - pad, y - pad), (x + tw + pad, y + th + pad)], outline=glow_color, width=1)
            draw.text((x, y), text, font=font, fill=color)

        elif effect == "glitch":
            glitch_phase = (t * speed) % 1.8
            is_glitching = glitch_phase < 0.25

            offset_r = -3 if is_glitching else -1
            offset_b = 3 if is_glitching else 1
            jitter_y = int(math.sin(t * 50) * 3) if is_glitching else 0

            draw.text((x + offset_r, y + jitter_y), text, font=font, fill=(255, 30, 80))
            draw.text((x + offset_b, y - jitter_y), text, font=font, fill=(0, 220, 255))
            draw.text((x, y), text, font=font, fill=color)

            if is_glitching:
                arr = np.array(im)
                slice_y = max(0, min(HEIGHT - 20, y + np.random.randint(-4, th)))
                slice_h = min(14, HEIGHT - slice_y)
                shift = np.random.randint(-12, 12)
                arr[slice_y:slice_y + slice_h] = np.roll(arr[slice_y:slice_y + slice_h], shift, axis=1)
                im = Image.fromarray(arr)
                draw = ImageDraw.Draw(im)

        elif effect == "typewriter":
            total_len = len(text)
            cycle_dur = (total_len * 0.15 + 2.0) / max(0.2, speed)
            cycle_t = t % cycle_dur

            char_idx = min(total_len, int(cycle_t * 8 * speed))
            displayed_text = text[:char_idx]

            cursor_visible = int(t * 3.5) % 2 == 0
            cursor_char = "█" if cursor_visible else ""

            draw.text((x, y), displayed_text + cursor_char, font=font, fill=color)

        elif effect == "sine_wave":
            cur_x = x
            for i, ch in enumerate(text):
                bounce_y = y + int(math.sin(t * speed * 4.0 + i * 0.55) * 6.0)
                draw.text((cur_x + 1, bounce_y + 1), ch, font=font, fill=glow_color)
                draw.text((cur_x, bounce_y), ch, font=font, fill=color)
                ch_bbox = draw.textbbox((0, 0), ch, font=font)
                cur_x += (ch_bbox[2] - ch_bbox[0])

        else:  # static
            # Shadow
            draw.text((x + 1, y + 1), text, font=font, fill=(glow_color[0]//3, glow_color[1]//3, glow_color[2]//3))
            draw.text((x, y), text, font=font, fill=color)

        return im, draw

    # ---- Export / Bake to Media Library ----

    def bake_to_media(self, media_mgr, duration_sec: float = 4.0, fps: int = 24, name: str = None, stats: dict = None) -> str:
        """Pre-renders current text animation into media library for zero-CPU looping."""
        total_frames = int(duration_sec * fps)
        item_id = f"txt_{str(uuid.uuid4())[:6]}"
        item_dir = os.path.join(media_mgr.storage_dir, item_id)
        os.makedirs(item_dir, exist_ok=True)

        f0_path = os.path.join(item_dir, "frames_0.bin")
        f180_path = os.path.join(item_dir, "frames_180.bin")
        thumb_path = os.path.join(item_dir, "thumb.jpg")

        first_text = "Banner"
        cfg = self.get_config()
        if cfg.get("elements"):
            first_text = cfg["elements"][0].get("text", "Banner")[:14]
        display_name = name or f"Text: {first_text}"

        with open(f0_path, "wb") as f0, open(f180_path, "wb") as f180:
            for i in range(total_frames):
                frame_t = i / fps
                _, img_0 = self.render(frame_t, orientation=0, stats=stats)
                img_180 = img_0.rotate(180)

                raw_0 = frame_to_rgb565(img_0)
                raw_180 = frame_to_rgb565(img_180)

                f0.write(raw_0)
                f180.write(raw_180)

                if i == 0:
                    thumb = img_0.resize((120, 90), Image.Resampling.LANCZOS)
                    thumb.save(thumb_path, "JPEG", quality=85)

        meta = {
            "id": item_id,
            "name": display_name,
            "ext": ".txt",
            "type": "text",
            "frame_count": total_frames,
            "fps": fps,
            "duration_sec": round(duration_sec, 2),
            "created_at": time.time(),
            "thumb": f"/api/media/{item_id}/thumb.jpg"
        }
        with open(os.path.join(item_dir, "meta.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        media_mgr.media_registry[item_id] = meta
        return item_id
