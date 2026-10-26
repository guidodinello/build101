"""WhatsApp photos and carousel references decode as bounded as onboarding uploads (#133)."""

import asyncio
import threading
import time
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest
from PIL import Image

from app.carousel import generator
from app.carousel.generator import CarouselGenerator, prepare_references
from app.carousel.schemas import CarouselBrief, CarouselCopy
from app.conversation.events import PhotoTooLarge, PhotoUnreadable
from app.imagegen.base import GeneratedImage
from app.media import images
from app.media.images import ImageTooLarge, UnreadableImage, decode, prepare_reference
from app.onboarding import uploads
from app.onboarding.uploads import read_upload
from app.posts import maker
from app.posts.maker import with_logo
from tests.conftest import make_image
from tests.fakes import FakeChannel, ScriptedModel, text_reply
from tests.test_chat_handler import EVENT_REPLY, SENDER, build, message, step_text

SIDE = 100
OVER_CAP = (SIDE + 1, SIDE)


def lower_the_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(images, "MAX_PIXELS", SIDE * SIDE)


def never_decoded(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(image: Image.Image) -> bytes:
        raise AssertionError("the photo was decoded")

    monkeypatch.setattr(images, "reference_from", refuse)


def count_decodes(monkeypatch: pytest.MonkeyPatch, *also: tuple[ModuleType, str]) -> dict[str, int]:
    """Slow `reference_from` in both modules, and each `(module, name)` in `also`, counting how
    many run at once."""
    seen = {"running": 0, "peak": 0, "calls": 0}
    lock = threading.Lock()

    def slowed[**P, T](original: Callable[P, T]) -> Callable[P, T]:
        def slow(*args: P.args, **kwargs: P.kwargs) -> T:
            with lock:
                seen["running"] += 1
                seen["calls"] += 1
                seen["peak"] = max(seen["peak"], seen["running"])
            time.sleep(0.05)
            with lock:
                seen["running"] -= 1
            return original(*args, **kwargs)

        return slow

    slow_reference = slowed(images.reference_from)
    monkeypatch.setattr(images, "reference_from", slow_reference)
    monkeypatch.setattr(uploads, "reference_from", slow_reference)  # process_upload binds its own
    for module, name in also:
        monkeypatch.setattr(module, name, slowed(getattr(module, name)))
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
    chat, background = build(model)

    await chat.handler.handle(message("image"), channel)
    await background.join()

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert step_text(model.calls[0][-1]) == PhotoTooLarge().note()
    assert chat.photos.recent(SENDER) == []


async def test_a_whatsapp_decompression_bomb_does_not_fail_the_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    model = ScriptedModel(replies=[text_reply(EVENT_REPLY)])
    channel = FakeChannel(media=make_image((SIDE, SIDE)))
    chat, background = build(model)

    await chat.handler.handle(message("image"), channel)
    await background.join()

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


async def test_a_post_render_and_uploads_share_the_decode_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = count_decodes(monkeypatch, (maker, "add_logo"))
    data = make_image((SIDE, 80))
    logo = make_image((40, 40), format="PNG")

    await asyncio.gather(
        with_logo([data] * 3, logo),
        *(read_upload(data, "image/jpeg", "photo") for _ in range(3)),
    )

    assert seen["calls"] == 6
    assert seen["peak"] == images.MAX_CONCURRENT_DECODES == 2


SCENE = make_image((SIDE, 125))


class InstantImageGen:
    """Every scene at once, so the slides' decodes all want a slot together."""

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        style_image: bytes | None = None,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> GeneratedImage:
        await asyncio.sleep(0)
        return GeneratedImage(data=SCENE, mime="image/jpeg", provider="fake", model=None, usage={})


async def test_a_carousel_and_uploads_share_the_decode_limit(
    monkeypatch: pytest.MonkeyPatch, carousel_spec: tuple[CarouselCopy, CarouselBrief]
) -> None:
    copy, brief = carousel_spec
    seen = count_decodes(monkeypatch, (generator, "to_post_image"))
    data = make_image((SIDE, 80))

    slides, *_ = await asyncio.gather(
        CarouselGenerator(InstantImageGen()).generate(copy, brief, [data]),
        *(read_upload(data, "image/jpeg", "photo") for _ in range(3)),
    )

    assert len(slides) == len(copy.slides)
    assert seen["peak"] == images.MAX_CONCURRENT_DECODES == 2


APP = Path(__file__).resolve().parent.parent / "app"
# The only threads started outside `decode`: `decode` itself, the upload reader that takes the
# same slot, and the mock video's file read (no image decode).
OWN_THREADS = {"media/images.py", "onboarding/uploads.py", "videogen/mock.py"}


def test_image_work_starts_threads_only_through_the_decode_limit() -> None:
    threaded = {
        path.relative_to(APP).as_posix()
        for path in APP.rglob("*.py")
        if "asyncio.to_thread(" in path.read_text()
    }

    assert threaded == OWN_THREADS
