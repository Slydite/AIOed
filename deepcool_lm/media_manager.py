"""
Media Manager for DeepCool LM360 LCD.
Pre-decodes GIFs, MP4s, and Images into pre-baked RGB565 binary frames (153,600 bytes per frame).
Provides 0% CPU streaming during playback with zero runtime decoding.
Includes FFmpeg-powered video cropping, trimming, letterboxing, and frame-rate conversion.
"""

import json
import logging
import os
import shutil
import subprocess
import time
import uuid
import numpy as np
from PIL import Image

logger = logging.getLogger("deepcool_lm.media")

TARGET_WIDTH = 320
TARGET_HEIGHT = 240
FRAME_BYTES = TARGET_WIDTH * TARGET_HEIGHT * 2  # 153,600


def frame_to_rgb565(img_rgb: Image.Image) -> bytes:
    """Fast conversion from PIL RGB Image (320x240) to RGB565 little-endian bytes."""
    arr = np.asarray(img_rgb)
    r = (arr[:, :, 0] >> 3).astype(np.uint16)
    g = (arr[:, :, 1] >> 2).astype(np.uint16)
    b = (arr[:, :, 2] >> 3).astype(np.uint16)
    rgb565 = (r << 11) | (g << 5) | b
    return rgb565.tobytes()


class FrameStreamer:
    """Reads pre-baked RGB565 frames directly from disk cache with zero decoding."""

    def __init__(self, bin_path: str, frame_count: int, fps: float):
        self.bin_path = bin_path
        self.frame_count = max(1, frame_count)
        self.fps = max(1.0, min(60.0, fps))
        self._data = None

        if os.path.exists(bin_path):
            file_size = os.path.getsize(bin_path)
            # If reasonably small (< 80MB), cache in RAM for instantaneous slicing
            if file_size < 80 * 1024 * 1024:
                try:
                    with open(bin_path, "rb") as f:
                        self._data = f.read()
                except Exception as e:
                    logger.warning(f"Could not load {bin_path} into memory: {e}")

    def get_frame(self, index: int) -> bytes:
        idx = index % self.frame_count
        offset = idx * FRAME_BYTES

        if self._data is not None:
            return self._data[offset:offset + FRAME_BYTES]

        try:
            with open(self.bin_path, "rb") as f:
                f.seek(offset)
                chunk = f.read(FRAME_BYTES)
                if len(chunk) == FRAME_BYTES:
                    return chunk
        except Exception as e:
            logger.debug(f"Error reading frame {idx}: {e}")

        return bytes(FRAME_BYTES)

    def close(self):
        self._data = None


class MediaManager:
    """Manages imported media, pre-decoding, thumbnail generation, cropping, and caching."""

    def __init__(self, storage_dir: str = "media_store"):
        self.storage_dir = os.path.abspath(storage_dir)
        os.makedirs(self.storage_dir, exist_ok=True)
        self.media_registry = {}
        self._load_registry()

    def _load_registry(self):
        self.media_registry.clear()
        if not os.path.exists(self.storage_dir):
            return

        for item_id in os.listdir(self.storage_dir):
            item_dir = os.path.join(self.storage_dir, item_id)
            if not os.path.isdir(item_dir):
                continue
            meta_path = os.path.join(item_dir, "meta.json")
            if os.path.exists(meta_path):
                try:
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    # Check if source video exists
                    source_candidates = [f for f in os.listdir(item_dir) if f.startswith("source.")]
                    meta["has_source"] = len(source_candidates) > 0
                    if meta["has_source"]:
                        meta["source_url"] = f"/api/media/{meta['id']}/source"
                    self.media_registry[meta["id"]] = meta
                except Exception as e:
                    logger.warning(f"Error reading metadata from {meta_path}: {e}")

    def set_storage_dir(self, new_dir: str, move_existing: bool = False) -> dict:
        """Changes the media storage directory and optionally moves existing items."""
        new_path = os.path.abspath(new_dir)
        os.makedirs(new_path, exist_ok=True)

        if move_existing and os.path.exists(self.storage_dir) and new_path != self.storage_dir:
            for item in os.listdir(self.storage_dir):
                src = os.path.join(self.storage_dir, item)
                dst = os.path.join(new_path, item)
                if os.path.isdir(src) and not os.path.exists(dst):
                    try:
                        shutil.move(src, dst)
                    except Exception as e:
                        logger.warning(f"Error moving {src} to {dst}: {e}")

        self.storage_dir = new_path
        self._load_registry()
        return {
            "storage_dir": self.storage_dir,
            "item_count": len(self.media_registry)
        }

    def list_media(self) -> list[dict]:
        """Return list of all available media items."""
        return sorted(self.media_registry.values(), key=lambda x: x.get("created_at", 0), reverse=True)

    def get_media(self, item_id: str) -> dict | None:
        return self.media_registry.get(item_id)

    def get_source_path(self, item_id: str) -> str | None:
        """Find source video/GIF file if saved."""
        item_dir = os.path.join(self.storage_dir, item_id)
        if not os.path.isdir(item_dir):
            return None
        for f in os.listdir(item_dir):
            if f.startswith("source."):
                return os.path.join(item_dir, f)
        return None

    def get_streamer(self, item_id: str, orientation: int = 180) -> FrameStreamer | None:
        meta = self.get_media(item_id)
        if not meta:
            return None

        bin_name = "frames_180.bin" if orientation == 180 else "frames_0.bin"
        bin_path = os.path.join(self.storage_dir, item_id, bin_name)
        if not os.path.exists(bin_path):
            alt_name = "frames_0.bin" if orientation == 180 else "frames_180.bin"
            bin_path = os.path.join(self.storage_dir, item_id, alt_name)

        if not os.path.exists(bin_path):
            return None

        return FrameStreamer(bin_path, meta.get("frame_count", 1), meta.get("fps", 15.0))

    def probe_file(self, file_path: str) -> dict:
        """Probe media dimensions, duration, and FPS using ffprobe."""
        info = {"width": 320, "height": 240, "duration": 0.0, "fps": 24.0}
        try:
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", file_path
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(res.stdout)
            for s in data.get("streams", []):
                if s.get("codec_type") == "video":
                    info["width"] = int(s.get("width", 320))
                    info["height"] = int(s.get("height", 240))
                    r_fps = s.get("r_frame_rate", "24/1")
                    if "/" in r_fps:
                        num, den = r_fps.split("/")
                        if float(den) > 0:
                            info["fps"] = round(float(num) / float(den), 1)
                    break
            dur = data.get("format", {}).get("duration")
            if dur:
                info["duration"] = round(float(dur), 2)
        except Exception as e:
            logger.debug(f"ffprobe probe failed: {e}")
        return info

    def import_file(
        self,
        file_path: str,
        display_name: str = None,
        crop_mode: str = "center",
        crop_rect: dict = None,
        start_sec: float = 0.0,
        end_sec: float = None,
        fps: float = None,
        max_frames: int = 600
    ) -> str:
        """
        Pre-decodes GIF, MP4, WebM, PNG, JPG into pre-baked binary caches.
        Supports center cover 4:3, letterbox fit, stretch, custom crop, and start/end trimming.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        item_id = str(uuid.uuid4())[:8]
        item_dir = os.path.join(self.storage_dir, item_id)
        os.makedirs(item_dir, exist_ok=True)

        ext = os.path.splitext(file_path)[1].lower()
        if not display_name:
            display_name = os.path.splitext(os.path.basename(file_path))[0]

        # Save pristine source file for future re-cropping & scrubbing
        source_dest = os.path.join(item_dir, f"source{ext}")
        shutil.copyfile(file_path, source_dest)

        logger.info(f"Starting pre-decoding for {display_name} ({ext}) with crop_mode={crop_mode}...")

        frames_0_path = os.path.join(item_dir, "frames_0.bin")
        frames_180_path = os.path.join(item_dir, "frames_180.bin")
        thumb_path = os.path.join(item_dir, "thumb.jpg")

        frame_count, final_fps = self._process_media_ffmpeg_or_pil(
            source_dest, ext, frames_0_path, frames_180_path, thumb_path,
            crop_mode=crop_mode, crop_rect=crop_rect,
            start_sec=start_sec, end_sec=end_sec,
            target_fps=fps, max_frames=max_frames
        )

        duration = (frame_count / final_fps) if final_fps > 0 else 1.0

        meta = {
            "id": item_id,
            "name": display_name,
            "ext": ext,
            "type": "video" if ext in (".mp4", ".webm", ".avi", ".mkv", ".mov") else ("gif" if ext == ".gif" else "image"),
            "frame_count": frame_count,
            "fps": round(final_fps, 1),
            "duration_sec": round(duration, 2),
            "created_at": time.time(),
            "thumb": f"/api/media/{item_id}/thumb.jpg",
            "has_source": True,
            "source_url": f"/api/media/{item_id}/source",
            "crop_mode": crop_mode,
            "crop_rect": crop_rect,
            "start_sec": start_sec,
            "end_sec": end_sec
        }

        meta_path = os.path.join(item_dir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        self.media_registry[item_id] = meta
        logger.info(f"Successfully processed '{display_name}' ({frame_count} frames @ {final_fps:.1f} fps).")
        return item_id

    def reprocess_media(
        self,
        item_id: str,
        crop_mode: str = "center",
        crop_rect: dict = None,
        start_sec: float = 0.0,
        end_sec: float = None,
        fps: float = None,
        max_frames: int = 600
    ) -> dict:
        """Re-encodes existing media item with new crop, trim, and fps parameters."""
        meta = self.get_media(item_id)
        if not meta:
            raise KeyError(f"Media {item_id} not found")

        source_path = self.get_source_path(item_id)
        if not source_path or not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file for {item_id} not found")

        item_dir = os.path.join(self.storage_dir, item_id)
        frames_0_path = os.path.join(item_dir, "frames_0.bin")
        frames_180_path = os.path.join(item_dir, "frames_180.bin")
        thumb_path = os.path.join(item_dir, "thumb.jpg")

        frame_count, final_fps = self._process_media_ffmpeg_or_pil(
            source_path, meta["ext"], frames_0_path, frames_180_path, thumb_path,
            crop_mode=crop_mode, crop_rect=crop_rect,
            start_sec=start_sec, end_sec=end_sec,
            target_fps=fps, max_frames=max_frames
        )

        duration = (frame_count / final_fps) if final_fps > 0 else 1.0

        meta.update({
            "frame_count": frame_count,
            "fps": round(final_fps, 1),
            "duration_sec": round(duration, 2),
            "has_source": True,
            "source_url": f"/api/media/{item_id}/source",
            "crop_mode": crop_mode,
            "crop_rect": crop_rect,
            "start_sec": start_sec,
            "end_sec": end_sec
        })

        meta_path = os.path.join(item_dir, "meta.json")
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        self.media_registry[item_id] = meta
        return meta

    def _process_media_ffmpeg_or_pil(
        self,
        file_path: str,
        ext: str,
        f0_path: str,
        f180_path: str,
        thumb_path: str,
        crop_mode: str = "center",
        crop_rect: dict = None,
        start_sec: float = 0.0,
        end_sec: float = None,
        target_fps: float = None,
        max_frames: int = 600
    ) -> tuple[int, float]:
        """Runs FFmpeg pipeline to crop, trim, scale, and generate f0 & f180 bin files."""
        if ext in (".png", ".jpg", ".jpeg", ".bmp", ".webp"):
            return self._process_image(file_path, f0_path, f180_path, thumb_path, crop_mode, crop_rect)

        # Build FFmpeg filter
        filter_parts = []

        if crop_mode == "custom" and crop_rect and crop_rect.get("w") and crop_rect.get("h"):
            cx = int(crop_rect.get("x", 0))
            cy = int(crop_rect.get("y", 0))
            cw = int(crop_rect.get("w", 320))
            ch = int(crop_rect.get("h", 240))
            filter_parts.append(f"crop={cw}:{ch}:{cx}:{cy}")
            filter_parts.append("scale=320:240")
        elif crop_mode == "fit":
            # Letterbox: maintain full video, black padding
            filter_parts.append("scale=320:240:force_original_aspect_ratio=decrease")
            filter_parts.append("pad=320:240:(ow-iw)/2:(oh-ih)/2:black")
        elif crop_mode == "stretch":
            filter_parts.append("scale=320:240")
        else:
            # Default "center": 4:3 cover crop without distortion
            filter_parts.append("crop='if(gt(a,4/3),ih*4/3,iw)':'if(gt(a,4/3),ih,iw*3/4)':(iw-ow)/2:(ih-oh)/2")
            filter_parts.append("scale=320:240")

        # Probe file for native FPS if not specified
        probe = self.probe_file(file_path)
        fps = target_fps or probe.get("fps") or 24.0
        fps = max(5.0, min(60.0, float(fps)))
        filter_parts.append(f"fps={fps}")

        vf_str = ",".join(filter_parts)

        # Build FFmpeg command for simultaneous f0 and f180 binary generation
        cmd = ["ffmpeg"]

        if start_sec and start_sec > 0:
            cmd.extend(["-ss", str(round(start_sec, 3))])
        if end_sec and end_sec > (start_sec or 0):
            cmd.extend(["-to", str(round(end_sec, 3))])

        cmd.extend(["-i", file_path])
        cmd.extend([
            "-filter_complex", f"[0:v]{vf_str},split=2[f0][f180];[f180]vflip,hflip[f180out]",
            "-vframes", str(max_frames),
            "-map", "[f0]", "-pix_fmt", "rgb565le", "-f", "rawvideo", "-y", f0_path,
            "-map", "[f180out]", "-pix_fmt", "rgb565le", "-f", "rawvideo", "-y", f180_path
        ])

        try:
            logger.info(f"Running FFmpeg: {' '.join(cmd)}")
            res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except Exception as e:
            logger.warning(f"FFmpeg pipeline encountered error: {e}. Falling back to Pillow/imageio.")
            if ext == ".gif":
                return self._process_gif(file_path, f0_path, f180_path, thumb_path, max_frames=max_frames)
            else:
                return self._process_video_imageio(file_path, f0_path, f180_path, thumb_path, max_frames=max_frames)

        # Generate thumb from first frame of f0
        if os.path.exists(f0_path) and os.path.getsize(f0_path) >= FRAME_BYTES:
            with open(f0_path, "rb") as f0:
                first_frame_bytes = f0.read(FRAME_BYTES)
            words = np.frombuffer(first_frame_bytes, dtype=np.uint16).reshape((240, 320))
            r = ((words >> 11) & 0x1F) << 3
            g = ((words >> 5) & 0x3F) << 2
            b = (words & 0x1F) << 3
            rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
            thumb_im = Image.fromarray(rgb, "RGB").resize((120, 90), Image.Resampling.LANCZOS)
            thumb_im.save(thumb_path, "JPEG", quality=85)

        total_bytes = os.path.getsize(f0_path) if os.path.exists(f0_path) else 0
        frame_count = max(1, total_bytes // FRAME_BYTES)
        return frame_count, fps

    def _process_image(self, file_path: str, f0_path: str, f180_path: str, thumb_path: str, crop_mode: str = "center", crop_rect: dict = None):
        img = Image.open(file_path).convert("RGB")
        w, h = img.size

        if crop_mode == "custom" and crop_rect:
            cx = max(0, min(w, int(crop_rect.get("x", 0))))
            cy = max(0, min(h, int(crop_rect.get("y", 0))))
            cw = min(w - cx, int(crop_rect.get("w", w)))
            ch = min(h - cy, int(crop_rect.get("h", h)))
            img_cropped = img.crop((cx, cy, cx + cw, cy + ch))
            img_resized = img_cropped.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        elif crop_mode == "fit":
            # Letterbox inside 320x240
            img_resized = Image.new("RGB", (TARGET_WIDTH, TARGET_HEIGHT), (0, 0, 0))
            ratio = min(TARGET_WIDTH / w, TARGET_HEIGHT / h)
            nw, nh = int(w * ratio), int(h * ratio)
            scaled = img.resize((nw, nh), Image.Resampling.LANCZOS)
            img_resized.paste(scaled, ((TARGET_WIDTH - nw) // 2, (TARGET_HEIGHT - nh) // 2))
        elif crop_mode == "stretch":
            img_resized = img.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        else:
            img_resized = self._resize_cover(img)

        thumb = img_resized.resize((120, 90), Image.Resampling.LANCZOS)
        thumb.save(thumb_path, "JPEG", quality=85)

        raw_0 = frame_to_rgb565(img_resized)
        raw_180 = frame_to_rgb565(img_resized.rotate(180))

        with open(f0_path, "wb") as f0, open(f180_path, "wb") as f180:
            f0.write(raw_0)
            f180.write(raw_180)

        return 1, 1.0

    def _process_gif(self, file_path: str, f0_path: str, f180_path: str, thumb_path: str, max_frames: int = 500):
        img = Image.open(file_path)
        frame_count = 0
        durations = []
        try:
            while True:
                dur = img.info.get("duration", 100)
                durations.append(dur if dur > 0 else 100)
                img.seek(img.tell() + 1)
        except EOFError:
            pass

        avg_dur = (sum(durations) / len(durations)) if durations else 100.0
        fps = 1000.0 / avg_dur if avg_dur > 0 else 10.0
        fps = max(1.0, min(60.0, fps))

        img.seek(0)
        first_frame = True

        with open(f0_path, "wb") as f0, open(f180_path, "wb") as f180:
            try:
                while frame_count < max_frames:
                    frame_rgb = img.convert("RGB")
                    frame_resized = self._resize_cover(frame_rgb)

                    if first_frame:
                        thumb = frame_resized.resize((120, 90), Image.Resampling.LANCZOS)
                        thumb.save(thumb_path, "JPEG", quality=85)
                        first_frame = False

                    raw_0 = frame_to_rgb565(frame_resized)
                    raw_180 = frame_to_rgb565(frame_resized.rotate(180))

                    f0.write(raw_0)
                    f180.write(raw_180)
                    frame_count += 1
                    img.seek(img.tell() + 1)
            except EOFError:
                pass

        return frame_count, fps

    def _process_video_imageio(self, file_path: str, f0_path: str, f180_path: str, thumb_path: str, max_frames: int = 600):
        import imageio.v3 as iio
        native_fps = 24.0
        try:
            props = iio.immeta(file_path)
            if "fps" in props and props["fps"] > 0:
                native_fps = float(props["fps"])
        except Exception:
            pass

        fps = max(5.0, min(60.0, native_fps))
        frame_count = 0
        first_frame = True

        with open(f0_path, "wb") as f0, open(f180_path, "wb") as f180:
            try:
                for frame_arr in iio.imiter(file_path):
                    if frame_count >= max_frames:
                        break

                    img_rgb = Image.fromarray(frame_arr).convert("RGB")
                    frame_resized = self._resize_cover(img_rgb)

                    if first_frame:
                        thumb = frame_resized.resize((120, 90), Image.Resampling.LANCZOS)
                        thumb.save(thumb_path, "JPEG", quality=85)
                        first_frame = False

                    raw_0 = frame_to_rgb565(frame_resized)
                    raw_180 = frame_to_rgb565(frame_resized.rotate(180))

                    f0.write(raw_0)
                    f180.write(raw_180)
                    frame_count += 1
            except Exception:
                pass

        return max(1, frame_count), fps

    def _resize_cover(self, img: Image.Image) -> Image.Image:
        """Center crop and resize to exactly 320x240 without distortion."""
        w, h = img.size
        target_ratio = TARGET_WIDTH / TARGET_HEIGHT
        current_ratio = w / h

        if current_ratio > target_ratio:
            new_w = int(h * target_ratio)
            left = (w - new_w) // 2
            img_cropped = img.crop((left, 0, left + new_w, h))
        else:
            new_h = int(w / target_ratio)
            top = (h - new_h) // 2
            img_cropped = img.crop((0, top, w, top + new_h))

        return img_cropped.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)

    def delete_media(self, item_id: str) -> bool:
        if item_id in self.media_registry:
            del self.media_registry[item_id]
            item_dir = os.path.join(self.storage_dir, item_id)
            if os.path.exists(item_dir):
                shutil.rmtree(item_dir, ignore_errors=True)
            return True
        return False

    def auto_import_deepcool_roaming(self, force_refresh: bool = False):
        """Scans user's AppData\\Roaming\\DeepCool media folder and imports uncropped source items."""
        appdata = os.environ.get("APPDATA", "")
        if not appdata:
            return

        dc_media_dir = os.path.join(appdata, "DeepCool", "media", "3690D8FE1974")
        if not os.path.exists(dc_media_dir):
            return

        if force_refresh:
            self.media_registry.clear()
            shutil.rmtree(self.storage_dir, ignore_errors=True)
            os.makedirs(self.storage_dir, exist_ok=True)

        existing_names = {m.get("name") for m in self.media_registry.values()}

        for root, dirs, files in os.walk(dc_media_dir):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext not in (".gif", ".mp4"):
                    continue

                # Skip cropped or thumbnail duplicates if original exists
                if file.startswith("cropped-") or file.startswith("first_"):
                    continue

                full_path = os.path.join(root, file)
                name = os.path.splitext(file)[0]
                if name in existing_names:
                    continue

                try:
                    logger.info(f"Auto-importing discovered media: {file}")
                    self.import_file(full_path, display_name=name)
                    existing_names.add(name)
                except Exception as e:
                    logger.warning(f"Could not auto-import {file}: {e}")
