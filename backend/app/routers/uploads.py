"""Media router — POST /api/media (Wave 2 amendment, issue #2).

Mints a photo_id for uploads so POST /api/assess (photo_id) and task
proof photos (proof_photo_id) have something to reference.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from .. import schemas as S
from ..auth import Identity, require_identity
from ..config import Settings, get_settings
from ..database import get_session
from ..media import ALLOWED_CONTENT_TYPES, sniff_ok, store_photo
from ..models import MediaFile

log = logging.getLogger("sahayta.routers.media")

router = APIRouter(prefix="/api", tags=["media"])


@router.post("/media", status_code=201, summary="Upload a photo, mint a photo_id")
async def upload_media(
    photo: UploadFile = File(...),
    identity: Identity = Depends(require_identity),
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> S.MediaUploadResponse:
    content_type = photo.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=422, detail="photo must be jpeg/png/webp")
    data = await photo.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail="photo too large")
    if not data:
        raise HTTPException(status_code=422, detail="empty file")
    if not sniff_ok(data, content_type):
        # Header claims an image type but the bytes don't match — reject.
        # Logged (not flagged): this is usually a broken client, not abuse.
        log.warning("upload magic-byte mismatch: claimed %s", content_type)
        raise HTTPException(
            status_code=422,
            detail="file bytes do not match the claimed image type",
        )

    photo_id, url, photo_hash = store_photo(data, content_type, settings.media_path, "sos")
    session.add(
        MediaFile(
            id=photo_id, url=url, photo_hash=photo_hash,
            content_type=content_type, size_bytes=len(data),
            uploaded_by=identity.device_id,
        )
    )
    await session.commit()
    return S.MediaUploadResponse(photo_id=photo_id, url=url, photo_hash=photo_hash)
