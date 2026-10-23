"""The closed pilot (#186): only the team's pilot numbers reach the Agency and the wizard.

The pilot list is `PILOT_SENDERS` plus, with the database, the rows of `pilot_senders`, which the
team edits in the Supabase SQL editor (docs/implementation/setup.md § Pilot numbers). An empty list
lets nobody in with ENV=prod and everyone in elsewhere.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from functools import cache

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import ChannelError, ChannelPort, InboundMessage
from app.channels.inbound import InboundHandler, mark_read, mask, phone_digits
from app.config import Settings, get_settings
from app.db.models import PilotSender
from app.db.session import get_sessionmaker
from app.ratelimit import MAX_TRACKED_KEYS, TtlMap

logger = logging.getLogger(__name__)

# A number added in the SQL editor gets in within this long, with no deploy.
PILOT_LIST_TTL_S = 60.0
# Kapso's plan counts every message sent and received, so a number not on the list that keeps
# writing gets one reply a day, not one per message.
WAITLIST_REPLY_EVERY_S = 24 * 3600.0
# SQLAlchemy doesn't wrap asyncpg's connect failures: an unreachable database (refused, DNS,
# timeout) raises OSError, not SQLAlchemyError.
DATABASE_DOWN = (SQLAlchemyError, OSError)


def configured_numbers(numbers: str) -> frozenset[str]:
    """The numbers of a comma-separated setting, as digits."""
    return frozenset(digits for number in numbers.split(",") if (digits := phone_digits(number)))


class PilotList:
    """Whether a WhatsApp number may onboard, chat and publish.

    A `configured` number gets in without reading the table, so it keeps working while the
    database is down. Any other number needs the table, read at most once per `ttl_s`: when a
    read fails the last list read stands; with none read yet, the error reaches the caller.
    """

    def __init__(
        self,
        configured: frozenset[str],
        sessions: async_sessionmaker[AsyncSession] | None,
        *,
        open_when_empty: bool,
        ttl_s: float = PILOT_LIST_TTL_S,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._configured = configured
        self._sessions = sessions
        self._open_when_empty = open_when_empty
        self._ttl_s = ttl_s
        self._clock = clock
        self._stored: frozenset[str] | None = None
        self._read_at = float("-inf")
        self._lock = asyncio.Lock()

    async def allows(self, phone: str) -> bool:
        digits = phone_digits(phone)
        if digits in self._configured:
            return True
        numbers = await self.numbers()
        if not numbers:
            return self._open_when_empty
        return digits in numbers

    async def numbers(self) -> frozenset[str]:
        if self._sessions is None:
            return self._configured
        async with self._lock:
            if self._stored is None or self._clock() - self._read_at >= self._ttl_s:
                self._stored = await self._read(self._sessions, self._stored)
                self._read_at = self._clock()
            return self._configured | self._stored

    async def log_at_boot(self) -> None:
        """Who gets in, by count: an empty list in production locks every Owner out."""
        try:
            count = len(await self.numbers())
        except DATABASE_DOWN:
            logger.warning("pilot list: pilot_senders could not be read at boot", exc_info=True)
            return
        if count:
            logger.info("pilot list: %d numbers get in", count)
        elif self._open_when_empty:
            logger.info("pilot list is empty: everyone gets in outside production")
        else:
            logger.warning(
                "pilot list is empty with ENV=prod: nobody gets in. Add the pilot numbers to "
                "the pilot_senders table (or PILOT_SENDERS)"
            )

    @staticmethod
    async def _read(
        sessions: async_sessionmaker[AsyncSession], last: frozenset[str] | None
    ) -> frozenset[str]:
        try:
            async with sessions() as db:
                phones = (await db.scalars(select(PilotSender.phone))).all()
        except DATABASE_DOWN:
            if last is None:
                raise
            logger.warning("reading pilot_senders failed, keeping the last list", exc_info=True)
            return last
        return frozenset(phone_digits(phone) for phone in phones)


def build_pilot_list(settings: Settings) -> PilotList:
    return PilotList(
        configured_numbers(settings.pilot_senders),
        get_sessionmaker() if settings.database_url else None,
        open_when_empty=settings.env != "prod",
    )


@cache
def get_pilot_list() -> PilotList:
    return build_pilot_list(get_settings())


class PilotGate:
    """In front of every message (#186): a number not on the pilot list gets the waitlist reply
    and nothing else, whatever it sent and whatever state its Business is in (its data is kept).

    No LLM call, no Business, no link, no job. Nothing about the number is kept but a masked log
    line and, in memory only, that it got the reply, which it gets at most once per
    `reply_every_s`; a reply that fails to send goes out on its next message. Past `max_keys` the
    oldest are forgotten, so a flood of numbers can't grow memory; at worst a forgotten number
    gets a second reply.
    """

    def __init__(
        self,
        inner: InboundHandler,
        pilot: PilotList,
        reply: str,
        reply_every_s: float = WAITLIST_REPLY_EVERY_S,
        max_keys: int = MAX_TRACKED_KEYS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._inner = inner
        self._pilot = pilot
        self._reply = reply
        self._replied = TtlMap[bool](reply_every_s, max_keys, clock)

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        if message.kind == "reaction":
            try:
                allowed = await self._pilot.allows(message.sender)
            except DATABASE_DOWN:
                logger.exception(
                    "pilot list unavailable, dropping reaction from %s", mask(message.sender)
                )
                return
            if allowed:
                await self._inner.handle(message, channel)
            else:
                await mark_read(message.message_id, channel, typing=False)
            return
        try:
            allowed = await self._pilot.allows(message.sender)
        except DATABASE_DOWN:
            logger.exception(
                "pilot list unavailable, dropping %s from %s", message.kind, mask(message.sender)
            )
            return
        if allowed:
            await self._inner.handle(message, channel)
            return
        number = phone_digits(message.sender)
        if self._replied.get(number):
            logger.info("%s from %s dropped: not on the pilot list", message.kind, mask(number))
            return
        # Marked before the send, so a message arriving during it gets no second reply.
        self._replied.set(number, True)
        logger.info("%s from %s: not on the pilot list, waitlist reply", message.kind, mask(number))
        try:
            await channel.send_text(message.sender, self._reply)
        except ChannelError:
            self._replied.delete(number)
            logger.warning("waitlist reply failed for %s", mask(number), exc_info=True)
