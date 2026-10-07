"""Image uploads (chat images, avatars, team logos).

Only raster images are accepted. Every image is decoded and re-encoded with Pillow, which strips
metadata (EXIF/GPS) and neutralizes polyglot files. SVG is intentionally not accepted.
"""

from __future__ import annotations

import asyncio
import io
import uuid
import warnings
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Upload
from app.models.enums import UploadKind

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}
MAX_EDGE = {UploadKind.CHAT: 1600, UploadKind.AVATAR: 512, UploadKind.LOGO: 512}
MAX_PIXELS = 16_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS
warnings.simplefilter("error", Image.DecompressionBombWarning)
_decode_slots: dict[int, asyncio.Semaphore] = {}


def _slots() -> asyncio.Semaphore:
    """At most two images are decoded at the same time (per event loop)."""
    loop = id(asyncio.get_running_loop())
    return _decode_slots.setdefault(loop, asyncio.Semaphore(2))


def _reencode(data: bytes, kind: UploadKind) -> tuple[bytes, int, int]:
    """Validate and re-encode an image (CPU heavy – runs in a worker thread)."""
    try:
        with Image.open(io.BytesIO(data)) as probe:
            if probe.format not in ALLOWED_FORMATS:
                raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Nur PNG, JPEG, WebP oder GIF erlaubt.")
            if probe.width * probe.height > MAX_PIXELS:
                raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Bild hat zu viele Pixel.")
            probe.verify()
        image = Image.open(io.BytesIO(data))
        if image.format == "JPEG":
            image.draft("RGB", (MAX_EDGE[kind] * 2, MAX_EDGE[kind] * 2))
        image = ImageOps.exif_transpose(image)
        image.thumbnail((MAX_EDGE[kind], MAX_EDGE[kind]))
        has_alpha = image.mode in ("RGBA", "LA", "P")
        image = image.convert("RGBA" if has_alpha else "RGB")
        out = io.BytesIO()
        image.save(out, format="WEBP", quality=85, method=4)
    except HTTPException:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Die Datei ist kein gültiges Bild.")
    return out.getvalue(), image.width, image.height


async def store_image(session: AsyncSession, file: UploadFile, kind: UploadKind, user_id: uuid.UUID | None) -> Upload:
    settings = get_settings()
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Datei zu groß (max. {settings.max_upload_mb} MB).")
    async with _slots():
        encoded, width, height = await asyncio.to_thread(_reencode, data, kind)

    upload_id = uuid.uuid4()
    rel = f"{kind.value.lower()}/{upload_id.hex[:2]}/{upload_id.hex}.webp"
    target = Path(settings.upload_dir) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded)
    record = Upload(
        id=upload_id,
        kind=kind,
        path=rel,
        content_type="image/webp",
        size_bytes=len(encoded),
        width=width,
        height=height,
        uploaded_by=user_id,
    )
    session.add(record)
    await session.flush()
    return record
