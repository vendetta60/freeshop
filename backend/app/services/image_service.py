"""Upload pipeline: sniff, re-encode, store (plan.md 9.7).

Three rules drive every decision here:

1. **The client's `Content-Type` and filename are claims, not facts.** The
   format is decided by the leading magic bytes and then by whether the
   decoder can actually open the data.
2. **The original bytes are never served.** Everything is decoded and
   re-encoded, which strips EXIF (including GPS), drops any appended payload,
   and makes a polyglot file - a valid image that is also a valid script -
   harmless by construction.
3. **The path is derived server-side** from a content hash, so no part of a
   filename supplied by a caller ever reaches the filesystem. Path traversal
   is not defended against; it is unrepresentable.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger

log = get_logger(__name__)

# Leading bytes -> format name. Sniffed, never trusted from the request.
_MAGIC: tuple[tuple[bytes, str], ...] = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"RIFF", "webp"),  # bytes 8..12 are 'WEBP', checked below
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
)

ACCEPTED = frozenset({"jpeg", "png", "webp", "avif", "heic", "gif"})

# Long edge of the stored image. Product photography beyond this is bandwidth
# nobody sees: the largest rendering surface in the design is a 2x detail
# gallery on a desktop viewport.
MAX_EDGE = 1600
JPEG_QUALITY = 82


@dataclass(frozen=True)
class StoredImage:
    path: str
    width: int
    height: int


def sniff(data: bytes) -> str | None:
    """Format name from the leading bytes, or None if it is not an image."""
    head = data[:32]
    for magic, name in _MAGIC:
        if not head.startswith(magic):
            continue
        if name == "webp":
            return "webp" if head[8:12] == b"WEBP" else None
        return name
    # ISO-BMFF container: 'ftyp' at offset 4, brand tells AVIF from HEIC.
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand in (b"avif", b"avis"):
            return "avif"
        if brand in (b"heic", b"heix", b"hevc", b"mif1", b"msf1"):
            return "heic"
    return None


def _reject(reason: str, **context: object) -> AppError:
    log.info("upload_rejected", reason=reason, **context)
    return AppError(
        ErrorCode.UPLOAD_REJECTED,
        status_code=400,
        field="file",
        details={"reason": reason},
    )


def store(data: bytes, upload_dir: Path, *, max_bytes: int) -> StoredImage:
    """Validate, re-encode and write one upload. Returns the relative path.

    Raises `UPLOAD_REJECTED` with a machine-readable reason for every refusal
    path, so the panel can say *why* rather than "upload failed".
    """
    if not data:
        raise _reject("empty")
    if len(data) > max_bytes:
        raise _reject("too_large", size=len(data), limit=max_bytes)

    fmt = sniff(data)
    if fmt is None:
        raise _reject("not_an_image")
    if fmt not in ACCEPTED:
        raise _reject("unsupported_format", format=fmt)

    try:
        with Image.open(io.BytesIO(data)) as source:
            # A decode bomb is a valid image; the pixel budget is the guard.
            source.verify()
        with Image.open(io.BytesIO(data)) as source:
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        # HEIC in particular sniffs fine and then fails to decode without a
        # plugin. Saying so beats a 500 the operator cannot act on.
        raise _reject("undecodable", format=fmt, error=type(exc).__name__) from exc

    if max(image.size) > MAX_EDGE:
        image.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    # No `exif=` argument, so metadata is dropped rather than copied.
    image.save(buffer, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
    encoded = buffer.getvalue()

    digest = hashlib.sha256(encoded).hexdigest()
    relative = f"products/{digest[:2]}/{digest[:16]}.jpg"
    target = upload_dir / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    # Content-addressed: an identical re-upload is already on disk and the
    # write is a no-op rather than a duplicate file.
    if not target.exists():
        target.write_bytes(encoded)

    return StoredImage(path=relative, width=image.width, height=image.height)
