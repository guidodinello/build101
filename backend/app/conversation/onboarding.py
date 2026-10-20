import logging
import time

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import ChannelPort, InboundMessage
from app.channels.inbound import InboundHandler, mark_read, mask
from app.copy import messages_es
from app.db.models import Business
from app.onboarding.links import add_onboarding_link, onboarding_url
from app.onboarding.state import (
    BEFORE_THE_FORM,
    OnboardingState,
    name_received,
    state_of,
    welcome,
)
from app.ratelimit import MAX_TRACKED_KEYS, KeyedLocks, TtlMap

logger = logging.getLogger(__name__)

MAX_NAME_CHARS = 200
# WhatsApp delivers an album as one message per photo: one welcome or reminder covers them all.
REMINDER_COOLDOWN_S = 30.0
# Both per-sender timestamps matter for seconds (the cooldown, "Hola" + "¿hay alguien?"), so they
# expire; with the cap, a flood of new numbers can't grow them (#106).
STATE_TTL_S = 600.0


class OnboardingGate:
    """Flow 1 before the web form: welcome, the business name, the magic link.

    Plain code, no LLM. Once the form is submitted every message goes to the chat handler.
    """

    def __init__(
        self,
        chat: InboundHandler,
        sessions: async_sessionmaker[AsyncSession],
        frontend_url: str,
        assistant_name: str,
        reminder_cooldown_s: float = REMINDER_COOLDOWN_S,
    ) -> None:
        self._chat = chat
        self._sessions = sessions
        self._frontend_url = frontend_url
        self._assistant_name = assistant_name
        self._reminder_cooldown_s = reminder_cooldown_s
        ttl_s = max(STATE_TTL_S, reminder_cooldown_s)
        self._locks = KeyedLocks()
        self._welcomed_at = TtlMap[float](ttl_s, MAX_TRACKED_KEYS)
        self._last_prompt = TtlMap[float](ttl_s, MAX_TRACKED_KEYS)

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        async with self._locks.hold(message.sender):
            try:
                reply = await self._onboard(message)
            except SQLAlchemyError:
                logger.exception("onboarding lookup failed for %s", mask(message.sender))
                reply = messages_es.REPLY_FAILED
            if reply:
                await mark_read(message.message_id, channel)
                await channel.send_text(message.sender, reply)
        if reply is None:
            await self._chat.handle(message, channel)

    async def _onboard(self, message: InboundMessage) -> str | None:
        """The reply before the form ("" to stay quiet), or None once the form is submitted."""
        async with self._sessions() as db:
            business = await db.scalar(
                select(Business).where(Business.owner_phone == message.sender).with_for_update()
            )
            if business is None:
                business = Business(owner_phone=message.sender)
                db.add(business)
            state = state_of(business)
            if state not in BEFORE_THE_FORM:
                return None
            if message.kind == "album":
                return ""

            name = business_name(message)
            if state == OnboardingState.NEW:
                welcome(business)
                self._welcomed_at.set(message.sender, time.time())
                reply = self._welcome(message.sender)
            elif state == OnboardingState.AWAITING_NAME and self._written_before_welcome(message):
                return ""
            elif state == OnboardingState.AWAITING_NAME and name is not None:
                business.name = name
                name_received(business)
                reply = messages_es.name_ack_link(name, self._new_link(db, business))
            elif self._prompted_recently(message.sender):
                return ""
            elif state == OnboardingState.AWAITING_NAME:
                reply = self._welcome(message.sender)
            else:
                reply = messages_es.link_reminder(self._new_link(db, business))
            await db.commit()
        return reply

    def _welcome(self, sender: str) -> str:
        self._last_prompt.set(sender, time.monotonic())
        return messages_es.welcome(self._assistant_name)

    def _new_link(self, db: AsyncSession, business: Business) -> str:
        # Only the token's hash is stored, so a reminder needs a new link.
        self._last_prompt.set(business.owner_phone, time.monotonic())
        return onboarding_url(self._frontend_url, add_onboarding_link(db, business))

    def _written_before_welcome(self, message: InboundMessage) -> bool:
        """ "Hola" + "¿hay alguien?" sent together: the second one isn't the business name."""
        welcomed_at = self._welcomed_at.get(message.sender)
        return (
            welcomed_at is not None
            and message.timestamp is not None
            and message.timestamp <= int(welcomed_at)
        )

    def _prompted_recently(self, sender: str) -> bool:
        last = self._last_prompt.get(sender)
        return last is not None and time.monotonic() - last < self._reminder_cooldown_s


def business_name(message: InboundMessage) -> str | None:
    """The name as the Owner wrote or said it; the wizard's first step lets them fix it."""
    words = message.text if message.kind == "text" else None
    if message.kind == "audio" and message.audio:
        words = message.audio.provider_transcript
    words = (words or "").strip()
    return words[:MAX_NAME_CHARS] or None
