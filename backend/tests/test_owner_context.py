"""What the orchestrator knows about the Business: notes, context, chat photos (ADR 0030)."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.schemas import AssetAnalysis
from app.conversation.context import render
from app.conversation.library import BrandLibrary
from app.conversation.notes import DbNotes, InMemoryNotes
from app.conversation.photo_keeper import PhotoKeeper
from app.conversation.photos import InMemoryPhotos
from app.conversation.turns import context_block
from app.db.models import AssetProduct, BrandAsset, BrandBrainVersion, Business, Product
from app.knowledge.base import BusinessKnowledge, CatalogItem, Note
from app.knowledge.db import DbKnowledge
from tests.conftest import make_image, requires_db
from tests.fakes import FakeStorage, ScriptedModel, brand_brain

PHONE = "59899123456"


def analysis(product_ids: list[str]) -> AssetAnalysis:
    return AssetAnalysis(
        description="Mesa de roble en el living",
        subjects=["mesa"],
        product_ids=product_ids,
        quality="high",
        orientation="portrait",
        has_people=False,
        has_text=False,
        dominant_colors=[],
        best_for=["hero"],
        safe_crop_focus="center",
    )


async def test_in_memory_notes_add_list_and_forget() -> None:
    notes = InMemoryNotes()

    first = await notes.add(PHONE, "No poner precios")
    await notes.add(PHONE, "Abrimos sábados")
    forgotten = await notes.archive(PHONE, first.id if first else "")
    unknown = await notes.archive(PHONE, "n99")

    assert (forgotten, unknown) == (True, False)
    assert [note.text for note in await notes.list(PHONE)] == ["Abrimos sábados"]


def test_an_empty_context_renders_nothing() -> None:
    assert render(BusinessKnowledge()) == ""


def test_the_context_lists_what_is_known() -> None:
    context = BusinessKnowledge(
        brand=brand_brain(),
        catalog=[CatalogItem("Mesa nórdica", "$U 12.000", "Roble macizo")],
        notes=[Note("n1", "No poner precios")],
        summary="Pidió un post de la mesa.",
        trend_notes="- [hook] Pieza heredable",
    )

    text = render(context)

    assert '"business_name":"Katei"' in text
    assert "whatsapp_summary" not in text.split("<brand_summary_sent>")[0]
    assert "<brand_summary_sent>\n• *Cómo hablamos:* cálidos\n</brand_summary_sent>" in text
    assert "- Mesa nórdica ($U 12.000): Roble macizo" in text
    assert "<owner_notes>\n- n1: No poner precios\n</owner_notes>" in text
    assert '<trend_notes>\n[\n "- [hook] Pieza heredable"\n]\n</trend_notes>' in text
    summary = "<conversation_summary>\nPidió un post de la mesa.\n</conversation_summary>"
    assert text.endswith(summary)


def test_a_chat_photo_kept_as_a_brand_photo_is_listed_once() -> None:
    photos = InMemoryPhotos()
    recent = photos.add(PHONE, make_image((100, 100)), None)
    recent.asset_id = uuid.uuid4()
    library = InMemoryPhotos().add(PHONE, b"", "Mesa: foto")
    library.id, library.asset_id = "b4", recent.asset_id
    other = InMemoryPhotos().add(PHONE, b"", "Silla: foto")
    other.id = "b1"

    block = context_block([recent], [], [other, library])

    assert "- b1: Silla: foto" in block
    assert "b4" not in block


@requires_db
async def test_db_notes_are_kept_per_business_and_archived_when_forgotten(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    notes = DbNotes(sessions)
    assert await notes.add(PHONE, "Sin precios") is None  # no Business yet
    async with sessions() as db:
        db.add(Business(owner_phone=PHONE))
        await db.commit()

    note = await notes.add(PHONE, "Sin precios")
    assert note is not None and note.id.startswith("n")
    assert await notes.list(PHONE) == [note]
    assert await notes.archive(PHONE, note.id) is True
    assert await notes.list(PHONE) == []
    assert await notes.archive(PHONE, note.id) is False


@requires_db
async def test_the_business_context_reads_the_latest_brand_and_the_catalog(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(
            owner_phone=PHONE,
            name="Katei",
            onboarding_state="active",
            onboarding_data={"preferences": {"current_offer": "15% en sillas"}},
            conversation_state={"awaiting": "brand_correction"},
        )
        db.add(business)
        await db.flush()
        db.add_all(
            [
                Product(business_id=business.id, name="Mesa nórdica", price="$U 12.000"),
                BrandBrainVersion(
                    business_id=business.id,
                    version=1,
                    data=brand_brain().model_dump(),
                    reason="onboarding",
                ),
            ]
        )
        await db.commit()

    context = await DbKnowledge(sessions).of(PHONE)

    assert context.business and context.business.current_offer == "15% en sillas"
    assert context.business.awaiting == "brand_correction"
    assert context.brand == brand_brain()
    assert context.catalog == [CatalogItem("Mesa nórdica", "$U 12.000", "")]
    assert await DbKnowledge(sessions).of("000") == BusinessKnowledge()


@requires_db
async def test_a_chat_photo_becomes_a_brand_photo_with_its_analysis(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=PHONE)
        db.add(business)
        await db.flush()
        mesa = Product(business_id=business.id, name="Mesa nórdica")
        db.add(mesa)
        await db.commit()
    storage = FakeStorage()
    model = ScriptedModel(drafts={AssetAnalysis: analysis([str(mesa.id)])})
    photo = InMemoryPhotos().add(PHONE, make_image((300, 400)), "la mesa nueva")

    await PhotoKeeper(model, sessions, storage).keep(PHONE, photo)

    assert photo.description == "Mesa de roble en el living"
    async with sessions() as db:
        asset = await db.get_one(BrandAsset, photo.asset_id)
        linked = await db.scalar(select(AssetProduct.product_id))
    assert (asset.source, asset.status) == ("whatsapp", "ready")
    assert (asset.width, asset.height) == (300, 400)
    assert asset.owner_hint == "la mesa nueva"
    assert linked == mesa.id
    assert "<catalog>" in model.structured_calls[0][0]["text"]
    [kept] = await BrandLibrary(sessions, storage).photos(PHONE)
    assert (kept.id, kept.caption, kept.asset_id) == (
        "b1",
        "Mesa nórdica: Mesa de roble en el living",
        photo.asset_id,
    )


async def test_without_a_database_a_chat_photo_is_only_described() -> None:
    model = ScriptedModel(drafts={AssetAnalysis: analysis([])})
    photo = InMemoryPhotos().add(PHONE, make_image((300, 400)), None)

    await PhotoKeeper(model).keep(PHONE, photo)

    assert (photo.description, photo.asset_id) == ("Mesa de roble en el living", None)
