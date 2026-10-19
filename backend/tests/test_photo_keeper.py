"""`PhotoKeeper.keep`: describes each Channel photo and stores it as a Brand asset."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.schemas import AssetAnalysis
from app.conversation.photo_keeper import PhotoKeeper
from app.conversation.photos import InMemoryPhotos, Photo
from app.db.models import AssetProduct, BrandAsset, Business, Product
from tests.conftest import make_image, requires_db
from tests.fakes import FakeStorage, ScriptedModel
from tests.test_asset_analysis import analysis

PHONE = "59899123456"


def new_photo() -> Photo:
    return InMemoryPhotos().add(PHONE, make_image((300, 400)), "la mesa")


@requires_db
async def test_a_photo_from_an_unknown_sender_is_described_not_stored(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    model = ScriptedModel(drafts={AssetAnalysis: analysis([])})
    photo = new_photo()

    await PhotoKeeper(model, sessions, FakeStorage()).keep(PHONE, photo)

    async with sessions() as db:
        assets = (await db.scalars(select(BrandAsset))).all()
    assert (photo.description, photo.asset_id, assets) == ("Mesa de roble en el living", None, [])


@requires_db
async def test_without_storage_a_photo_is_described_not_stored(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        db.add(Business(owner_phone=PHONE))
        await db.commit()
    model = ScriptedModel(drafts={AssetAnalysis: analysis([])})
    photo = new_photo()

    await PhotoKeeper(model, sessions, None).keep(PHONE, photo)

    async with sessions() as db:
        assets = (await db.scalars(select(BrandAsset))).all()
    assert (photo.description, photo.asset_id, assets) == ("Mesa de roble en el living", None, [])


@requires_db
async def test_the_products_the_analyst_found_are_linked_as_its_own(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=PHONE)
        db.add(business)
        await db.flush()
        mesa = Product(business_id=business.id, name="Mesa")
        db.add(mesa)
        await db.commit()
    model = ScriptedModel(drafts={AssetAnalysis: analysis([str(mesa.id)])})
    photo = new_photo()

    await PhotoKeeper(model, sessions, FakeStorage()).keep(PHONE, photo)

    async with sessions() as db:
        link = (await db.scalars(select(AssetProduct))).one()
    assert (link.asset_id, link.product_id, link.source) == (photo.asset_id, mesa.id, "analyst")
