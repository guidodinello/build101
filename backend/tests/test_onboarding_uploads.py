import asyncio
import threading
import time
from io import BytesIO

import pytest
from PIL import Image

from app.media import images
from app.onboarding import uploads
from app.onboarding.uploads import (
    ImageTooLarge,
    ProcessedUpload,
    UnreadableImage,
    asset_path,
    llm_copy_path,
    logo_palette,
    process_upload,
    read_upload,
)
from tests.conftest import make_image


def make_logo() -> bytes:
    image = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    image.paste((47, 62, 44, 255), (0, 0, 120, 100))
    image.paste((200, 155, 109, 255), (120, 0, 200, 100))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def color_distance(a: str, b: str) -> int:
    return max(abs(int(a[i : i + 2], 16) - int(b[i : i + 2], 16)) for i in (1, 3, 5))


def test_photo_gets_its_size_and_a_reduced_jpeg_copy() -> None:
    processed = process_upload(make_image((3000, 2000)), "image/jpeg", "photo")

    assert (processed.width, processed.height) == (3000, 2000)
    with Image.open(BytesIO(processed.llm_copy)) as copy:
        assert copy.format == "JPEG"
        assert max(copy.size) == 1536
    assert processed.jpeg is None
    assert processed.palette is None


def test_heic_is_converted_to_jpeg() -> None:
    processed = process_upload(make_image((400, 300), format="HEIF"), "image/heic", "photo")

    assert processed.jpeg is not None
    with Image.open(BytesIO(processed.jpeg)) as jpeg:
        assert jpeg.format == "JPEG"
        assert jpeg.size == (400, 300)


def test_logo_palette_ignores_the_transparent_background() -> None:
    processed = process_upload(make_logo(), "image/png", "logo")

    assert processed.palette is not None
    assert len(processed.palette) == 2
    for found, expected in zip(processed.palette, ["#2f3e2c", "#c89b6d"], strict=True):
        assert color_distance(found, expected) <= 4


def test_logo_palette_of_a_fully_transparent_image_is_empty() -> None:
    assert logo_palette(Image.new("RGBA", (50, 50), (0, 0, 0, 0))) == []


def test_an_image_over_the_pixel_cap_is_rejected_before_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(uploads, "MAX_PIXELS", 100 * 100)

    with pytest.raises(ImageTooLarge, match="101x100"):
        process_upload(make_image((101, 100)), "image/jpeg", "photo")


def test_a_decompression_bomb_is_unreadable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)

    with pytest.raises(UnreadableImage):
        process_upload(make_image((50, 50)), "image/jpeg", "photo")


def test_unreadable_file_raises() -> None:
    with pytest.raises(UnreadableImage):
        process_upload(b"not an image", "image/jpeg", "photo")


def test_storage_paths() -> None:
    assert asset_path("b1", "a1", "image/heic") == "b1/a1.heic"
    assert llm_copy_path("b1", "a1") == "b1/a1-llm.jpg"


@pytest.mark.parametrize(
    ("format", "content_type"),
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp"), ("HEIF", "image/heic")],
)
def test_every_accepted_format_passes(format: str, content_type: str) -> None:
    processed = process_upload(make_image((120, 80), format=format), content_type, "photo")

    assert (processed.width, processed.height) == (120, 80)


@pytest.mark.parametrize("format", ["TIFF", "BMP", "GIF"])
def test_a_file_of_another_format_is_unreadable_whatever_it_declares(format: str) -> None:
    with pytest.raises(UnreadableImage):
        process_upload(make_image((50, 50), format=format), "image/png", "photo")


def test_a_file_must_match_its_declared_type() -> None:
    with pytest.raises(UnreadableImage):
        process_upload(make_image((50, 50), format="PNG"), "image/jpeg", "photo")


def test_the_pixel_cap_is_25_megapixels() -> None:
    assert uploads.MAX_PIXELS == 25_000_000


async def test_decodes_run_at_most_as_many_at_once_as_the_limit_allows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(images, "MAX_CONCURRENT_DECODES", 2)
    running = 0
    peak = 0
    lock = threading.Lock()
    reference_from = uploads.reference_from

    def slow_reference(image: Image.Image) -> bytes:
        nonlocal running, peak
        with lock:
            running += 1
            peak = max(peak, running)
        time.sleep(0.05)
        with lock:
            running -= 1
        return reference_from(image)

    monkeypatch.setattr(uploads, "reference_from", slow_reference)
    data = make_image((100, 80))

    await asyncio.gather(*(read_upload(data, "image/jpeg", "photo") for _ in range(6)))

    assert peak == 2


async def test_decodes_waiting_for_a_slot_leave_the_thread_pool_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Waiting happens on the event loop: one decode runs in a thread, the rest hold none."""
    monkeypatch.setattr(images, "MAX_CONCURRENT_DECODES", 1)
    in_threads = 0
    peak = 0
    lock = threading.Lock()
    process = uploads.process_upload

    def counting(data: bytes, content_type: str, kind: str) -> ProcessedUpload:
        nonlocal in_threads, peak
        with lock:
            in_threads += 1
            peak = max(peak, in_threads)
        try:
            time.sleep(0.05)
            return process(data, content_type, kind)
        finally:
            with lock:
                in_threads -= 1

    monkeypatch.setattr(uploads, "process_upload", counting)
    data = make_image((100, 80))

    await asyncio.gather(*(read_upload(data, "image/jpeg", "photo") for _ in range(5)))

    assert peak == 1
