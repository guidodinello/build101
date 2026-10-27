import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import timedelta
from typing import Protocol, runtime_checkable

from sqlalchemy import delete, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.background import BackgroundWork
from app.db.models import InboundDelivery
from app.ratelimit import ALBUM_BURST, ALBUM_PER_MINUTE, MAX_TRACKED_KEYS, RateLimiter

from .base import ChannelError, ChannelPort, InboundMessage

logger = logging.getLogger(__name__)

DEDUPE_MAX_KEYS = 10_000
# Kept longer than the replay window (an hour): a body can't come back as "new" while it is fresh.
DEDUPE_RETENTION = timedelta(hours=48)
DEDUPE_PRUNE_EVERY_S = 3600.0
# A failed prune is tried again this soon, not a whole interval later.
DEDUPE_PRUNE_RETRY_S = 60.0


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


async def mark_read(message_id: str, channel: ChannelPort, *, typing: bool = True) -> None:
    """Mark a message read; show typing for normal turns, and only log failures."""
    try:
        await channel.mark_read(message_id, typing=typing)
    except ChannelError:
        logger.warning("mark_read failed for %s", message_id, exc_info=True)


class DbDedupeStore:
    """`INSERT ... ON CONFLICT DO NOTHING` on `inbound_deliveries`: survives a restart (#105).

    Rows older than `DEDUPE_RETENTION` are deleted by a background task, at most once per
    `DEDUPE_PRUNE_EVERY_S` and never two at a time, so the table stays small without a job and
    the webhook request does no DELETE. A failed prune is logged and tried again after
    `DEDUPE_PRUNE_RETRY_S`; it can't fail `first_seen`, whose id is already committed.
    """

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        background: BackgroundWork,
        retention: timedelta = DEDUPE_RETENTION,
        prune_every_s: float = DEDUPE_PRUNE_EVERY_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sessions = sessions
        self._background = background
        self._retention = retention
        self._prune_every_s = prune_every_s
        self._clock = clock
        self._next_prune_at = float("-inf")
        # The running prune, to keep it to one at a time.
        self._prune_task: asyncio.Task[None] | None = None

    async def first_seen(self, key: str) -> bool:
        async with self._sessions() as db:
            inserted = await db.scalar(
                insert(InboundDelivery)
                .values(external_id=key)
                .on_conflict_do_nothing()
                .returning(InboundDelivery.external_id)
            )
            await db.commit()
        self._prune_if_due()
        return inserted is not None

    def _prune_if_due(self) -> None:
        if self._prune_task is not None and not self._prune_task.done():
            return
        if self._clock() < self._next_prune_at:
            return
        self._prune_task = self._background.start(self._prune(), "inbound dedupe prune")

    async def _prune(self) -> None:
        delay = self._prune_every_s
        try:
            async with self._sessions() as db:
                await db.execute(
                    delete(InboundDelivery).where(
                        InboundDelivery.received_at < func.now() - self._retention
                    )
                )
                await db.commit()
        except SQLAlchemyError:
            logger.warning("pruning inbound_deliveries failed", exc_info=True)
            delay = min(delay, DEDUPE_PRUNE_RETRY_S)
        self._next_prune_at = self._clock() + delay


class RateLimitedHandler:
    """A token bucket per sender in front of the handler (#106): no turn over the limit reaches
    the LLM. The Owner is told once per throttled stretch, so a flood doesn't earn a flood of
    replies.

    An album announcement costs no turn (each photo arrives as a message of its own) and doesn't
    end a throttled stretch, but it has a small bucket of its own: over it, the announcement is
    dropped silently, so albums can't be used to flood the handler or to reset the notice.
    """

    def __init__(
        self,
        inner: InboundHandler,
        limiter: RateLimiter,
        notice: str,
        max_keys: int = MAX_TRACKED_KEYS,
        albums: RateLimiter | None = None,
    ) -> None:
        self._inner = inner
        self._limiter = limiter
        self._albums = (
            albums if albums is not None else RateLimiter(ALBUM_BURST, ALBUM_PER_MINUTE, max_keys)
        )
        self._notice = notice
        self._max_keys = max_keys
        self._notified: OrderedDict[str, None] = OrderedDict()

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        if message.kind == "album":
            if self._albums.take(message.sender):
                await self._inner.handle(message, channel)
            else:
                logger.debug("album limit hit by %s", mask(message.sender))
            return
        if self._limiter.take(message.sender):
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
        if message.kind == "reaction":
            await mark_read(message.message_id, channel, typing=False)
            return
        logger.info(
            "inbound %s id=%s from=%s", message.kind, message.message_id, mask(message.sender)
        )
        await mark_read(message.message_id, channel)
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


def phone_digits(phone: str) -> str:
    """A WhatsApp number as digits only: "+598 99 123 456" and "59899123456" are one number."""
    return "".join(char for char in phone if char.isdigit())
