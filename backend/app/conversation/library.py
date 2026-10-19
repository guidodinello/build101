import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.schemas import BrandBrain
from app.db.models import AssetProduct, BrandAsset, Business, Product
from app.jobs.brand import latest_brand_brain
from app.jobs.niche import latest_trend_notes
from app.onboarding.uploads import llm_copy_path
from app.storage import ASSETS_BUCKET, StorageError, StoragePort

from .photos import Photo

logger = logging.getLogger(__name__)


class BrandLibrary:
    """The photos the Owner uploaded in the wizard or sent in the chat, offered to the chat as
    `b1`, `b2`, ..., and their logo.

    Until T19 moves the chat onto the database. Ids follow upload order over every photo of the
    Business, archived ones included, so a photo keeps its id. Each agents' copy, and the logo's
    original, is downloaded once and kept in memory.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession], storage: StoragePort) -> None:
        self._sessions = sessions
        self._storage = storage
        self._images: dict[uuid.UUID, bytes] = {}
        self._logos: dict[uuid.UUID, bytes] = {}

    async def photos(self, sender: str) -> list[Photo]:
        async with self._sessions() as db:
            business = await db.scalar(select(Business).where(Business.owner_phone == sender))
            if business is None:
                return []
            assets = (
                await db.scalars(
                    select(BrandAsset)
                    .where(BrandAsset.business_id == business.id, BrandAsset.kind == "photo")
                    .order_by(BrandAsset.created_at, BrandAsset.id)
                )
            ).all()
            products = dict(
                (
                    await db.execute(
                        select(AssetProduct.asset_id, Product.name)
                        .join(Product, Product.id == AssetProduct.product_id)
                        .where(Product.business_id == business.id, Product.archived_at.is_(None))
                    )
                ).all()
            )
        numbered = [
            (f"b{n}", asset)
            for n, asset in enumerate(assets, start=1)
            if asset.status == "ready" and asset.archived_at is None
        ]
        await asyncio.gather(*(self._fetch(asset) for _, asset in numbered))
        return [
            Photo(
                photo_id,
                self._images[asset.id],
                describe(asset, products.get(asset.id)),
                asset.created_at,
                seen=True,
                asset_id=asset.id,
            )
            for photo_id, asset in numbered
            if asset.id in self._images
        ]

    async def logo(self, sender: str) -> bytes | None:
        """The latest logo as uploaded, not the agents' JPEG copy, which drops transparency."""
        async with self._sessions() as db:
            asset = await db.scalar(
                select(BrandAsset)
                .join(Business, Business.id == BrandAsset.business_id)
                .where(
                    Business.owner_phone == sender,
                    BrandAsset.kind == "logo",
                    BrandAsset.status == "ready",
                    BrandAsset.archived_at.is_(None),
                )
                .order_by(BrandAsset.created_at.desc(), BrandAsset.id.desc())
                .limit(1)
            )
        if asset is None:
            return None
        if asset.id not in self._logos:
            data = await self._storage.download(ASSETS_BUCKET, asset.storage_path)
            if data is None:
                # Not "no logo": the Owner has one, and the chat must not tell them otherwise.
                raise StorageError(f"the logo {asset.id} is missing from storage")
            self._logos[asset.id] = data
        return self._logos[asset.id]

    async def _fetch(self, asset: BrandAsset) -> None:
        if asset.id in self._images:
            return
        data = await self._storage.download(
            ASSETS_BUCKET, llm_copy_path(asset.business_id, asset.id)
        )
        if data is None:
            logger.warning("the agents' copy of asset %s is missing", asset.id)
            return
        self._images[asset.id] = data


class BrandBrains:
    """The latest Brand Brain of the Owner's Business, for the posts made in the chat.

    Until T19 moves the chat onto the database. Read on every post, so a correction applies to
    the next one.
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def latest(self, sender: str) -> BrandBrain | None:
        async with self._sessions() as db:
            business_id = await db.scalar(select(Business.id).where(Business.owner_phone == sender))
            if business_id is None:
                return None
            return await latest_brand_brain(db, business_id)


class NicheTrends:
    """The trend notes of the Owner's Business's niche (ADR 0025), for the posts made in the
    chat. Read on every post, so a new week's report applies to the next one."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def latest(self, sender: str) -> str | None:
        async with self._sessions() as db:
            business = await db.scalar(select(Business).where(Business.owner_phone == sender))
            if business is None:
                return None
            return await latest_trend_notes(db, business)


def describe(asset: BrandAsset, product: str | None) -> str:
    """What the model reads about a wizard photo: its product and the Asset Analyst's words."""
    description = (asset.analysis or {}).get("description") or "sin analizar todavía"
    return f"{product}: {description}" if product else description
