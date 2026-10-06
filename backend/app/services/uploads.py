"""Image uploads (chat images, avatars, team logos).

Only raster images are accepted. Every image is decoded and re-encoded with Pillow, which strips
metadata (EXIF/GPS) and neutralizes polyglot files. SVG is intentionally not accepted.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Upload
from app.models.enums import UploadKind

ALLOWED_FORMATS = {"PNG", "JPEG", "WEBP", "GIF"}
MAX_EDGE = {UploadKind.CHAT: 1600, UploadKind.AVATAR: 512, UploadKind.LOGO: 512}
Image.MAX_IMAGE_PIXELS = 40_000_000


async def store_image(session: AsyncSession, file: UploadFile, kind: UploadKind, user_id: uuid.UUID | None) -> Upload:
    settings = get_settings()
    limit = settings.max_upload_mb * 1024 * 1024
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"Datei zu groß (max. {settings.max_upload_mb} MB).")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        image = Image.open(io.BytesIO(data))
        if image.format not in ALLOWED_FORMATS:
            raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Nur PNG, JPEG, WebP oder GIF erlaubt.")
        image = ImageOps.exif_transpose(image)
        image.thumbnail((MAX_EDGE[kind], MAX_EDGE[kind]))
        has_alpha = image.mode in ("RGBA", "LA", "P")
        image = image.convert("RGBA" if has_alpha else "RGB")
        out = io.BytesIO()
        image.save(out, format="WEBP", quality=85, method=4)
    except HTTPException:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Die Datei ist kein gültiges Bild.")

    upload_id = uuid.uuid4()
    rel = f"{kind.value.lower()}/{upload_id.hex[:2]}/{upload_id.hex}.webp"
    target = Path(settings.upload_dir) / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(out.getvalue())
    record = Upload(
        id=upload_id,
        kind=kind,
        path=rel,
        content_type="image/webp",
        size_bytes=len(out.getvalue()),
        width=image.width,
        height=image.height,
        uploaded_by=user_id,
    )
    session.add(record)
    await session.flush()
    return record
