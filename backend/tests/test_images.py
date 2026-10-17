from io import BytesIO

from PIL import Image

from app.media.images import (
    POST_SIZE,
    REFERENCE_MAX_SIDE,
    image_mime,
    image_size,
    prepare_reference,
    to_post_image,
)
from tests.conftest import make_image

EXIF_ORIENTATION = 0x0112
ROTATED_90_CLOCKWISE = 6


def test_to_post_image_turns_gemini_2k_into_1080x1350_jpeg() -> None:
    result = to_post_image(make_image((1856, 2304), format="PNG"))

    assert image_size(result) == POST_SIZE
    assert image_mime(result) == "image/jpeg"


def test_to_post_image_crops_a_square_to_4_5() -> None:
    assert image_size(to_post_image(make_image((2000, 2000)))) == POST_SIZE


def test_prepare_reference_downscales_large_photos_keeping_aspect() -> None:
    width, height = image_size(prepare_reference(make_image((4000, 3000), format="PNG")))

    assert max(width, height) == REFERENCE_MAX_SIDE
    assert abs(width / height - 4 / 3) < 0.01


def test_prepare_reference_keeps_small_photos_as_they_are() -> None:
    assert image_size(prepare_reference(make_image((800, 600)))) == (800, 600)


def test_prepare_reference_reads_heic_and_returns_jpeg() -> None:
    result = prepare_reference(make_image((640, 480), format="HEIF"))

    assert image_mime(result) == "image/jpeg"
    assert image_size(result) == (640, 480)


def test_prepare_reference_applies_exif_rotation() -> None:
    buffer = BytesIO()
    exif = Image.Exif()
    exif[EXIF_ORIENTATION] = ROTATED_90_CLOCKWISE
    Image.new("RGB", (400, 200)).save(buffer, format="JPEG", exif=exif)

    assert image_size(prepare_reference(buffer.getvalue())) == (200, 400)
