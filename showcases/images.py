"""Showcase images: what an upload must be, and the images the Hub keeps from it.

An upload is checked before anything decodes its pixels: its size in bytes, that Pillow
reads its header as one of the allowed formats (judged by the bytes, never the file's name
or declared type), and its dimensions and proportions (read from the header). Then it's
turned upright, scaled down and re-encoded as WebP twice (`process`): the stored files are
always fresh images the Hub made, with no metadata and none of the upload's bytes.

The files go through Django's default storage (the ImageFields on `Showcase`), so moving
them to object storage later is a settings change.
"""

import uuid
from dataclasses import dataclass
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"PNG": "PNG", "JPEG": "JPEG", "WEBP": "WebP"}
MAX_BYTES = 8 * 1024 * 1024
MIN_WIDTH, MIN_HEIGHT = 640, 360
MAX_SIDE = 8000
MAX_RATIO = 4  # neither side more than 4 times the other

MESSAGES = {
    "too_big": "Choose an image of 8 MB or less.",
    "not_an_image": "That file isn't an image the Hub can read. Use PNG, JPEG or WebP.",
    "wrong_format": "Use a PNG, JPEG or WebP image.",
    "too_small": f"Use an image at least {MIN_WIDTH} × {MIN_HEIGHT} pixels.",
    "too_large": f"Use an image no more than {MAX_SIDE} pixels on either side.",
    "bad_ratio": f"Use an image no more than {MAX_RATIO} times as wide as it is tall, or as tall as it is wide.",
}


def _refuse(code: str) -> ValidationError:
    return ValidationError(MESSAGES[code], code=code)


def check(upload) -> None:
    """Raise ValidationError (its code one of MESSAGES') unless `upload` is an allowed image
    of an allowed size. Leaves `upload` at its start."""
    if upload.size > MAX_BYTES:
        raise _refuse("too_big")
    upload.seek(0)
    try:
        with Image.open(upload) as image:  # reads the header only
            kind, (width, height) = image.format, image.size
            image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise _refuse("not_an_image") from None
    finally:
        upload.seek(0)
    if kind not in ALLOWED_FORMATS:
        raise _refuse("wrong_format")
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        raise _refuse("too_small")
    if max(width, height) > MAX_SIDE:
        raise _refuse("too_large")
    if max(width, height) > MAX_RATIO * min(width, height):
        raise _refuse("bad_ratio")


# What the Hub stores: a display copy for the showcase's page and a smaller one for the
# list's cards, both WebP, both scaled down to fit (never up).
DISPLAY_SIDE = 1920  # the page's image is at most 960 px wide on screen: enough for 2x
CARD_SIDE = 800  # a card is at most about 400 px wide: enough for 2x
QUALITY = 85


@dataclass(frozen=True)
class Processed:
    """The two images the Hub keeps from one upload."""

    display: ContentFile
    card: ContentFile


def upload_to(instance, filename: str) -> str:
    """A fresh random name for every display image, so a replaced one is never served from a
    cache."""
    return f"showcases/{uuid.uuid4().hex}.webp"


def card_upload_to(instance, filename: str) -> str:
    """A fresh random name for every card image."""
    return f"showcases/cards/{uuid.uuid4().hex}.webp"


def _webp(image: Image.Image, side: int, name: str) -> ContentFile:
    copy = image.copy()
    copy.thumbnail((side, side), Image.Resampling.LANCZOS)  # shrinks only, keeps proportions
    out = BytesIO()
    copy.save(out, "WEBP", quality=QUALITY, method=4)
    return ContentFile(out.getvalue(), name=name)


def process(upload) -> Processed:
    """The images the Hub stores from `upload`: turned upright (EXIF), scaled down to fit
    DISPLAY_SIDE and CARD_SIDE, and re-encoded as WebP, so no metadata or original bytes are
    kept. Call check() first.

    Decoding happens here, so a file whose header passed but whose pixels don't decode (a
    truncated file) raises ValidationError too.
    """
    upload.seek(0)
    try:
        with Image.open(upload) as opened:
            opened.seek(0)  # an animated WebP keeps its first frame
            image = ImageOps.exif_transpose(opened)
            transparent = image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info
            image = image.convert("RGBA" if transparent else "RGB")
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise _refuse("not_an_image") from None
    finally:
        upload.seek(0)
    return Processed(
        display=_webp(image, DISPLAY_SIDE, "showcase.webp"),
        card=_webp(image, CARD_SIDE, "card.webp"),
    )
