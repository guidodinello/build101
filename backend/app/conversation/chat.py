import logging

from sqlalchemy.exc import SQLAlchemyError

from app.channels.base import ChannelPort, InboundMessage
from app.channels.inbound import mark_read, mask
from app.copy import messages_es

from .button_router import ButtonRouter
from .events import (
    AudioUnclear,
    Event,
    PhotosReceived,
    StaleButton,
    UnsupportedMedia,
)
from .history import History
from .photo_batches import PhotoBatches
from .photos import Photo
from .turns import Turns, request

logger = logging.getLogger(__name__)


class ChatHandler:
    """InboundHandler that answers text, voice notes and photos with the LLM.

    It routes each kind of message and holds the sender's lock while it is answered. Photos wait
    in `PhotoBatches` and are answered together, with any text that arrives meanwhile. Buttons and
    other kinds are answered as events (`Turns.notify`, ADR 0026).
    """

    def __init__(
        self, turns: Turns, batches: PhotoBatches, buttons: ButtonRouter, history: History
    ) -> None:
        self._turns = turns
        self._batches = batches
        self._buttons = buttons
        self._history = history

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        match message.kind:
            case "album":
                return
            case "image" if message.media:
                await self._batches.arrived(message, message.media, channel, self._answer_batch)
                return
        photos = self._batches.take(message.sender)
        async with self._history.lock(message.sender):
            await mark_read(message.message_id, channel)
            try:
                reply = await self._answer(message, photos, channel)
            except SQLAlchemyError:
                logger.warning("database failed for %s", mask(message.sender), exc_info=True)
                reply = messages_es.REPLY_FAILED
            if reply is not None:
                await channel.send_text(message.sender, reply)

    async def _answer(
        self, message: InboundMessage, photos: list[Photo], channel: ChannelPort
    ) -> str | None:
        """The reply to send, or None when an event turn already answered."""
        match message.kind:
            case "text" if message.text:
                return await self._turns.owner_turn(
                    message.sender,
                    message.message_id,
                    request(photos, message.text),
                    channel,
                    words=message.text,
                    attached=bool(photos),
                )
            case "audio" if message.audio and message.audio.provider_transcript:
                # ADR 0021: a voice note is handled as its transcript. The Gemini fallback
                # transcriber (TranscriberPort) isn't built yet, so no transcript = unclear.
                transcript = f"[audio] {message.audio.provider_transcript}"
                return await self._turns.owner_turn(
                    message.sender,
                    message.message_id,
                    request(photos, transcript),
                    channel,
                    words=message.audio.provider_transcript,
                    attached=bool(photos),
                )
            case "audio":
                event: Event = AudioUnclear()
            case "button" if message.button:
                tapped = await self._buttons.handle(
                    message.sender, message.button.id, channel, self._turns.notify
                )
                if tapped is None:
                    return None
                event = tapped
            case "button":
                event = StaleButton()
            case _:
                event = UnsupportedMedia()
        await self._turns.event_turn(message.sender, event, channel)
        return None

    async def _answer_batch(
        self, sender: str, photos: list[Photo], last_message_id: str, channel: ChannelPort
    ) -> None:
        """A finished photo batch: with captions the model answers them, without it answers the
        photos themselves."""
        async with self._history.lock(sender):
            await mark_read(last_message_id, channel)
            captions = " ".join(photo.caption for photo in photos if photo.caption)
            if captions:
                reply = await self._turns.owner_turn(
                    sender,
                    last_message_id,
                    request(photos, captions),
                    channel,
                    words=captions,
                    attached=True,
                )
                await channel.send_text(sender, reply)
            else:
                event = PhotosReceived(tuple(photo.id for photo in photos))
                await self._turns.event_turn(sender, event, channel, last_message_id)
