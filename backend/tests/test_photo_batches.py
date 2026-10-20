"""`PhotoBatches`: photos sent one by one are answered together, once, after the debounce."""

import asyncio

from app.background import BackgroundWork
from app.channels.base import ChannelPort, InboundMessage
from app.conversation.events import PhotoTooBig, PhotoUnreadable
from app.conversation.photo_batches import PhotoBatches
from app.conversation.photos import InMemoryPhotos, Photo
from tests.fakes import EventLog, FakeChannel
from tests.test_chat_handler import SENDER, message

DEBOUNCE_S = 0.05


class Answers:
    def __init__(self) -> None:
        self.batches: list[tuple[str, list[Photo], str]] = []

    async def __call__(
        self, sender: str, photos: list[Photo], last_message_id: str, channel: ChannelPort
    ) -> None:
        self.batches.append((sender, photos, last_message_id))


def batches(
    max_photo_mb: int = 1,
) -> tuple[PhotoBatches, InMemoryPhotos, EventLog, BackgroundWork]:
    photos, events, background = InMemoryPhotos(), EventLog(), BackgroundWork()
    return (
        PhotoBatches(photos, None, max_photo_mb, events, DEBOUNCE_S, background=background),
        photos,
        events,
        background,
    )


def photo_message(message_id: str) -> InboundMessage:
    return message("image", text=None).model_copy(update={"message_id": message_id})


async def arrive(
    batch: PhotoBatches, incoming: InboundMessage, channel: FakeChannel, answers: Answers
) -> None:
    assert incoming.media is not None
    await batch.arrived(incoming, incoming.media, channel, answers)


async def test_an_album_is_answered_once_with_all_its_photos_after_the_debounce() -> None:
    batch, photos, _, background = batches()
    channel, answers = FakeChannel(), Answers()

    await arrive(batch, photo_message("m1"), channel, answers)
    await arrive(batch, photo_message("m2"), channel, answers)
    assert answers.batches == []  # still waiting for a third photo
    await background.join()

    [(sender, taken, last_message_id)] = answers.batches
    assert (sender, last_message_id) == (SENDER, "m2")
    assert [photo.id for photo in taken] == [photo.id for photo in photos.recent(SENDER)]
    assert len(taken) == 2


async def test_take_hands_the_waiting_photos_over_and_cancels_the_answer() -> None:
    batch, _, _, background = batches()
    channel, answers = FakeChannel(), Answers()
    await arrive(batch, photo_message("m1"), channel, answers)

    taken = batch.take(SENDER)
    await asyncio.sleep(DEBOUNCE_S * 3)
    await background.join()

    assert len(taken) == 1
    assert answers.batches == []
    assert batch.take(SENDER) == []


async def test_a_photo_over_the_limit_is_an_event_and_starts_no_batch() -> None:
    batch, photos, events, background = batches()
    incoming = photo_message("m1")
    assert incoming.media is not None
    big = incoming.model_copy(
        update={"media": incoming.media.model_copy(update={"byte_size": 2 * 1024 * 1024})}
    )
    answers = Answers()

    await arrive(batch, big, FakeChannel(), answers)
    await background.join()

    assert events.events == [(SENDER, PhotoTooBig(1))]
    assert photos.recent(SENDER) == [] and answers.batches == []


async def test_a_photo_that_cannot_be_decoded_is_an_event() -> None:
    batch, _, events, background = batches()
    channel, answers = FakeChannel(media=b"not an image"), Answers()

    await arrive(batch, photo_message("m1"), channel, answers)
    await background.join()

    assert events.events == [(SENDER, PhotoUnreadable())]
    assert answers.batches == []
