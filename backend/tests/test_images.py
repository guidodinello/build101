from io import BytesIO

import pytest
from PIL import Image

from app.media.images import (
    LIGHT_BACKING,
    POST_SIZE,
    REFERENCE_MAX_SIDE,
    add_logo,
    fit_logo,
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


def transparent_logo(size: tuple[int, int], mark: tuple[int, int], color: str) -> bytes:
    """A PNG of `size`, transparent but for a centered frame of `mark` size in `color`.

    A frame, not a solid block: like letters, a real logo has transparent pixels inside it.
    """
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    left, top = (size[0] - mark[0]) // 2, (size[1] - mark[1]) // 2
    image.paste(Image.new("RGBA", mark, color), (left, top))
    hole = (mark[0] // 2, mark[1] // 2)
    if all(hole):
        image.paste(
            Image.new("RGBA", hole, (0, 0, 0, 0)),
            (left + (mark[0] - hole[0]) // 2, top + (mark[1] - hole[1]) // 2),
        )
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def pixel(data: bytes, xy: tuple[int, int]) -> tuple[int, int, int]:
    with Image.open(BytesIO(data)) as image:
        return image.convert("RGB").getpixel(xy)


def near(color: tuple[int, int, int], expected: tuple[int, int, int], tolerance: int = 24) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(color, expected, strict=True))


def test_the_logo_lands_in_the_bottom_right_corner_and_nothing_else_changes() -> None:
    post = to_post_image(make_image((1080, 1350), color="white"))

    result = add_logo(post, make_image((300, 120), color="#dc0000", format="PNG"))

    assert image_size(result) == POST_SIZE
    assert image_mime(result) == "image/jpeg"
    assert near(pixel(result, (1080 - 60, 1350 - 60)), (220, 0, 0))
    assert near(pixel(result, (60, 60)), (255, 255, 255))
    assert near(pixel(result, (540, 1350 - 60)), (255, 255, 255))


def test_a_logo_fits_its_corner_box_keeping_its_shape() -> None:
    wide = fit_logo(make_image((1000, 100), format="PNG"), POST_SIZE)
    tall = fit_logo(make_image((100, 1000), format="PNG"), POST_SIZE)

    assert wide.size == (238, 24)
    assert tall.size == (12, 122)


def test_a_logo_loses_its_transparent_margins() -> None:
    fitted = fit_logo(transparent_logo((400, 400), (200, 100), "black"), POST_SIZE)

    assert fitted.size == (238, 119)


def test_a_dark_transparent_logo_on_a_dark_photo_gets_a_light_backing() -> None:
    post = to_post_image(make_image((1080, 1350), color="#202020"))
    logo = transparent_logo((240, 120), (200, 100), "#000000")

    result = add_logo(post, logo)

    # Just inside the margin, where the backing starts: the backing, not the photo.
    margin = round(1080 * 0.04)
    assert near(pixel(result, (1080 - margin - 4, 1350 - margin - 30)), LIGHT_BACKING, 48)
    assert near(pixel(result, (1080 - margin + 4, 1350 - margin - 30)), (32, 32, 32))


def test_a_dark_transparent_logo_on_a_light_photo_gets_no_backing() -> None:
    post = to_post_image(make_image((1080, 1350), color="white"))
    logo = transparent_logo((240, 120), (200, 100), "#000000")

    result = add_logo(post, logo)

    fitted = fit_logo(logo, POST_SIZE)
    margin = round(1080 * 0.04)
    just_left = (1080 - margin - fitted.width - 6, 1350 - margin - fitted.height // 2)
    assert near(pixel(result, just_left), (255, 255, 255))


def test_a_fully_transparent_logo_is_rejected() -> None:
    with pytest.raises(ValueError, match="transparent"):
        fit_logo(transparent_logo((100, 100), (0, 0), "black"), POST_SIZE)
