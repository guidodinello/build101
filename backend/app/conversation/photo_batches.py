import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.background import BackgroundWork
from app.channels.base import ChannelError, ChannelPort, InboundMedia, InboundMessage
from app.channels.inbound import mask
from app.media.images import ImageTooLarge, UnreadableImage, decode, prepare_reference

from .events import Notify, PhotoTooBig, PhotoTooLarge, PhotoUnreadable
from .photo_keeper import PhotoKeeper
from .photos import InMemoryPhotos, Photo

logger = logging.getLogger(__name__)

BYTES_PER_MB = 1024 * 1024
# WhatsApp delivers an album as one message per photo, 1–4 s apart (seen on 2026-10-17).
PHOTO_DEBOUNCE_S = 5.0

# Answers a finished batch: the sender, its photos, the last message's id, the channel.
AnswerBatch = Callable[[str, list[Photo], str, ChannelPort], Awaitable[None]]


@dataclass(slots=True)
class _Batch:
    photos: list[Photo] = field(default_factory=list)
    last_message_id: str = ""
    timer: asyncio.Task[None] | None = None


class PhotoBatches:
    """Collects the photos an Owner sends one by one and hands them over together.

    A batch waits `debounce_s` after its last photo, then goes to `answer` once; a message of
    another kind that arrives meanwhile `take`s it instead and answers it along with its words.
    Each photo is also kept as a Brand asset in the background (`keeper`, when there is one).
    """

    def __init__(
        self,
        photos: InMemoryPhotos,
        keeper: PhotoKeeper | None,
        max_photo_mb: int,
        notify: Notify,
        debounce_s: float = PHOTO_DEBOUNCE_S,
        *,
        background: BackgroundWork,
    ) -> None:
        self._photos = photos
        self._keeper = keeper
        self._max_photo_mb = max_photo_mb
        self._notify = notify
        self._debounce_s = debounce_s
        self._background = background
        self._batches: dict[str, _Batch] = {}

    async def arrived(
        self,
        message: InboundMessage,
        media: InboundMedia,
        channel: ChannelPort,
        answer: AnswerBatch,
    ) -> None:
        """Read the photo into the sender's batch and restart the wait; too big or unreadable
        photos are an event for the Owner instead."""
        sender = message.sender
        if (media.byte_size or 0) > self._max_photo_mb * BYTES_PER_MB:
            await self._notify(sender, PhotoTooBig(self._max_photo_mb), channel)
            return
        try:
            data, _ = await channel.download_media(media.media_id)
            if len(data) > self._max_photo_mb * BYTES_PER_MB:
                await self._notify(sender, PhotoTooBig(self._max_photo_mb), channel)
                return
            reference = await decode(prepare_reference, data)
        except ImageTooLarge:
            logger.warning("photo %s is over the pixel cap", media.media_id)
            await self._notify(sender, PhotoTooLarge(), channel)
            return
        except (ChannelError, UnreadableImage):
            logger.warning("could not read photo %s", media.media_id, exc_info=True)
            await self._notify(sender, PhotoUnreadable(), channel)
            return
        photo = self._photos.add(sender, reference, message.text)
        if self._keeper:
            self._background.start(
                self._keeper.keep(sender, photo), f"keeping photo {photo.id} for {mask(sender)}"
            )
        batch = self._batches.setdefault(sender, _Batch())
        batch.photos.append(photo)
        batch.last_message_id = message.message_id
        if batch.timer:
            batch.timer.cancel()
        batch.timer = self._background.start(
            self._answer_later(sender, channel, answer), f"answering photos for {mask(sender)}"
        )

    def take(self, sender: str) -> list[Photo]:
        """The sender's waiting photos, no longer waiting (none if there are none)."""
        batch = self._batches.pop(sender, None)
        if batch is None:
            return []
        if batch.timer:
            batch.timer.cancel()
        return batch.photos

    async def _answer_later(self, sender: str, channel: ChannelPort, answer: AnswerBatch) -> None:
        await asyncio.sleep(self._debounce_s)
        # Popped right after the wait: a photo arriving from here on starts a new batch.
        batch = self._batches.pop(sender)
        await answer(sender, batch.photos, batch.last_message_id, channel)
