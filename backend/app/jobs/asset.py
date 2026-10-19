import uuid
from typing import Any

from sqlalchemy import select

from app.agents.asset_analyst import CatalogProduct, analyze_photo
from app.db.models import AssetProduct, BrandAsset, Product
from app.onboarding.uploads import llm_copy_path
from app.storage import ASSETS_BUCKET

from .runner import JobContext


async def analyze_asset(context: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
    """Asset Analyst on one photo; the analysis is saved on the Brand asset (agents.md)."""
    asset_id = uuid.UUID(payload["asset_id"])
    async with context.sessions() as db:
        asset = await db.get(BrandAsset, asset_id)
        if asset is None or asset.archived_at is not None or asset.status != "ready":
            return {"skipped": "not a ready asset"}
        if asset.analysis is not None:
            return {"skipped": "already analyzed"}
        products = (
            await db.scalars(
                select(Product)
                .where(Product.business_id == asset.business_id, Product.archived_at.is_(None))
                .order_by(Product.position)
            )
        ).all()
        linked = await db.scalar(
            select(AssetProduct.product_id).where(
                AssetProduct.asset_id == asset.id, AssetProduct.source == "owner"
            )
        )
        business_id, owner_hint = asset.business_id, asset.owner_hint

    image = await context.storage.download(ASSETS_BUCKET, llm_copy_path(business_id, asset_id))
    if image is None:
        async with context.sessions() as db:
            current = await db.get(BrandAsset, asset_id)
        if current is None or current.archived_at is not None:
            return {"skipped": "archived while queued"}  # archiving deletes the files
        raise FileNotFoundError(f"the agents' copy of asset {asset_id} is missing")
    catalog = [CatalogProduct(str(p.id), p.name, p.description) for p in products]
    analysis = await analyze_photo(
        context.model, image, catalog, owner_hint, str(linked) if linked else None
    )

    async with context.sessions() as db:
        asset = await db.get_one(BrandAsset, asset_id)
        asset.analysis = analysis.model_dump()
        await db.commit()
    return {"quality": analysis.quality, "product_ids": analysis.product_ids}
