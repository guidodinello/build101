import asyncio
import logging
import time
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.brand_strategist import BrandInputs, write_brand_brain
from app.agents.schemas import BrandBrain
from app.channels.base import Button, ChannelPort
from app.conversation.brand import RESUME_STATE
from app.conversation.history import record_note
from app.copy import messages_es
from app.db.models import BrandAsset, BrandBrainVersion, Business, Job, Product

from .runner import JobContext

logger = logging.getLogger(__name__)

# Flow 3 targets the summary within 60 s of the form; the Instagram import and the photo
# analyses run first, in parallel.
ANALYSES_WAIT_S = 60.0
INPUT_JOBS = ("analyze_asset", "import_instagram")
ANALYSES_POLL_S = 2.0
WHATSAPP_BODY_MAX = 1024
BRAND_SUMMARY_NOTE = (
    "[brand summary sent] The Owner got the summary of their brand (<brand_summary_sent>) with "
    "the buttons Sí, es mi marca and Corregir algo."
)


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
        await _resume(context, context.business_id)
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
        business.onboarding_state = "awaiting_brand_confirmation"
        business.conversation_state = {}
        await db.commit()
        owner_phone, channel_kind, name = business.owner_phone, business.channel, business.name

    if channel_kind == "whatsapp":
        await send_brand_summary(context.channel, owner_phone, name or brain.business_name, brain)
        await record_note(context.sessions, business_id, BRAND_SUMMARY_NOTE)
    return {"version": version}


async def _resume(context: JobContext, business_id: uuid.UUID) -> None:
    """A failed revision of a confirmed brand puts the Business back where it was (ADR 0030)."""
    async with context.sessions() as db:
        business = await db.get_one(Business, business_id, with_for_update=True)
        previous = business.conversation_state.get(RESUME_STATE)
        if business.onboarding_state == "generating_brand" and previous:
            business.onboarding_state = previous
            business.conversation_state = {}
            await db.commit()


async def send_brand_summary(
    channel: ChannelPort, owner_phone: str, business_name: str, brain: BrandBrain
) -> None:
    body = messages_es.brand_summary(business_name, brain.whatsapp_summary)
    buttons = [
        Button(id="brand_ok", title=messages_es.BUTTON_BRAND_OK),
        Button(id="brand_fix", title=messages_es.BUTTON_BRAND_FIX),
    ]
    if len(body) <= WHATSAPP_BODY_MAX:
        await channel.send_buttons(owner_phone, body, buttons)
        return
    # A summary over the limit even after the Strategist's retry: text first, then the question.
    await channel.send_text(owner_phone, body.removesuffix("¿Es así?").rstrip())
    await channel.send_buttons(owner_phone, "¿Es así?", buttons)


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


async def latest_brand_brain(db: AsyncSession, business_id: uuid.UUID) -> BrandBrain | None:
    row = await db.scalar(
        select(BrandBrainVersion)
        .where(BrandBrainVersion.business_id == business_id)
        .order_by(BrandBrainVersion.version.desc())
        .limit(1)
    )
    return BrandBrain.model_validate(row.data) if row else None


async def _inputs(
    db: AsyncSession, business: Business, previous: BrandBrain | None, correction: str | None
) -> BrandInputs:
    products = (
        await db.scalars(
            select(Product)
            .where(Product.business_id == business.id, Product.archived_at.is_(None))
            .order_by(Product.position)
        )
    ).all()
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
