import asyncio
import logging
import time
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.brand_strategist import BrandInputs, write_brand_brain
from app.agents.schemas import BrandBrain
from app.conversation.events import BrandSummaryReady
from app.db.models import BrandAsset, BrandBrainVersion, Business, Job
from app.knowledge.db import active_products, latest_brand_brain
from app.onboarding.state import (
    OnboardingState,
    brand_brain_written,
    resume_after_failed_revision,
)

from .queue import enqueue, requeue
from .runner import JobContext

logger = logging.getLogger(__name__)

# Flow 3 targets the summary within 60 s of the form; the Instagram import and the photo
# analyses run first, in parallel.
ANALYSES_WAIT_S = 60.0
INPUT_JOBS = ("analyze_asset", "import_instagram")
ANALYSES_POLL_S = 2.0


async def generate_brand(context: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    """Brand Strategist → new Brand Brain version → `brand_summary` with its buttons (Flow 3).

    `payload["correction"]` (the Owner's words after "Corregir algo", or an `update_brand`
    change) runs revise mode on the latest version.
    """
    if context.business_id is None:
        raise ValueError("generate_brand needs a business")
    try:
        return await _generate_brand(context, context.business_id, payload.get("correction"))
    except Exception:
        await resume_revision(context.sessions, context.business_id)
        raise


async def _generate_brand(
    context: JobContext, business_id: uuid.UUID, correction: str | None
) -> dict[str, Any]:
    await _wait_for_analyses(context, business_id)

    async with context.sessions() as db:
        business = await db.get_one(Business, business_id)
        previous = await latest_brand_brain(db, business_id)
        inputs = await _inputs(db, business, previous if correction else None, correction)

    brain = await write_brand_brain(context.model, inputs)

    async with context.sessions() as db:
        business = await db.get_one(Business, business_id)
        version = (
            await db.scalar(
                select(func.max(BrandBrainVersion.version)).where(
                    BrandBrainVersion.business_id == business_id
                )
            )
            or 0
        ) + 1
        db.add(
            BrandBrainVersion(
                business_id=business_id,
                version=version,
                data=brain.model_dump(),
                reason="correction" if correction else "onboarding",
            )
        )
        brand_brain_written(business)
        await db.commit()
        owner_phone, channel_kind, name = business.owner_phone, business.channel, business.name

    if channel_kind == "whatsapp":
        # A failed delivery fails the job, so the Owner is told and can retry (`JobFailed`).
        event = BrandSummaryReady(name or brain.business_name, brain.whatsapp_summary)
        await context.notify(owner_phone, event, context.channel)
    return {"version": version}


async def resume_revision(
    sessions: async_sessionmaker[AsyncSession], business_id: uuid.UUID
) -> None:
    """A failed revision of a confirmed brand puts the Business back where it was (ADR 0030)."""
    async with sessions() as db:
        business = await db.get_one(Business, business_id, with_for_update=True)
        if resume_after_failed_revision(business):
            await db.commit()


async def queue_stranded_brands(sessions: async_sessionmaker[AsyncSession]) -> int:
    """A brand job for each Business stuck generating its brand with nothing left to finish it.

    One whose last brand job is queued or running waits for it, and one whose last brand job
    failed with Reintentar sent waits for the Owner. Any other gets a copy of its last brand job,
    or a first one: a restart interrupted its job before the runner requeued interrupted jobs, or
    the Owner was never told it failed (#178). The runner runs this once, when it starts.
    """
    queued = 0
    async with sessions() as db:
        stuck = (
            await db.scalars(
                select(Business)
                .where(Business.onboarding_state == OnboardingState.GENERATING_BRAND)
                # Whoever holds a lock on one (a route, another instance's check) moves it on.
                # NO KEY: a Reintentar tap's new job checks its foreign key with a KEY SHARE lock
                # on the Business, so FOR UPDATE would deadlock with the wait for its job below.
                .with_for_update(skip_locked=True, key_share=True)
            )
        ).all()
        for business in stuck:
            # Locked like a Reintentar tap locks it, so the two can't both queue a copy.
            last = await db.scalar(
                select(Job)
                .where(Job.business_id == business.id, Job.kind == "generate_brand")
                .order_by(Job.created_at.desc())
                .limit(1)
                .with_for_update()
            )
            if last is None:
                enqueue(db, "generate_brand", business.id, {})
            elif _is_stranded(last):
                requeue(db, last)
            else:
                continue
            queued += 1
        await db.commit()
    if queued:
        logger.warning("queued %d brand jobs for Businesses stuck generating their brand", queued)
    return queued


def _is_stranded(job: Job) -> bool:
    """Neither queued nor running, and no Reintentar sent or tapped: nothing will run it again."""
    return (
        job.status in ("succeeded", "failed")
        and job.retry_offered_at is None
        and not (job.result or {}).get("retried_by")
    )


async def _wait_for_analyses(context: JobContext, business_id: uuid.UUID) -> None:
    """Give the import and the photo analyses time to finish; then go on without them.

    The import queues its photos' analyses as it finishes, so the wait covers those too.
    """
    deadline = time.monotonic() + ANALYSES_WAIT_S
    while True:
        async with context.sessions() as db:
            pending = await db.scalar(
                select(func.count()).where(
                    Job.business_id == business_id,
                    Job.kind.in_(INPUT_JOBS),
                    Job.status.in_(("queued", "running")),
                )
            )
        if not pending:
            return
        if time.monotonic() >= deadline:
            logger.warning("brand for %s goes on with %d input jobs pending", business_id, pending)
            return
        await asyncio.sleep(ANALYSES_POLL_S)


async def _inputs(
    db: AsyncSession, business: Business, previous: BrandBrain | None, correction: str | None
) -> BrandInputs:
    products = await active_products(db, business.id)
    assets = (
        await db.scalars(
            select(BrandAsset)
            .where(
                BrandAsset.business_id == business.id,
                BrandAsset.status == "ready",
                BrandAsset.archived_at.is_(None),
            )
            .order_by(BrandAsset.created_at)
        )
    ).all()
    logo = next((asset for asset in reversed(assets) if asset.kind == "logo"), None)
    brand = business.onboarding_data.get("brand", {})
    return BrandInputs(
        business={
            "name": business.name,
            "category": business.category,
            "one_liner": business.one_liner,
            "description": business.description,
            "location": business.location,
            "website": business.website,
            "instagram_handle": business.instagram_handle,
        },
        catalog=[
            {
                "id": str(product.id),
                "name": product.name,
                "description": product.description,
                "price": product.price,
            }
            for product in products
        ],
        questionnaire=business.onboarding_data.get("preferences") or {},
        brand_words=brand.get("three_words", []),
        colors=[] if brand.get("no_brand_yet") else brand.get("colors", []),
        logo_palette=(logo.palette or []) if logo else [],
        logo_asset_id=str(logo.id) if logo else None,
        photo_descriptions=[
            asset.analysis["description"]
            for asset in assets
            if asset.kind == "photo" and asset.analysis
        ],
        instagram=business.onboarding_data.get("instagram"),
        previous=previous,
        correction=correction,
    )
