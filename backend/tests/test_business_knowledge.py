"""What the Agency knows about a Business: one interface, a database and a local adapter."""

import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.conversation.history import InMemoryHistory
from app.conversation.notes import DbNotes, InMemoryNotes
from app.db.models import AssetProduct, BrandAsset, BrandBrainVersion, Business, Product
from app.knowledge.base import BusinessKnowledge, CatalogItem, Knowledge
from app.knowledge.db import MAX_PRODUCTS, DbKnowledge
from app.knowledge.local import LocalKnowledge
from tests.conftest import requires_db
from tests.fakes import brand_brain

PHONE = "59899123456"
TRENDS = "- [hook] Pieza heredable"


@dataclass
class Rig:
    """An adapter and the ways its Owner's notes and summary get written."""

    knowledge: Knowledge
    add_note: Callable[[str], Awaitable[None]]
    set_summary: Callable[[str], Awaitable[None]]


def local_rig() -> Rig:
    notes, history = InMemoryNotes(), InMemoryHistory()

    async def add_note(text: str) -> None:
        await notes.add(PHONE, text)

    async def set_summary(text: str) -> None:
        await history.compact(PHONE, 0, text)

    return Rig(LocalKnowledge(notes, history), add_note, set_summary)


async def db_rig(sessions: async_sessionmaker[AsyncSession]) -> Rig:
    async with sessions() as db:
        db.add(Business(owner_phone=PHONE, name="Katei"))
        await db.commit()

    async def add_note(text: str) -> None:
        await DbNotes(sessions).add(PHONE, text)

    async def set_summary(text: str) -> None:
        async with sessions() as db:
            business = await db.scalar(select(Business).where(Business.owner_phone == PHONE))
            assert business is not None
            business.conversation_summary = text
            await db.commit()

    return Rig(DbKnowledge(sessions), add_note, set_summary)


async def a_sender_nobody_told_us_about_knows_nothing(rig: Rig) -> None:
    assert await rig.knowledge.of("59800000000") == BusinessKnowledge()


async def the_notes_and_the_summary_are_part_of_what_is_known(rig: Rig) -> None:
    await rig.add_note("Abrimos sábados")
    await rig.add_note("No poner precios")
    await rig.set_summary("Pidió un post de la mesa.")

    known = await rig.knowledge.of(PHONE)

    assert [note.text for note in known.notes] == ["Abrimos sábados", "No poner precios"]
    assert known.summary == "Pidió un post de la mesa."


# What every adapter of `Knowledge` answers the same way.
CONTRACT = [
    a_sender_nobody_told_us_about_knows_nothing,
    the_notes_and_the_summary_are_part_of_what_is_known,
]


@pytest.mark.parametrize("case", CONTRACT, ids=lambda case: case.__name__)
async def test_the_local_adapter_keeps_the_contract(case: Callable[[Rig], Awaitable[None]]) -> None:
    await case(local_rig())


@requires_db
@pytest.mark.parametrize("case", CONTRACT, ids=lambda case: case.__name__)
async def test_the_database_adapter_keeps_the_contract(
    case: Callable[[Rig], Awaitable[None]], sessions: async_sessionmaker[AsyncSession]
) -> None:
    await case(await db_rig(sessions))


async def test_the_same_trend_notes_serve_every_sender_without_a_database() -> None:
    knowledge = LocalKnowledge(InMemoryNotes(), InMemoryHistory(), TRENDS)

    assert (await knowledge.of(PHONE)).trend_notes == TRENDS
    assert (await knowledge.of("59800000000")).trend_notes == TRENDS


class BrokenSessions:
    def __call__(self) -> AsyncSession:
        raise OperationalError("select", {}, ConnectionError("database down"))


async def test_a_database_failure_leaves_nothing_known_rather_than_raising() -> None:
    knowledge = DbKnowledge(BrokenSessions())  # type: ignore[arg-type]

    assert await knowledge.of(PHONE) == BusinessKnowledge()


@requires_db
async def test_the_catalog_is_the_active_products_in_the_owners_order(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=PHONE, name="Katei")
        db.add(business)
        await db.flush()
        db.add_all(
            [
                Product(business_id=business.id, name="Silla", position=2),
                Product(business_id=business.id, name="Mesa", price="$U 12.000", position=1),
                Product(
                    business_id=business.id,
                    name="Banco viejo",
                    position=0,
                    archived_at=datetime.now(UTC),
                ),
            ]
        )
        await db.commit()

    known = await DbKnowledge(sessions).of(PHONE)

    assert known.catalog == [
        CatalogItem("Mesa", "$U 12.000", ""),
        CatalogItem("Silla", None, ""),
    ]


@requires_db
async def test_the_catalog_is_capped_and_its_descriptions_cut(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=PHONE, name="Katei")
        db.add(business)
        await db.flush()
        db.add_all(
            Product(business_id=business.id, name=f"P{n}", description="x" * 500, position=n)
            for n in range(MAX_PRODUCTS + 5)
        )
        await db.commit()

    known = await DbKnowledge(sessions).of(PHONE)

    assert len(known.catalog) == MAX_PRODUCTS
    assert len(known.catalog[0].description) == 200


@requires_db
async def test_the_brand_is_the_latest_version(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=PHONE, name="Katei")
        db.add(business)
        await db.flush()
        first = brand_brain().model_copy(update={"one_liner": "Primera"})
        second = brand_brain().model_copy(update={"one_liner": "Segunda"})
        db.add_all(
            BrandBrainVersion(
                business_id=business.id,
                version=version,
                data=brain.model_dump(),
                reason="onboarding",
            )
            for version, brain in ((1, first), (2, second))
        )
        await db.commit()

    known = await DbKnowledge(sessions).of(PHONE)

    assert known.brand is not None
    assert known.brand.one_liner == "Segunda"


def photo_asset(business: Business, n: int) -> BrandAsset:
    return BrandAsset(
        business_id=business.id,
        kind="photo",
        source="web",
        status="ready",
        storage_path=f"{business.id}/{n}.jpg",
        mime_type="image/jpeg",
    )


@requires_db
async def test_a_posts_products_are_those_linked_to_its_photos_each_once(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=PHONE, name="Katei")
        other = Business(owner_phone="59899000002", name="Otra")
        db.add_all([business, other])
        await db.flush()
        mesa = Product(
            business_id=business.id,
            name="Mesa",
            price="$U 12.000",
            description="Enchapada en roble. " + "x" * 300,
            position=2,
        )
        silla = Product(business_id=business.id, name="Silla", position=1)
        banco = Product(
            business_id=business.id, name="Banco", position=0, archived_at=datetime.now(UTC)
        )
        ajena = Product(business_id=other.id, name="Ajena", position=0)
        lampara = Product(business_id=business.id, name="Lámpara", position=3)
        photos = [photo_asset(business, n) for n in range(3)]
        db.add_all([mesa, silla, banco, ajena, lampara, *photos])
        await db.flush()
        db.add_all(
            [
                AssetProduct(asset_id=photos[0].id, product_id=mesa.id, source="owner"),
                AssetProduct(asset_id=photos[0].id, product_id=banco.id, source="owner"),
                AssetProduct(asset_id=photos[1].id, product_id=mesa.id, source="analyst"),
                AssetProduct(asset_id=photos[1].id, product_id=silla.id, source="analyst"),
                AssetProduct(asset_id=photos[1].id, product_id=ajena.id, source="analyst"),
                AssetProduct(asset_id=photos[2].id, product_id=lampara.id, source="owner"),
            ]
        )
        await db.commit()

    products = await DbKnowledge(sessions).products(PHONE, [photos[0].id, photos[1].id])

    assert products == [
        CatalogItem("Silla", None, ""),
        CatalogItem("Mesa", "$U 12.000", "Enchapada en roble. " + "x" * 300),
    ]


@requires_db
async def test_photos_without_links_have_no_products(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=PHONE, name="Katei")
        db.add(business)
        await db.flush()
        photo = photo_asset(business, 1)
        db.add_all([photo, Product(business_id=business.id, name="Mesa")])
        await db.commit()

    knowledge = DbKnowledge(sessions)

    assert await knowledge.products(PHONE, [photo.id]) == []
    assert await knowledge.products("59800000000", [photo.id]) == []


async def test_without_a_database_there_are_no_products() -> None:
    assert await local_rig().knowledge.products(PHONE, [uuid.uuid4()]) == []


async def test_a_database_failure_reads_as_no_products() -> None:
    knowledge = DbKnowledge(BrokenSessions())  # type: ignore[arg-type]

    assert await knowledge.products(PHONE, [uuid.uuid4()]) == []
