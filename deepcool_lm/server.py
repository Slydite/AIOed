"""
FastAPI Local Web Server for DeepCool LM360 Controller.
Serves responsive dashboard, MJPEG live video preview, Text Animation Studio,
and REST APIs on http://localhost:5220.
"""

import asyncio
import io
import json
import logging
import os
import shutil
import tempfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from deepcool_lm.service import DisplayService
from deepcool_lm.text_animator import FONTS_REGISTRY, EFFECTS

logger = logging.getLogger("deepcool_lm.server")


class ModeRequest(BaseModel):
    mode: str


class OrientationRequest(BaseModel):
    orientation: int


class ThemeRequest(BaseModel):
    theme_id: str


class ThemeSlotRequest(BaseModel):
    theme_id: str
    slot_id: str
    metric: str


class TempUnitRequest(BaseModel):
    unit: str


class BrightnessRequest(BaseModel):
    action: str  # "up" or "down"


class BrightnessSetRequest(BaseModel):
    level: int = None
    percent: int = None


class MediaSelectRequest(BaseModel):
    media_id: str


class ReprocessMediaRequest(BaseModel):
    crop_mode: str = "center"
    crop_rect: dict = None
    start_sec: float = 0.0
    end_sec: float = None
    fps: float = None


class TextConfigRequest(BaseModel):
    elements: list = None
    text: str = None
    subtext: str = None
    font: str = None
    font_size: int = None
    sub_font_size: int = None
    text_x: int = None
    subtext_x: int = None
    text_y: int = None
    subtext_y: int = None
    text_align: str = None
    sub_align: str = None
    effect: str = None
    color: str = None
    sub_color: str = None
    glow_color: str = None
    bg_color: str = None
    bg_style: str = None
    speed: float = None


class MediaStorageRequest(BaseModel):
    storage_dir: str
    move_existing: bool = False


class TextBakeRequest(BaseModel):
    name: str = None
    duration_sec: float = 4.0
    fps: int = 24


class AutostartRequest(BaseModel):
    enable: bool


def create_app(service: DisplayService, web_dir: str = "web") -> FastAPI:
    app = FastAPI(title="DeepCool LM360 Dashboard")

    @app.get("/api/status")
    def get_status():
        return service.get_status()

    @app.get("/api/preview.jpg")
    def get_preview():
        jpeg_data = service.get_preview_jpeg()
        return Response(content=jpeg_data, media_type="image/jpeg", headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        })

    @app.get("/api/preview/stream")
    async def stream_preview():
        """MJPEG live stream delivering 25 FPS directly to browser <img> elements."""
        async def frame_generator():
            try:
                while True:
                    jpeg_bytes = service.get_preview_jpeg()
                    chunk = (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n"
                        b"Content-Length: " + str(len(jpeg_bytes)).encode() + b"\r\n\r\n"
                        + jpeg_bytes + b"\r\n"
                    )
                    yield chunk
                    await asyncio.sleep(0.04)
            except asyncio.CancelledError:
                pass

        return StreamingResponse(
            frame_generator(),
            media_type="multipart/x-mixed-replace; boundary=frame",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    @app.post("/api/mode")
    def set_mode(req: ModeRequest):
        if req.mode not in ("monitor", "media", "text", "off"):
            raise HTTPException(status_code=400, detail="Invalid mode")
        service.set_mode(req.mode)
        return {"status": "ok", "mode": req.mode}

    @app.post("/api/orientation")
    def set_orientation(req: OrientationRequest):
        if req.orientation not in (0, 180):
            raise HTTPException(status_code=400, detail="Orientation must be 0 or 180")
        service.set_orientation(req.orientation)
        return {"status": "ok", "orientation": req.orientation}

    @app.post("/api/theme")
    def set_theme(req: ThemeRequest):
        service.set_theme(req.theme_id)
        return {"status": "ok", "theme_id": req.theme_id}

    @app.post("/api/theme/slot")
    def set_theme_slot(req: ThemeSlotRequest):
        service.set_theme_slot(req.theme_id, req.slot_id, req.metric)
        return {"status": "ok"}

    @app.post("/api/temp_unit")
    def set_temp_unit(req: TempUnitRequest):
        service.set_temp_unit(req.unit)
        return {"status": "ok", "unit": req.unit}

    @app.post("/api/brightness")
    def adjust_brightness(req: BrightnessRequest):
        if req.action == "up":
            service.brightness_up()
        elif req.action == "down":
            service.brightness_down()
        else:
            raise HTTPException(status_code=400, detail="Action must be 'up' or 'down'")
        return {
            "status": "ok",
            "brightness": service.usb.brightness_pct,
            "percent": service.usb.brightness_pct
        }

    @app.post("/api/brightness/set")
    def set_brightness(req: BrightnessSetRequest):
        if req.percent is not None:
            pct = req.percent
        elif req.level is not None:
            pct = req.level * 20 if req.level <= 5 else req.level
        else:
            raise HTTPException(status_code=400, detail="Must provide 'percent' (0..100) or 'level'")

        service.set_brightness(pct)
        return {
            "status": "ok",
            "brightness": service.usb.brightness_pct,
            "percent": service.usb.brightness_pct
        }

    # ---- Media API ----

    @app.post("/api/media/select")
    def select_media(req: MediaSelectRequest):
        service.set_media(req.media_id)
        return {"status": "ok", "media_id": req.media_id}

    @app.delete("/api/media/{media_id}")
    def delete_media(media_id: str):
        success = service.media_mgr.delete_media(media_id)
        if not success:
            raise HTTPException(status_code=404, detail="Media not found")
        if service.config.get("active_media_id") == media_id:
            items = service.media_mgr.list_media()
            new_id = items[0]["id"] if items else None
            service.config.set("active_media_id", new_id)
            service.wake()
        return {"status": "ok"}

    @app.post("/api/media/upload")
    async def upload_media(
        file: UploadFile = File(...),
        name: str = Form(None),
        crop_mode: str = Form("center"),
        crop_rect: str = Form(None),
        start_sec: float = Form(0.0),
        end_sec: float = Form(None),
        fps: float = Form(None)
    ):
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in (".gif", ".mp4", ".webm", ".png", ".jpg", ".jpeg"):
            raise HTTPException(status_code=400, detail=f"Unsupported file format: {ext}")

        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp_path = tmp.name
            shutil.copyfileobj(file.file, tmp)

        try:
            rect_dict = None
            if crop_rect:
                try:
                    rect_dict = json.loads(crop_rect)
                except Exception:
                    pass

            display_name = name or os.path.splitext(file.filename)[0]
            item_id = service.media_mgr.import_file(
                tmp_path,
                display_name=display_name,
                crop_mode=crop_mode,
                crop_rect=rect_dict,
                start_sec=start_sec,
                end_sec=end_sec,
                fps=fps
            )
            service.set_media(item_id)
            return {"status": "ok", "item_id": item_id}
        except Exception as e:
            logger.error(f"Error processing media upload: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    @app.get("/api/media/{media_id}/thumb.jpg")
    def get_media_thumb(media_id: str):
        item_dir = os.path.join(service.media_mgr.storage_dir, media_id)
        thumb_path = os.path.join(item_dir, "thumb.jpg")
        if os.path.exists(thumb_path):
            return FileResponse(thumb_path, media_type="image/jpeg")
        raise HTTPException(status_code=404, detail="Thumbnail not found")

    @app.get("/api/media/{media_id}/source")
    def get_media_source(media_id: str):
        src = service.media_mgr.get_source_path(media_id)
        if src and os.path.exists(src):
            ext = os.path.splitext(src)[1].lower()
            mime = "video/mp4" if ext == ".mp4" else ("image/gif" if ext == ".gif" else "application/octet-stream")
            return FileResponse(src, media_type=mime)
        raise HTTPException(status_code=404, detail="Source media not found")

    @app.get("/api/media/{media_id}/probe")
    def probe_media(media_id: str):
        src = service.media_mgr.get_source_path(media_id)
        if not src or not os.path.exists(src):
            raise HTTPException(status_code=404, detail="Source media not found")
        return service.media_mgr.probe_file(src)

    @app.post("/api/media/{media_id}/reprocess")
    def reprocess_media(media_id: str, req: ReprocessMediaRequest):
        try:
            meta = service.media_mgr.reprocess_media(
                media_id,
                crop_mode=req.crop_mode,
                crop_rect=req.crop_rect,
                start_sec=req.start_sec,
                end_sec=req.end_sec,
                fps=req.fps
            )
            if service.config.get("active_media_id") == media_id:
                service.wake()
            return {"status": "ok", "meta": meta}
        except Exception as e:
            logger.error(f"Error reprocessing media {media_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/api/media/storage")
    def get_media_storage():
        return {"storage_dir": service.media_mgr.storage_dir}

    @app.post("/api/media/storage")
    def set_media_storage(req: MediaStorageRequest):
        try:
            res = service.set_media_storage_dir(req.storage_dir, move_existing=req.move_existing)
            return {"status": "ok", **res}
        except Exception as e:
            logger.error(f"Error changing media storage dir: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ---- Text Animation Studio API ----

    @app.get("/api/text/config")
    def get_text_config():
        return {
            "config": service.get_text_config(),
            "available_fonts": [{"id": k, "name": v["name"]} for k, v in FONTS_REGISTRY.items()],
            "available_effects": EFFECTS
        }

    @app.post("/api/text/config")
    def update_text_config(req: TextConfigRequest):
        update_dict = {k: v for k, v in req.dict().items() if v is not None}
        service.set_text_config(update_dict)
        return {"status": "ok", "config": service.get_text_config()}

    @app.post("/api/text/bake")
    def bake_text(req: TextBakeRequest):
        try:
            item_id = service.bake_text(duration_sec=req.duration_sec, fps=req.fps, name=req.name)
            return {"status": "ok", "item_id": item_id}
        except Exception as e:
            logger.error(f"Error baking text animation: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/api/autostart")
    def set_autostart(req: AutostartRequest):
        res = service.config.set_autostart(req.enable)
        return {"status": "ok" if res else "error", "autostart": req.enable}

    # Serve static assets
    abs_assets_dir = os.path.abspath("assets")
    if os.path.exists(abs_assets_dir):
        app.mount("/assets", StaticFiles(directory=abs_assets_dir), name="assets")

    abs_web_dir = os.path.abspath(web_dir)
    if os.path.exists(abs_web_dir):
        app.mount("/static", StaticFiles(directory=abs_web_dir), name="static")

        abs_css_dir = os.path.join(abs_web_dir, "css")
        if os.path.exists(abs_css_dir):
            app.mount("/css", StaticFiles(directory=abs_css_dir), name="css")

        abs_js_dir = os.path.join(abs_web_dir, "js")
        if os.path.exists(abs_js_dir):
            app.mount("/js", StaticFiles(directory=abs_js_dir), name="js")

        @app.get("/", response_class=HTMLResponse)
        def serve_index():
            index_path = os.path.join(abs_web_dir, "index.html")
            if os.path.exists(index_path):
                with open(index_path, "r", encoding="utf-8") as f:
                    return f.read()
            return "<h1>Web UI not found</h1>"

    return app
