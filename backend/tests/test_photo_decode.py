"""WhatsApp photos and carousel references decode as bounded as onboarding uploads (#133)."""

import asyncio
import threading
import time

import pytest
from PIL import Image

from app.carousel.generator import prepare_references
from app.conversation.events import PhotoTooLarge, PhotoUnreadable
from app.media import images
from app.media.images import ImageTooLarge, UnreadableImage, decode, prepare_reference
from app.onboarding import uploads
from app.onboarding.uploads import read_upload
from tests.conftest import make_image
from tests.fakes import FakeChannel, ScriptedModel, text_reply
from tests.test_chat_handler import EVENT_REPLY, SENDER, handler, message, step_text

SIDE = 100
OVER_CAP = (SIDE + 1, SIDE)


def lower_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(images, "MAX_PIXELS", SIDE * SIDE)


def never_decoded(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(image: Image.Image) -> bytes:
        raise AssertionError("the photo was decoded")

    monkeypatch.setattr(images, "reference_from", refuse)


def count_decodes(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Slow `reference_from` in both modules, counting how many run at once."""
    seen = {"running": 0, "peak": 0, "calls": 0}
    lock = threading.Lock()
    original = images.reference_from

    def slow(image: Image.Image) -> bytes:
        with lock:
            seen["running"] += 1
            seen["calls"] += 1
            seen["peak"] = max(seen["peak"], seen["running"])
        time.sleep(0.05)
        with lock:
            seen["running"] -= 1
        return original(image)

    monkeypatch.setattr(images, "reference_from", slow)
    monkeypatch.setattr(uploads, "reference_from", slow)  # process_upload binds its own name
    return seen


def test_a_photo_over_the_pixel_cap_is_refused_before_decoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lower_the_cap(monkeypatch)
    never_decoded(monkeypatch)

    with pytest.raises(ImageTooLarge):
        prepare_reference(make_image(OVER_CAP))


def test_a_photo_at_the_pixel_cap_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    lower_the_cap(monkeypatch)

    assert prepare_reference(make_image((SIDE, SIDE)))


def test_a_decompression_bomb_is_an_unreadable_photo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)  # SIDE x SIDE is over twice that

    with pytest.raises(UnreadableImage) as error:
        prepare_reference(make_image((SIDE, SIDE)))

    assert not isinstance(error.value, ImageTooLarge)


def truncated_heic() -> bytes:
    """A HEIF whose header reads fine but whose data ends early: pillow_heif raises ValueError."""
    data = make_image((400, 300), format="HEIF")
    return data[: len(data) * 9 // 10]


def test_a_truncated_heic_is_an_unreadable_photo() -> None:
    with pytest.raises(UnreadableImage):
        prepare_reference(truncated_heic())


def test_a_truncated_heic_upload_is_unreadable() -> None:
    with pytest.raises(uploads.UnreadableImage):
        uploads.process_upload(truncated_heic(), "image/heic", "photo")


def test_a_file_that_is_not_an_image_is_an_unreadable_photo() -> None:
    with pytest.raises(UnreadableImage):
        prepare_reference(b"not an image")


async def test_a_whatsapp_photo_over_the_cap_gets_a_short_reply(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lower_the_cap(monkeypatch)
    never_decoded(monkeypatch)
    model = ScriptedModel(replies=[text_reply(EVENT_REPLY)])
    channel = FakeChannel(media=make_image(OVER_CAP))
    chat = handler(model)

    await chat.handle(message("image"), channel)
    await chat.join()

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert step_text(model.calls[0][-1]) == PhotoTooLarge().note()
    assert chat._photos.recent(SENDER) == []


async def test_a_whatsapp_decompression_bomb_does_not_fail_the_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    model = ScriptedModel(replies=[text_reply(EVENT_REPLY)])
    channel = FakeChannel(media=make_image((SIDE, SIDE)))
    chat = handler(model)

    await chat.handle(message("image"), channel)
    await chat.join()

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert step_text(model.calls[0][-1]) == PhotoUnreadable().note()


async def test_whatsapp_and_onboarding_decodes_share_one_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = count_decodes(monkeypatch)
    data = make_image((SIDE, 80))

    await asyncio.gather(
        *(read_upload(data, "image/jpeg", "photo") for _ in range(3)),
        *(decode(prepare_reference, data) for _ in range(3)),
    )

    assert seen["calls"] == 6
    assert seen["peak"] == images.MAX_CONCURRENT_DECODES == 2


@pytest.mark.parametrize("onboarding_first", [True, False])
async def test_the_decode_limit_does_not_depend_on_who_asks_first(
    monkeypatch: pytest.MonkeyPatch, onboarding_first: bool
) -> None:
    monkeypatch.setattr(images, "MAX_CONCURRENT_DECODES", 1)
    seen = count_decodes(monkeypatch)
    data = make_image((SIDE, 80))
    uploads_ = [read_upload(data, "image/jpeg", "photo") for _ in range(2)]
    photos = [decode(prepare_reference, data) for _ in range(2)]

    await asyncio.gather(*(uploads_ + photos if onboarding_first else photos + uploads_))

    assert seen["calls"] == 4
    assert seen["peak"] == 1


async def test_the_carousel_references_decode_under_the_same_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = count_decodes(monkeypatch)
    references = [make_image((SIDE, 80)) for _ in range(5)]

    prepared = await prepare_references(references)

    assert len(prepared) == 5
    assert seen["peak"] == 2
