"""The brand summary and WhatsApp's 24 h window (#204).

WhatsApp takes free-form messages only within 24 h of the Owner's last message; outside it a send
is accepted and fails later, unseen. So a summary goes out only inside the window, and otherwise
waits, unsent (`brand_brains.summary_sent_at` empty), for the Owner's next message, which opens
the window again. Until it goes out, nothing tells the orchestrator the Owner saw it.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.schemas import BrandBrain
from app.channels.base import ChannelPort
from app.channels.inbound import mask
from app.db.models import BrandBrainVersion, Business
from app.knowledge.db import latest_brand_version
from app.onboarding.state import OnboardingState, state_of

from .events import BrandSummaryReady, Notify

logger = logging.getLogger(__name__)

WHATSAPP_WINDOW = timedelta(hours=24)


def window_open(last_inbound_at: datetime | None, now: datetime) -> bool:
    """Whether a free-form message can still reach the Owner; never, when they never wrote."""
    return last_inbound_at is not None and now - last_inbound_at < WHATSAPP_WINDOW


async def latest_summary_pending(db: AsyncSession, business: Business) -> bool:
    """The latest summary hasn't gone out, and the Business still waits for the Owner's answer."""
    if state_of(business) != OnboardingState.AWAITING_BRAND_CONFIRMATION:
        return False
    version = await latest_brand_version(db, business.id)
    return version is not None and version.summary_sent_at is None


async def send_pending_summary(
    sessions: async_sessionmaker[AsyncSession],
    business_id: uuid.UUID,
    notify: Notify,
    channel: ChannelPort,
) -> bool:
    """Send the latest summary with its buttons if it hasn't gone out; True when it went out now.

    The version is marked sent before the send, under its row lock, so two callers (the brand job
    and the Owner's next message) can't both send it; a send that fails clears the mark again.
    """
    async with sessions() as db:
        version = await db.scalar(
            select(BrandBrainVersion)
            .where(BrandBrainVersion.business_id == business_id)
            .order_by(BrandBrainVersion.version.desc())
            .limit(1)
            .with_for_update()
        )
        business = await db.get_one(Business, business_id)
        if (
            version is None
            or version.summary_sent_at is not None
            or state_of(business) != OnboardingState.AWAITING_BRAND_CONFIRMATION
        ):
            return False
        version.summary_sent_at = datetime.now(UTC)
        await db.commit()
        owner_phone, name = business.owner_phone, business.name
    brain = BrandBrain.model_validate(version.data)
    event = BrandSummaryReady(name or brain.business_name, brain.whatsapp_summary)
    try:
        await notify(owner_phone, event, channel)
    except Exception:
        # Whatever failed (the history, the send), the summary waits for the Owner's next message.
        logger.warning(
            "brand summary for %s not sent; it waits for the next message",
            mask(owner_phone),
            exc_info=True,
        )
        async with sessions() as db:
            await db.execute(
                update(BrandBrainVersion)
                .where(BrandBrainVersion.id == version.id)
                .values(summary_sent_at=None)
            )
            await db.commit()
        return False
    return True
