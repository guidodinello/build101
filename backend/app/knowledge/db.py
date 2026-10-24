"""The database adapter of `Knowledge`, and the readers it is built from."""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.data.niches import CURATED_WOOD_FURNITURE_UY, Niche
from app.agents.niche_analyst import NicheReport, trend_notes
from app.agents.schemas import BrandBrain
from app.channels.inbound import mask
from app.db.models import (
    AssetProduct,
    BrandBrainVersion,
    Business,
    NicheReportRow,
    OwnerNote,
    Product,
)
from app.onboarding.state import awaiting, state_of

from .base import BusinessFacts, BusinessKnowledge, CatalogItem, Note, short_id

logger = logging.getLogger(__name__)

MAX_PRODUCTS = 30
PRODUCT_DESCRIPTION_CHARS = 200


async def business_of(db: AsyncSession, sender: str) -> Business | None:
    """The Business whose Owner has this phone: the one place that looks it up."""
    return await db.scalar(select(Business).where(Business.owner_phone == sender))


async def active_products(
    db: AsyncSession, business_id: uuid.UUID, limit: int | None = None
) -> list[Product]:
    """The Catalog: the Business's products that are not archived, in the Owner's order."""
    query = (
        select(Product)
        .where(Product.business_id == business_id, Product.archived_at.is_(None))
        .order_by(Product.position)
    )
    if limit is not None:
        query = query.limit(limit)
    return list((await db.scalars(query)).all())


async def latest_brand_brain(db: AsyncSession, business_id: uuid.UUID) -> BrandBrain | None:
    row = await db.scalar(
        select(BrandBrainVersion)
        .where(BrandBrainVersion.business_id == business_id)
        .order_by(BrandBrainVersion.version.desc())
        .limit(1)
    )
    return BrandBrain.model_validate(row.data) if row else None


def niche_of(business: Business) -> Niche:
    """The Business's niche. Nothing records it yet (no wizard field, no classifier), and the
    MVP serves one vertical (mvp.md), so every Business is in curated wood furniture."""
    return CURATED_WOOD_FURNITURE_UY


async def latest_niche_report(db: AsyncSession, niche_id: str) -> NicheReport | None:
    row = await db.scalar(
        select(NicheReportRow)
        .where(NicheReportRow.niche_id == niche_id)
        .order_by(NicheReportRow.week_start.desc())
        .limit(1)
    )
    return NicheReport.model_validate(row.report) if row else None


async def latest_trend_notes(db: AsyncSession, business: Business) -> str | None:
    """The trend notes of the Business's niche, from its latest report; None before the first."""
    report = await latest_niche_report(db, niche_of(business).id)
    return trend_notes(report) if report else None


class DbKnowledge:
    """Knowledge read fresh from Postgres on every call, in one session."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def of(self, sender: str) -> BusinessKnowledge:
        try:
            return await self._read(sender)
        except SQLAlchemyError:
            logger.warning(
                "reading what the Agency knows failed for %s", mask(sender), exc_info=True
            )
            return BusinessKnowledge()

    async def products(self, sender: str, asset_ids: list[uuid.UUID]) -> list[CatalogItem]:
        if not asset_ids:
            return []
        try:
            async with self._sessions() as db:
                business = await business_of(db, sender)
                if business is None:
                    return []
                rows = await db.scalars(
                    select(Product)
                    .where(
                        Product.business_id == business.id,
                        Product.archived_at.is_(None),
                        Product.id.in_(
                            select(AssetProduct.product_id).where(
                                AssetProduct.asset_id.in_(asset_ids)
                            )
                        ),
                    )
                    .order_by(Product.position, Product.id)
                )
                return [CatalogItem(row.name, row.price, row.description) for row in rows]
        except SQLAlchemyError:
            logger.warning("reading the post's products failed for %s", mask(sender), exc_info=True)
            return []

    async def _read(self, sender: str) -> BusinessKnowledge:
        async with self._sessions() as db:
            business = await business_of(db, sender)
            if business is None:
                return BusinessKnowledge()
            brand = await latest_brand_brain(db, business.id)
            products = await active_products(db, business.id, MAX_PRODUCTS)
            rows = await db.scalars(
                select(OwnerNote)
                .where(OwnerNote.business_id == business.id, OwnerNote.archived_at.is_(None))
                .order_by(OwnerNote.created_at, OwnerNote.id)
            )
            notes = [Note(short_id(row.id), row.text) for row in rows]
            trends = await latest_trend_notes(db, business)
        preferences = business.onboarding_data.get("preferences") or {}
        facts = BusinessFacts(
            name=business.name,
            owner_name=business.owner_name,
            category=business.category,
            one_liner=business.one_liner,
            location=business.location,
            website=business.website,
            instagram_handle=business.instagram_handle,
            current_offer=preferences.get("current_offer"),
            onboarding_state=state_of(business),
            awaiting=awaiting(business),
        )
        catalog = [
            CatalogItem(
                product.name, product.price, product.description[:PRODUCT_DESCRIPTION_CHARS]
            )
            for product in products
        ]
        return BusinessKnowledge(
            facts,
            brand,
            catalog,
            notes,
            summary=business.conversation_summary,
            trend_notes=trends,
        )
