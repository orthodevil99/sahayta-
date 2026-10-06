"""Photo storage + perceptual hashing.

Uploads land under ``SAHAYTA_MEDIA_DIR`` (git-ignored) and are served at
``/media/...``. Duplicate-photo detection uses a 64-bit difference hash
(dHash) computed with Pillow — perceptual, so re-uploads of the same photo
match even after re-encoding. Falls back to SHA-256 when the image cannot be
decoded (hash is then exact-match only, still stored honestly).
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path

from PIL import Image

log = logging.getLogger("sahayta.media")

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
EXT_BY_TYPE = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}

# Magic-byte signatures, checked IN ADDITION to the Content-Type header.
# Format validation only — NOT content moderation (see docs/safety.md).
_MAGIC = {
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
}


def sniff_ok(data: bytes, content_type: str) -> bool:
    """True when the file's magic bytes match the claimed image type."""
    if content_type == "image/webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    sigs = _MAGIC.get(content_type)
    return bool(sigs) and any(data.startswith(s) for s in sigs)


def dhash_hex(image_bytes: bytes) -> str | None:
    """64-bit difference hash as 16 hex chars; None if undecodable."""
    try:
        with Image.open(__import__("io").BytesIO(image_bytes)) as img:
            img = img.convert("L").resize((9, 8), Image.LANCZOS)
            px = list(img.getdata())
            bits = 0
            for y in range(8):
                for x in range(8):
                    bits = (bits << 1) | (
                        1 if px[y * 9 + x] > px[y * 9 + x + 1] else 0
                    )
            return f"{bits:016x}"
    except Exception as exc:  # noqa: BLE001 — undecodable bytes are normal input
        log.debug("dhash failed, will use sha256: %s", exc)
        return None


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_photo(
    data: bytes, content_type: str, media_root: Path, subdir: str = "sos"
) -> tuple[str, str, str | None]:
    """Persist photo bytes. Returns (photo_id, public_url, photo_hash).

    photo_hash is the dHash when decodable, else ``sha256:<hex>`` (the prefix
    marks exact-match-only semantics honestly).
    """
    photo_id = str(uuid.uuid4())
    ext = EXT_BY_TYPE.get(content_type, ".bin")
    target_dir = media_root / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{photo_id}{ext}"
    (target_dir / filename).write_bytes(data)

    dhash = dhash_hex(data)
    photo_hash = dhash if dhash else f"sha256:{sha256_hex(data)}"
    return photo_id, f"/media/{subdir}/{filename}", photo_hash
