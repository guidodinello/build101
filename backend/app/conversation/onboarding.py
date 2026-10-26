import logging
import time
import uuid
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.background import BackgroundWork
from app.channels.base import ChannelPort, InboundMessage
from app.channels.inbound import InboundHandler, mark_read, mask
from app.copy import messages_es
from app.db.models import BrandAsset, Business
from app.onboarding.links import add_onboarding_link, onboarding_url
from app.onboarding.state import (
    BEFORE_THE_FORM,
    OnboardingState,
    name_received,
    state_of,
    welcome,
)
from app.ratelimit import MAX_TRACKED_KEYS, KeyedLocks, TtlMap

from .photo_batches import PhotoBatches
from .photo_keeper import PhotoKeeper
from .photos import Photo

logger = logging.getLogger(__name__)

MAX_NAME_CHARS = 200
# WhatsApp delivers an album as one message per photo: one welcome or reminder covers them all.
REMINDER_COOLDOWN_S = 30.0
# Both per-sender timestamps matter for seconds (the cooldown, "Hola" + "¿hay alguien?"), so they
# expire; with the cap, a flood of new numbers can't grow them (#106).
STATE_TTL_S = 600.0
# Photos kept per Business before the form is submitted, like the wizard's photo step: a number
# that never finishes onboarding can't fill Storage or run up photo descriptions.
MAX_EARLY_PHOTOS = 15


@dataclass(frozen=True, slots=True)
class EarlyPhotos:
    """What the gate needs to keep photos sent before the form: the database and Storage."""

    batches: PhotoBatches
    keeper: PhotoKeeper
    background: BackgroundWork
    max_kept: int = MAX_EARLY_PHOTOS


class OnboardingGate:
    """Flow 1 before the web form: welcome, the business name, the magic link.

    Plain code, no LLM. Once the form is submitted every message goes to the chat handler.

    With `photos`, a photo sent before the form waits in its batch, is kept as a Brand asset up
    to `max_kept` per Business, and the batch gets one reply.
    """

    def __init__(
        self,
        chat: InboundHandler,
        sessions: async_sessionmaker[AsyncSession],
        frontend_url: str,
        assistant_name: str,
        reminder_cooldown_s: float = REMINDER_COOLDOWN_S,
        *,
        photos: EarlyPhotos | None = None,
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
        self._photos = photos
        # Photos being described and stored: not in `brand_assets` yet, but under the cap.
        self._keeping = Counter[uuid.UUID]()

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        async with self._locks.hold(message.sender):
            if self._photos and message.kind == "image" and message.media:
                try:
                    early = await self._before_the_form(message.sender)
                except SQLAlchemyError:
                    early = False
                if early:
                    await self._photos.batches.arrived(
                        message, message.media, channel, self._answer_photos
                    )
                    return
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

    async def _before_the_form(self, sender: str) -> bool:
        async with self._sessions() as db:
            business = await db.scalar(select(Business).where(Business.owner_phone == sender))
        return business is None or state_of(business) in BEFORE_THE_FORM

    async def _answer_photos(
        self, sender: str, photos: list[Photo], last_message_id: str, channel: ChannelPort
    ) -> None:
        if self._photos is None:  # only `self._photos.batches` calls this
            return
        async with self._locks.hold(sender):
            try:
                reply = await self._kept_reply(sender, photos, self._photos)
            except SQLAlchemyError:
                logger.exception("keeping early photos failed for %s", mask(sender))
                reply = messages_es.REPLY_FAILED
            await mark_read(last_message_id, channel)
            await channel.send_text(sender, reply)

    async def _kept_reply(self, sender: str, photos: list[Photo], early: EarlyPhotos) -> str:
        """Keep what fits under the cap and say so, with what onboarding still needs."""
        count = len(photos)
        async with self._sessions() as db:
            business = await db.scalar(
                select(Business).where(Business.owner_phone == sender).with_for_update()
            )
            if business is None:
                business = Business(owner_phone=sender)
                db.add(business)
                await db.flush()
            kept = await self._room(db, business.id, count, early.max_kept)
            state = state_of(business)
            if state == OnboardingState.NEW:
                welcome(business)
                self._welcomed_at.set(sender, time.time())
                self._last_prompt.set(sender, time.monotonic())
                reply = messages_es.welcome_with_photos(self._assistant_name, count)
            elif state == OnboardingState.AWAITING_NAME:
                self._last_prompt.set(sender, time.monotonic())
                reply = messages_es.photos_kept_ask_name(count)
            elif state == OnboardingState.AWAITING_WEB_FORM and self._prompted_recently(sender):
                reply = messages_es.photos_kept_form(count)
            elif state == OnboardingState.AWAITING_WEB_FORM:
                reply = messages_es.photos_kept_link(count, self._new_link(db, business))
            else:
                # The form was submitted while the batch waited.
                reply = messages_es.photos_kept(count)
            await db.commit()
            business_id = business.id
        self._keeping[business_id] += kept
        for photo in photos[:kept]:
            early.background.start(
                self._keep(early.keeper, sender, business_id, photo),
                f"keeping early photo {photo.id} for {mask(sender)}",
            )
        return reply

    async def _room(
        self, db: AsyncSession, business_id: uuid.UUID, wanted: int, max_kept: int
    ) -> int:
        stored = await db.scalar(
            select(func.count())
            .select_from(BrandAsset)
            .where(
                BrandAsset.business_id == business_id,
                BrandAsset.kind == "photo",
                BrandAsset.source == "whatsapp",
            )
        )
        room = max_kept - (stored or 0) - self._keeping[business_id]
        return max(0, min(wanted, room))

    async def _keep(
        self, keeper: PhotoKeeper, sender: str, business_id: uuid.UUID, photo: Photo
    ) -> None:
        try:
            await keeper.keep(sender, photo)
        finally:
            self._keeping[business_id] -= 1
            if self._keeping[business_id] <= 0:
                del self._keeping[business_id]

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
