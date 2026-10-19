import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.asset_analyst import CatalogProduct, analyze_photo
from app.agents.schemas import AssetAnalysis
from app.db.models import Product
from app.llm.client import ChatModel


async def analyze_brand_photo(
    model: ChatModel,
    image: bytes,
    owner_hint: str | None,
    *,
    sessions: async_sessionmaker[AsyncSession] | None = None,
    business_id: uuid.UUID | None = None,
    linked_product_id: uuid.UUID | None = None,
) -> AssetAnalysis:
    """The Asset Analyst on one Brand asset photo, against its Business's Catalog.

    The one path for photos from the wizard, Instagram and the Channel. Without `sessions` and
    `business_id` the Catalog is empty (no database). Saving the analysis stays with the caller.
    """
    catalog: list[CatalogProduct] = []
    if sessions is not None and business_id is not None:
        async with sessions() as db:
            catalog = await _catalog(db, business_id)
    linked = str(linked_product_id) if linked_product_id else None
    return await analyze_photo(model, image, catalog, owner_hint, linked)


async def _catalog(db: AsyncSession, business_id: uuid.UUID) -> list[CatalogProduct]:
    products = (
        await db.scalars(
            select(Product)
            .where(Product.business_id == business_id, Product.archived_at.is_(None))
            .order_by(Product.position)
        )
    ).all()
    return [CatalogProduct(str(p.id), p.name, p.description) for p in products]
