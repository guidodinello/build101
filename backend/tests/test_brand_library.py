from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.conversation.library import BrandBrains, BrandLibrary
from app.db.models import AssetProduct, BrandAsset, BrandBrainVersion, Business, Product
from tests.conftest import make_image, requires_db
from tests.fakes import FakeStorage, brand_brain

pytestmark = requires_db

PHONE = "59899123456"


class CountingStorage(FakeStorage):
    downloads: int = 0

    async def download(self, bucket: str, path: str) -> bytes | None:
        self.downloads += 1
        return await super().download(bucket, path)


async def test_the_wizard_photos_keep_their_ids_and_show_their_product(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    storage = CountingStorage()
    start = datetime.now(UTC) - timedelta(hours=1)
    async with sessions() as db:
        business = Business(owner_phone=PHONE, name="Katei")
        db.add(business)
        await db.flush()
        mesa = Product(business_id=business.id, name="Mesa nórdica")
        photos = [
            BrandAsset(
                business_id=business.id,
                kind="photo",
                source="web",
                status="ready",
                storage_path=f"{business.id}/{n}.jpg",
                mime_type="image/jpeg",
                analysis={"description": f"Foto {n}"},
                archived_at=start if n == 2 else None,
                created_at=start + timedelta(minutes=n),
            )
            for n in (1, 2, 3)
        ]
        logo = BrandAsset(
            business_id=business.id,
            kind="logo",
            source="web",
            status="ready",
            storage_path=f"{business.id}/logo.png",
            mime_type="image/png",
        )
        db.add_all([mesa, *photos, logo])
        await db.flush()
        db.add(AssetProduct(asset_id=photos[2].id, product_id=mesa.id, source="owner"))
        await db.commit()
    for photo in photos:
        storage.put("assets", f"{business.id}/{photo.id}-llm.jpg", make_image((100, 100)))
    library = BrandLibrary(sessions, storage)

    first = await library.photos(PHONE)
    again = await library.photos(PHONE)

    assert [(p.id, p.caption) for p in first] == [("b1", "Foto 1"), ("b3", "Mesa nórdica: Foto 3")]
    assert [p.id for p in again] == ["b1", "b3"]
    assert storage.downloads == 2


async def test_an_unknown_sender_has_no_wizard_photos(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    assert await BrandLibrary(sessions, FakeStorage()).photos("59800000000") == []


async def test_posts_read_the_latest_brand_brain_version(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=PHONE, name="Katei")
        db.add(business)
        await db.flush()
        db.add_all(
            [
                BrandBrainVersion(
                    business_id=business.id,
                    version=version,
                    data=brand_brain(one_liner=one_liner).model_dump(),
                    reason=reason,
                )
                for version, one_liner, reason in [
                    (1, "Muebles restaurados", "onboarding"),
                    (2, "Muebles restaurados a mano", "correction"),
                ]
            ]
        )
        await db.commit()

    brand = await BrandBrains(sessions).latest(PHONE)

    assert brand is not None
    assert brand.one_liner == "Muebles restaurados a mano"


async def test_an_owner_without_a_brand_brain_has_none(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        db.add(Business(owner_phone=PHONE, name="Katei"))
        await db.commit()

    assert await BrandBrains(sessions).latest(PHONE) is None
    assert await BrandBrains(sessions).latest("59800000000") is None


async def test_the_latest_logo_is_read_as_uploaded_once(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    storage = CountingStorage()
    start = datetime.now(UTC) - timedelta(hours=1)
    async with sessions() as db:
        business = Business(owner_phone=PHONE, name="Katei")
        db.add(business)
        await db.flush()
        logos = [
            BrandAsset(
                business_id=business.id,
                kind="logo",
                source="web",
                status="ready",
                storage_path=f"{business.id}/logo-{n}.png",
                mime_type="image/png",
                created_at=start + timedelta(minutes=n),
            )
            for n in (1, 2)
        ]
        db.add_all(logos)
        await db.commit()
    newest = make_image((200, 80), format="PNG")
    storage.put("assets", f"{business.id}/logo-1.png", make_image((10, 10), format="PNG"))
    storage.put("assets", f"{business.id}/logo-2.png", newest)
    library = BrandLibrary(sessions, storage)

    assert await library.logo(PHONE) == newest
    assert await library.logo(PHONE) == newest
    assert storage.downloads == 1


async def test_an_owner_without_a_logo_has_none(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        db.add(Business(owner_phone=PHONE, name="Katei"))
        await db.commit()

    assert await BrandLibrary(sessions, FakeStorage()).logo(PHONE) is None
