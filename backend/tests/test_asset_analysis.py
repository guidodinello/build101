"""The one Asset Analyst path for Brand asset photos (wizard, Instagram and Channel)."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.schemas import AssetAnalysis
from app.assets.analysis import analyze_brand_photo
from app.db.models import Business, Product
from tests.conftest import make_image, requires_db
from tests.fakes import ScriptedModel


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


async def add_catalog(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[uuid.UUID, list[Product]]:
    async with sessions() as db:
        business = Business(owner_phone="59899123456")
        db.add(business)
        await db.flush()
        products = [
            Product(business_id=business.id, name="Silla", description="Pino", position=2),
            Product(business_id=business.id, name="Mesa", description="Roble", position=1),
            Product(
                business_id=business.id, name="Vieja", position=0, archived_at=datetime.now(UTC)
            ),
        ]
        db.add_all(products)
        await db.commit()
    return business.id, products


async def test_without_a_database_the_catalog_is_empty_and_unknown_products_are_dropped() -> None:
    model = ScriptedModel(drafts={AssetAnalysis: analysis([str(uuid.uuid4())])})

    result = await analyze_brand_photo(model, make_image((100, 100)), "la mesa")

    assert result.product_ids == []
    assert "<catalog>\n[]\n</catalog>" in model.structured_calls[0][0]["text"]
    assert '<owner_hint>\n"la mesa"\n</owner_hint>' in model.structured_calls[0][0]["text"]


@requires_db
async def test_the_catalog_is_the_businesss_active_products_in_order(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business_id, products = await add_catalog(sessions)
    silla, mesa, _ = products
    model = ScriptedModel(drafts={AssetAnalysis: analysis([str(silla.id)])})

    result = await analyze_brand_photo(
        model, make_image((100, 100)), None, sessions=sessions, business_id=business_id
    )

    text = model.structured_calls[0][0]["text"]
    assert text.index("Mesa") < text.index("Silla")
    assert "Vieja" not in text
    assert result.product_ids == [str(silla.id)]


@requires_db
async def test_the_linked_product_reaches_the_analyst(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business_id, products = await add_catalog(sessions)
    model = ScriptedModel(drafts={AssetAnalysis: analysis([])})

    await analyze_brand_photo(
        model,
        make_image((100, 100)),
        None,
        sessions=sessions,
        business_id=business_id,
        linked_product_id=products[1].id,
    )

    assert "<linked_product>" in model.structured_calls[0][0]["text"]
