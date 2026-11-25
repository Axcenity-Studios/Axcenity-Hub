"""Profile photos: what an upload must be, and the one image the Hub keeps from it.

An upload is checked before anything decodes its pixels: its size in bytes, that Pillow
reads it as one of the allowed formats, and its dimensions (read from the header). Then it's
turned upright (EXIF), cropped to a centred square, scaled to SIZE and re-encoded as WebP, so
the stored file is always a fresh image the Hub made: no metadata, no original bytes.
"""

import uuid
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"PNG": "PNG", "JPEG": "JPEG", "WEBP": "WebP", "GIF": "GIF"}
MAX_BYTES = 2 * 1024 * 1024
MIN_SIDE = 64
MAX_SIDE = 4096
SIZE = 256  # the stored square, enough for 2x screens at the largest size shown (96 px)
QUALITY = 85

TOO_BIG = "Choose an image of 2 MB or less."
NOT_AN_IMAGE = "That file isn't an image the Hub can read. Use PNG, JPEG, WebP or GIF."
WRONG_FORMAT = "Use a PNG, JPEG, WebP or GIF image."
TOO_SMALL = f"Use an image at least {MIN_SIDE} × {MIN_SIDE} pixels."
TOO_LARGE = f"Use an image no more than {MAX_SIDE} pixels on either side."


def upload_to(instance, filename: str) -> str:
    """A fresh random name for every photo, so a new one is never served from a cache."""
    return f"avatars/{uuid.uuid4().hex}.webp"


def check(upload) -> None:
    """Raise ValidationError unless `upload` is an allowed image of an allowed size."""
    if upload.size > MAX_BYTES:
        raise ValidationError(TOO_BIG, code="too_big")
    upload.seek(0)
    try:
        with Image.open(upload) as image:  # reads the header only
            kind, (width, height) = image.format, image.size
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise ValidationError(NOT_AN_IMAGE, code="not_an_image") from None
    finally:
        upload.seek(0)
    if kind not in ALLOWED_FORMATS:
        raise ValidationError(WRONG_FORMAT, code="wrong_format")
    if min(width, height) < MIN_SIDE:
        raise ValidationError(TOO_SMALL, code="too_small")
    if max(width, height) > MAX_SIDE:
        raise ValidationError(TOO_LARGE, code="too_large")


def process(upload) -> ContentFile:
    """The stored photo: upright, a centred square of SIZE pixels, as WebP. Call check() first.

    Decoding happens here, so a file whose header passed but whose pixels don't decode
    (truncated, an unsupported mode) raises ValidationError too.
    """
    upload.seek(0)
    try:
        with Image.open(upload) as image:
            image.seek(0)  # an animated GIF or WebP keeps its first frame
            image = ImageOps.exif_transpose(image)
            transparent = image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info
            square = ImageOps.fit(
                image.convert("RGBA" if transparent else "RGB"),
                (SIZE, SIZE),
                Image.Resampling.LANCZOS,
            )
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise ValidationError(NOT_AN_IMAGE, code="not_an_image") from None
    finally:
        upload.seek(0)
    out = BytesIO()
    square.save(out, "WEBP", quality=QUALITY, method=6)
    return ContentFile(out.getvalue(), name="avatar.webp")
