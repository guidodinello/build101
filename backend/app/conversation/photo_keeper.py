import asyncio
import uuid
from io import BytesIO

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.asset_analyst import CatalogProduct, analyze_photo
from app.agents.schemas import AssetAnalysis
from app.db.models import AssetProduct, BrandAsset, Business, Product
from app.llm.client import ChatModel
from app.onboarding.uploads import asset_path, llm_copy_path
from app.storage import ASSETS_BUCKET, StoragePort

from .photos import Photo

JPEG = "image/jpeg"


class PhotoKeeper:
    """Describes each photo the Owner sends in the chat (Asset Analyst) and, with the database,
    stores it as a Brand asset, so it outlives the 30 minutes of `<recent_photos>` (ADR 0030).
    """

    def __init__(
        self,
        model: ChatModel,
        sessions: async_sessionmaker[AsyncSession] | None = None,
        storage: StoragePort | None = None,
    ) -> None:
        self._model = model
        self._sessions = sessions
        self._storage = storage

    async def keep(self, sender: str, photo: Photo) -> None:
        business_id, catalog = await self._business(sender)
        analysis = await analyze_photo(self._model, photo.data, catalog, photo.caption, None)
        photo.description = analysis.description
        if business_id is not None and self._sessions and self._storage:
            photo.asset_id = await store_photo(
                self._sessions, self._storage, business_id, photo, analysis
            )

    async def _business(self, sender: str) -> tuple[uuid.UUID | None, list[CatalogProduct]]:
        if self._sessions is None or self._storage is None:
            return None, []
        async with self._sessions() as db:
            business_id = await db.scalar(select(Business.id).where(Business.owner_phone == sender))
            if business_id is None:
                return None, []
            products = (
                await db.scalars(
                    select(Product)
                    .where(Product.business_id == business_id, Product.archived_at.is_(None))
                    .order_by(Product.position)
                )
            ).all()
        return business_id, [CatalogProduct(str(p.id), p.name, p.description) for p in products]


async def store_photo(
    sessions: async_sessionmaker[AsyncSession],
    storage: StoragePort,
    business_id: uuid.UUID,
    photo: Photo,
    analysis: AssetAnalysis,
) -> uuid.UUID:
    asset_id = uuid.uuid4()
    path = asset_path(business_id, asset_id, JPEG)
    # The photo is already the agents' JPEG (prepare_reference): it is both copies.
    await storage.upload(ASSETS_BUCKET, path, photo.data, JPEG)
    await storage.upload(ASSETS_BUCKET, llm_copy_path(business_id, asset_id), photo.data, JPEG)
    width, height = await asyncio.to_thread(image_size, photo.data)
    async with sessions() as db:
        db.add(
            BrandAsset(
                id=asset_id,
                business_id=business_id,
                kind="photo",
                source="whatsapp",
                status="ready",
                storage_path=path,
                mime_type=JPEG,
                size_bytes=len(photo.data),
                width=width,
                height=height,
                owner_hint=photo.caption,
                analysis=analysis.model_dump(),
            )
        )
        await db.flush()
        db.add_all(
            AssetProduct(asset_id=asset_id, product_id=uuid.UUID(product_id), source="analyst")
            for product_id in analysis.product_ids
        )
        await db.commit()
    return asset_id


def image_size(data: bytes) -> tuple[int, int]:
    with Image.open(BytesIO(data)) as image:
        return image.size
