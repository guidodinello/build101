from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Business
from app.jobs.queue import enqueue
from app.onboarding.state import (
    REVISABLE,
    OnboardingState,
    ask_for_brand_correction,
    confirm_brand,
    start_brand_revision,
)


class BrandFlow:
    """The Owner's answer to `brand_summary` on WhatsApp (Flow 3), and later brand changes."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def confirm(self, sender: str) -> bool:
        """`brand_ok`: the Business becomes active. False when it isn't awaiting confirmation."""
        async with self._sessions() as db:
            business = await self._awaiting_confirmation(db, sender)
            if business is None:
                return False
            confirm_brand(business)
            await db.commit()
        return True

    async def ask_for_correction(self, sender: str) -> bool:
        """`brand_fix`: the orchestrator reads the Owner's next message as the correction."""
        async with self._sessions() as db:
            business = await self._awaiting_confirmation(db, sender)
            if business is None:
                return False
            ask_for_brand_correction(business)
            await db.commit()
        return True

    async def revise(self, sender: str, change: str) -> bool:
        """Queue the Brand Strategist's revise mode with the Owner's change (`update_brand`).

        False before the first brand exists or while one is being written.
        """
        async with self._sessions() as db:
            business = await db.scalar(
                select(Business)
                .where(
                    Business.owner_phone == sender,
                    Business.onboarding_state.in_(REVISABLE),
                )
                .with_for_update()
            )
            if business is None:
                return False
            start_brand_revision(business)
            enqueue(db, "generate_brand", business.id, {"correction": change})
            await db.commit()
        return True

    async def _awaiting_confirmation(self, db: AsyncSession, sender: str) -> Business | None:
        return await db.scalar(
            select(Business)
            .where(
                Business.owner_phone == sender,
                Business.onboarding_state == OnboardingState.AWAITING_BRAND_CONFIRMATION,
            )
            .with_for_update()
        )
