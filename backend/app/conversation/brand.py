from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Business
from app.jobs.queue import enqueue

AWAITING_CORRECTION = "brand_correction"


class BrandFlow:
    """The Owner's answer to `brand_summary` on WhatsApp (Flow 3): confirm it, or correct it."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def confirm(self, sender: str) -> bool:
        """`brand_ok`: the Business becomes active. False when it isn't awaiting confirmation."""
        async with self._sessions() as db:
            business = await self._awaiting_confirmation(db, sender)
            if business is None:
                return False
            business.onboarding_state = "active"
            business.conversation_state = {}
            await db.commit()
        return True

    async def ask_for_correction(self, sender: str) -> bool:
        """`brand_fix`: the Owner's next message is the correction."""
        async with self._sessions() as db:
            business = await self._awaiting_confirmation(db, sender)
            if business is None:
                return False
            business.conversation_state = {"awaiting": AWAITING_CORRECTION}
            await db.commit()
        return True

    async def take_correction(self, sender: str, text: str) -> bool:
        """When a correction was asked for, queue the Brand Strategist's revise mode with it."""
        async with self._sessions() as db:
            business = await self._awaiting_confirmation(db, sender)
            if business is None or business.conversation_state.get("awaiting") != (
                AWAITING_CORRECTION
            ):
                return False
            business.conversation_state = {}
            # Back to generating: the old summary's buttons go stale until the new one arrives.
            business.onboarding_state = "generating_brand"
            enqueue(db, "generate_brand", business.id, {"correction": text})
            await db.commit()
        return True

    async def _awaiting_confirmation(self, db: AsyncSession, sender: str) -> Business | None:
        return await db.scalar(
            select(Business)
            .where(
                Business.owner_phone == sender,
                Business.onboarding_state == "awaiting_brand_confirmation",
            )
            .with_for_update()
        )
