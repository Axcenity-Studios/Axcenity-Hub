"""The media pipeline: responsive derivatives of every captured image in the manifest.

A source image (an unretouched capture, copied in from where it was made) lives in
`marketing/media_sources/`, which is never served. `make_media` writes its
derivatives into `static/marketing/media/<key>/`: every width in `WIDTHS` the
source can supply without upscaling, in AVIF and WebP (offered through
`<picture>`) and JPEG (the fallback every browser reads). The manifest
(`content.MEDIA`) lists them, and the tests check each file's real pixel size.
"""

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from PIL import Image

SOURCES_DIR = settings.BASE_DIR / "marketing" / "media_sources"
OUTPUT_DIR = settings.BASE_DIR / "static" / "marketing" / "media"
# Where the derivatives are served from, under STATIC_URL.
STATIC_PREFIX = "marketing/media"

# The widths every source is cut to (those it's at least as wide as). They cover 1× and 2× of
# every display size: a phone's inline frame, the desktop stage and the hero's fallback.
WIDTHS = (640, 960, 1280, 1920, 2560)


@dataclass(frozen=True)
class Format:
    """One output format: its file extension, MIME type and Pillow save options."""

    extension: str
    mime: str
    pillow: str
    options: tuple[tuple[str, object], ...]


# In the order <picture> offers them; the last is the <img> fallback.
FORMATS = (
    Format("avif", "image/avif", "AVIF", (("quality", 80), ("speed", 4))),
    Format("webp", "image/webp", "WEBP", (("quality", 90), ("method", 6))),
    Format(
        "jpg", "image/jpeg", "JPEG", (("quality", 88), ("optimize", True), ("progressive", True))
    ),
)
FALLBACK = FORMATS[-1]


@dataclass(frozen=True)
class Derivative:
    """One generated file: its static path, format and real pixel size."""

    path: str
    format: Format
    width: int
    height: int


def widths_for(source_width: int) -> tuple[int, ...]:
    """The widths a source this wide is cut to: never wider than the source itself."""
    widths = tuple(width for width in WIDTHS if width <= source_width)
    return widths or (source_width,)


def derivatives(key: str, source_size: tuple[int, int]) -> tuple[Derivative, ...]:
    """Every derivative of the item `key`, by format then width, heights kept in proportion."""
    source_width, source_height = source_size
    return tuple(
        Derivative(
            f"{STATIC_PREFIX}/{key}/{key}-{width}.{fmt.extension}",
            fmt,
            width,
            round(width * source_height / source_width),
        )
        for fmt in FORMATS
        for width in widths_for(source_width)
    )


def build(
    key: str,
    source: str,
    source_size: tuple[int, int],
    *,
    sources_dir: Path = SOURCES_DIR,
    output_dir: Path = OUTPUT_DIR,
    force: bool = False,
) -> list[Path]:
    """Writes the derivatives of one source that are missing or older than it; returns them.

    Refuses a source whose real size isn't `source_size`, so the manifest can't
    drift from the file. Never writes into `sources_dir`.
    """
    source_path = sources_dir / source
    with Image.open(source_path) as image:
        if image.size != tuple(source_size):
            raise ValueError(f"{source}: the manifest says {source_size}, the file is {image.size}")
        picture = image.convert("RGB")  # no alpha or palette: every format takes it as is
    written = []
    for item in derivatives(key, source_size):
        target = output_dir / Path(item.path).relative_to(STATIC_PREFIX)
        if not force and target.exists() and target.stat().st_mtime >= source_path.stat().st_mtime:
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        resized = picture.resize((item.width, item.height), Image.Resampling.LANCZOS)
        resized.save(target, item.format.pillow, **dict(item.format.options))
        written.append(target)
    return written
