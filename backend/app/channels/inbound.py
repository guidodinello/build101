import asyncio
import logging
import time
from collections import OrderedDict
from datetime import timedelta
from typing import Protocol, runtime_checkable

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import InboundDelivery
from app.ratelimit import MAX_TRACKED_KEYS, RateLimiter

from .base import ChannelError, ChannelPort, InboundMessage

logger = logging.getLogger(__name__)

DEDUPE_MAX_KEYS = 10_000
# Kept longer than the replay window (an hour): a body can't come back as "new" while it is fresh.
DEDUPE_RETENTION = timedelta(hours=48)
DEDUPE_PRUNE_EVERY_S = 3600.0


@runtime_checkable
class DedupeStore(Protocol):
    async def first_seen(self, key: str) -> bool:
        """Atomically record `key`; True if it was not seen before."""
        ...


@runtime_checkable
class InboundHandler(Protocol):
    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None: ...


class InMemoryDedupeStore:
    """Remembers the last `max_keys` keys: the no-database mode, where a restart forgets them."""

    def __init__(self, max_keys: int = DEDUPE_MAX_KEYS) -> None:
        self._max_keys = max_keys
        self._keys: OrderedDict[str, None] = OrderedDict()
        self._lock = asyncio.Lock()

    async def first_seen(self, key: str) -> bool:
        async with self._lock:
            if key in self._keys:
                return False
            self._keys[key] = None
            if len(self._keys) > self._max_keys:
                self._keys.popitem(last=False)
            return True


class DbDedupeStore:
    """`INSERT ... ON CONFLICT DO NOTHING` on `inbound_deliveries`: survives a restart (#105).

    Rows older than `DEDUPE_RETENTION` are deleted, at most once per `DEDUPE_PRUNE_EVERY_S`, so
    the table stays small without a job.
    """

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        retention: timedelta = DEDUPE_RETENTION,
        prune_every_s: float = DEDUPE_PRUNE_EVERY_S,
    ) -> None:
        self._sessions = sessions
        self._retention = retention
        self._prune_every_s = prune_every_s
        self._last_prune: float | None = None

    async def first_seen(self, key: str) -> bool:
        async with self._sessions() as db:
            inserted = await db.scalar(
                insert(InboundDelivery)
                .values(external_id=key)
                .on_conflict_do_nothing()
                .returning(InboundDelivery.external_id)
            )
            await db.commit()
        await self._prune_if_due()
        return inserted is not None

    async def _prune_if_due(self) -> None:
        now = time.monotonic()
        if self._last_prune is not None and now - self._last_prune < self._prune_every_s:
            return
        self._last_prune = now
        async with self._sessions() as db:
            await db.execute(
                delete(InboundDelivery).where(
                    InboundDelivery.received_at < func.now() - self._retention
                )
            )
            await db.commit()


class RateLimitedHandler:
    """A token bucket per sender in front of the handler (#106): no turn over the limit reaches
    the LLM. The Owner is told once per throttled stretch, so a flood doesn't earn a flood of
    replies. An album announcement is free: each photo arrives as a message of its own."""

    def __init__(
        self,
        inner: InboundHandler,
        limiter: RateLimiter,
        notice: str,
        max_keys: int = MAX_TRACKED_KEYS,
    ) -> None:
        self._inner = inner
        self._limiter = limiter
        self._notice = notice
        self._max_keys = max_keys
        self._notified: OrderedDict[str, None] = OrderedDict()

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        if message.kind == "album" or self._limiter.take(message.sender):
            self._notified.pop(message.sender, None)
            await self._inner.handle(message, channel)
            return
        logger.warning(
            "rate limit hit by %s, dropping %s", mask(message.sender), message.message_id
        )
        if message.sender in self._notified:
            return
        self._notified[message.sender] = None
        if len(self._notified) > self._max_keys:
            self._notified.popitem(last=False)
        try:
            await channel.send_text(message.sender, self._notice)
        except ChannelError:
            logger.warning("rate limit notice failed for %s", mask(message.sender), exc_info=True)


class EchoHandler:
    """Placeholder until the conversation router (T23): echoes and describes what arrived."""

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        logger.info(
            "inbound %s id=%s from=%s", message.kind, message.message_id, mask(message.sender)
        )
        try:
            await channel.mark_read(message.message_id, typing=True)
        except ChannelError:
            logger.warning("mark_read failed for %s", message.message_id, exc_info=True)
        await channel.send_text(message.sender, describe(message))


def describe(message: InboundMessage) -> str:
    match message.kind:
        case "text":
            return f"Recibí: {message.text}"
        case "button" if message.button:
            return f'Tocaste "{message.button.title}" ({message.button.id})'
        case "image":
            caption = f" ({message.text})" if message.text else ""
            return f"Recibí una foto{caption}"
        case "audio" if message.audio and message.audio.provider_transcript:
            return f'Recibí un audio: "{message.audio.provider_transcript}"'
        case "audio":
            return "Recibí un audio sin transcripción"
        case _:
            return "Recibí un mensaje que todavía no sé leer"


def mask(phone: str) -> str:
    return f"***{phone[-4:]}"
