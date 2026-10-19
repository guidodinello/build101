"""What the Agency knows about a Business: one interface, a database and a local adapter."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.conversation.history import InMemoryHistory
from app.conversation.notes import DbNotes, InMemoryNotes
from app.db.models import BrandBrainVersion, Business, Product
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
