"""Showcase images (showcases.images): what an upload must be, and the images the Hub keeps
from it."""

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from showcases import images


def image_file(size=(1280, 720), kind="PNG", name="shot.png", mode="RGB", **save):
    out = BytesIO()
    Image.new(mode, size, "#3366aa").save(out, kind, **save)
    return SimpleUploadedFile(name, out.getvalue(), content_type=f"image/{kind.lower()}")


def padded_png(total: int) -> SimpleUploadedFile:
    """A readable PNG of exactly `total` bytes (junk after its end, which Pillow ignores)."""
    data = image_file().read()
    return SimpleUploadedFile("big.png", data + b"\0" * (total - len(data)), "image/png")


REFUSED = {
    # The wrong type: judged by the bytes, never the name or the declared content type.
    "a GIF": (lambda: image_file(kind="GIF", name="shot.gif"), "wrong_format"),
    "a BMP": (lambda: image_file(kind="BMP", name="shot.bmp"), "wrong_format"),
    "a TIFF named .png": (lambda: image_file(kind="TIFF", name="shot.png"), "wrong_format"),
    "text named .png": (
        lambda: SimpleUploadedFile("shot.png", b"not an image at all", "image/png"),
        "not_an_image",
    ),
    "an SVG": (
        lambda: SimpleUploadedFile(
            "shot.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720"/>',
            "image/svg+xml",
        ),
        "not_an_image",
    ),
    "an empty file": (lambda: SimpleUploadedFile("shot.png", b"", "image/png"), "not_an_image"),
    # Too many bytes, however readable.
    "one byte over the limit": (lambda: padded_png(images.MAX_BYTES + 1), "too_big"),
    # Dimensions out of range.
    "too narrow": (lambda: image_file((images.MIN_WIDTH - 1, 720)), "too_small"),
    "too short": (lambda: image_file((1280, images.MIN_HEIGHT - 1)), "too_small"),
    "too wide a side": (lambda: image_file((images.MAX_SIDE + 1, 2100)), "too_large"),
    "too tall a side": (lambda: image_file((2100, images.MAX_SIDE + 1)), "too_large"),
    "wider than 4:1": (lambda: image_file((4 * 640 + 1, 640)), "bad_ratio"),
    "taller than 4:1": (lambda: image_file((640, 4 * 640 + 1)), "bad_ratio"),
}

ACCEPTED = {
    "the smallest allowed": lambda: image_file((images.MIN_WIDTH, images.MIN_HEIGHT)),
    "exactly 4:1 at the largest side": lambda: image_file((images.MAX_SIDE, images.MAX_SIDE // 4)),
    "exactly 1:4": lambda: image_file((800, 3200)),
    "a JPEG": lambda: image_file(kind="JPEG", name="shot.jpg"),
    "a WebP": lambda: image_file(kind="WEBP", name="shot.webp"),
    "exactly the byte limit": lambda: padded_png(images.MAX_BYTES),
}


@pytest.mark.parametrize("make", ACCEPTED.values(), ids=ACCEPTED.keys())
def test_an_allowed_image_passes_the_check(make):
    upload = make()
    images.check(upload)
    assert upload.tell() == 0  # left ready to be read again


@pytest.mark.parametrize(("make", "code"), REFUSED.values(), ids=REFUSED.keys())
def test_an_upload_of_the_wrong_type_size_or_dimensions_is_refused(make, code):
    upload = make()
    with pytest.raises(ValidationError) as refused:
        images.check(upload)
    assert refused.value.code == code
    assert refused.value.messages == [images.MESSAGES[code]]
    assert upload.tell() == 0
