import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import ChannelError, ChannelPort, InboundMessage
from app.channels.inbound import InboundHandler, mask
from app.db.models import Business, Product
from app.transcription.base import TranscriberPort, TranscriptionError, Vocabulary

logger = logging.getLogger(__name__)

# The Catalog can be long; the names past these are rarely what a voice note is about.
MAX_VOCABULARY_PRODUCTS = 100
BYTES_PER_MB = 1024 * 1024


class VoiceNotes:
    """InboundHandler that transcribes a voice note Kapso sent without a transcript (ADR 0021).

    The transcript takes the place Kapso's would have, so everything behind it (onboarding, the
    chat) reads a voice note the same way whoever transcribed it. A note over `max_audio_mb` is
    marked `too_long` and never sent to the transcriber; a failed or empty transcription leaves
    the note as it came, which the handlers answer as unclear.
    """

    def __init__(
        self,
        inner: InboundHandler,
        transcriber: TranscriberPort,
        max_audio_mb: int,
        sessions: async_sessionmaker[AsyncSession] | None = None,
    ) -> None:
        self._inner = inner
        self._transcriber = transcriber
        self._max_bytes = max_audio_mb * BYTES_PER_MB
        self._sessions = sessions

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        await self._inner.handle(await self._resolved(message, channel), channel)

    async def _resolved(self, message: InboundMessage, channel: ChannelPort) -> InboundMessage:
        audio = message.audio
        if message.kind != "audio" or audio is None or audio.transcript:
            return message
        too_long = message.model_copy(update={"audio": audio.model_copy(update={"too_long": True})})
        if audio.byte_size is not None and audio.byte_size > self._max_bytes:
            return too_long
        try:
            data, _ = await channel.download_media(audio.media_id)
        except ChannelError:
            logger.warning("voice note %s download failed", message.message_id, exc_info=True)
            return message
        if len(data) > self._max_bytes:
            return too_long
        vocabulary = await self._vocabulary(message.sender)
        try:
            text = await self._transcriber.transcribe(data, audio.mime_type, vocabulary)
        except TranscriptionError:
            logger.warning("voice note %s not transcribed", message.message_id, exc_info=True)
            return message
        transcript = text.strip() or None
        return message.model_copy(
            update={"audio": audio.model_copy(update={"transcript": transcript})}
        )

    async def _vocabulary(self, sender: str) -> Vocabulary:
        """The Business name and its Catalog's Product names; none without the database."""
        if self._sessions is None:
            return Vocabulary()
        try:
            async with self._sessions() as db:
                business = await db.scalar(select(Business).where(Business.owner_phone == sender))
                if business is None:
                    return Vocabulary()
                names = await db.scalars(
                    select(Product.name)
                    .where(Product.business_id == business.id, Product.archived_at.is_(None))
                    .order_by(Product.position, Product.created_at)
                    .limit(MAX_VOCABULARY_PRODUCTS)
                )
                return Vocabulary(business.name, tuple(names))
        except SQLAlchemyError:
            # The words only help the spelling: the note is still worth transcribing without them.
            logger.warning("vocabulary lookup failed for %s", mask(sender), exc_info=True)
            return Vocabulary()
