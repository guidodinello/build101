import json
from dataclasses import replace

from app.agents.asset_analyst import CatalogProduct, analyze_photo
from app.agents.brand_strategist import (
    MAX_SUMMARY_CHARS,
    NEUTRAL_PALETTE,
    BrandInputs,
    write_brand_brain,
)
from app.agents.schemas import AssetAnalysis, FeaturedProduct
from tests.conftest import make_image
from tests.fakes import SequenceModel, brand_brain

CATALOG = [CatalogProduct("p1", "Mesa nórdica", "Roble"), CatalogProduct("p2", "Silla", "Pino")]


def analysis(**changes: object) -> AssetAnalysis:
    base = AssetAnalysis(
        description="Mesa de roble en un living.",
        subjects=["mesa", "roble"],
        product_ids=["p1"],
        quality="high",
        orientation="portrait",
        has_people=False,
        has_text=False,
        dominant_colors=["#AA8855"],
        best_for=["hero"],
        safe_crop_focus="center",
    )
    return base.model_copy(update=changes)


def inputs(**changes: object) -> BrandInputs:
    base = BrandInputs(
        business={"name": "Katei"},
        catalog=[{"id": "p1", "name": "Mesa nórdica", "description": "", "price": None}],
        questionnaire={"goal": "awareness", "posts_per_week": 5, "avoid": "no hablar de precios"},
        brand_words=["cálido", "artesanal", "honesto"],
        colors=["#2f3e2c", "#c89b6d"],
        logo_asset_id="logo-1",
    )
    return replace(base, **changes)


async def test_analysis_keeps_only_catalog_products_and_valid_colors() -> None:
    model = SequenceModel(
        [analysis(product_ids=["p1", "p9", "p1"], dominant_colors=["#AA8855", "beige"])]
    )

    result = await analyze_photo(model, make_image((100, 100)), CATALOG, "la mesa nueva", "p1")

    assert result.product_ids == ["p1"]
    assert result.dominant_colors == ["#aa8855"]
    text = model.contents[0][0]["text"]
    assert "<owner_hint>la mesa nueva</owner_hint>" in text
    assert "<linked_product>p1: Mesa nórdica</linked_product>" in text
    assert model.contents[0][1]["type"] == "image"


async def test_brand_brain_is_held_to_the_owner_facts() -> None:
    featured = [
        FeaturedProduct(product_id="p1", name="Otro nombre", why="el más vendido"),
        FeaturedProduct(product_id="p9", name="Inventado", why="no existe"),
    ]
    model = SequenceModel([brand_brain(featured_products=featured, goal="sales")])

    brain = await write_brand_brain(model, inputs())

    assert [(p.product_id, p.name) for p in brain.featured_products] == [("p1", "Mesa nórdica")]
    assert brain.constraints[0] == "no hablar de precios"
    assert brain.goal == "awareness"
    assert brain.posting.posts_per_week == 5
    assert brain.visual_identity.primary_color == "#2f3e2c"
    assert brain.visual_identity.logo_asset_id == "logo-1"


async def test_without_colors_the_brand_gets_the_neutral_palette() -> None:
    model = SequenceModel([brand_brain()])

    brain = await write_brand_brain(model, inputs(colors=[], logo_asset_id=None))

    identity = brain.visual_identity
    assert (
        identity.primary_color,
        identity.secondary_color,
        identity.accent_color,
        identity.background_color,
        identity.text_color,
    ) == NEUTRAL_PALETTE
    assert identity.logo_asset_id is None
    assert '"owner_colors": "none yet"' in model.contents[0][0]["text"]


async def test_a_summary_over_the_limit_gets_one_retry() -> None:
    long = brand_brain(whatsapp_summary="x" * (MAX_SUMMARY_CHARS + 1))
    model = SequenceModel([long, brand_brain(whatsapp_summary="• corto")])

    brain = await write_brand_brain(model, inputs())

    assert brain.whatsapp_summary == "• corto"
    assert len(model.contents) == 2
    assert "the limit is 600" in model.contents[1][-1]["text"]


async def test_revise_mode_sends_the_previous_brain_and_the_correction() -> None:
    model = SequenceModel([brand_brain()])

    await write_brand_brain(model, inputs(previous=brand_brain(), correction="somos más formales"))

    text = model.contents[0][0]["text"]
    assert "<previous_brand_brain>" in text
    assert "<correction>somos más formales</correction>" in text


def instagram_posts(count: int) -> list[dict[str, object]]:
    return [
        {"caption": f"Post {i} #Roble #montevideo", "likes": i, "comments": 0, "type": "IMAGE"}
        for i in range(count)
    ]


async def test_the_owner_instagram_reaches_the_strategist_as_a_sample() -> None:
    model = SequenceModel([brand_brain()])
    instagram = {
        "username": "katei",
        "biography": "Muebles de roble",
        "posts": [*instagram_posts(40), {"caption": "", "likes": 999}],
    }

    await write_brand_brain(model, inputs(instagram=instagram))

    text = model.contents[0][0]["text"]
    block = json.loads(text.split("<instagram>\n")[1].split("\n</instagram>")[0])
    captions = [item["caption"].split(" #")[0] for item in block["captions"]]
    assert captions[:2] == ["Post 39", "Post 38"]  # most engaged first, then the newest
    assert len(captions) == 30
    assert "Post 0" in captions and "Post 25" not in captions
    assert block["top_hashtags"][:2] == ["#roble", "#montevideo"]
    assert (block["biography"], block["posts_read"]) == ("Muebles de roble", 41)


async def test_without_instagram_there_is_no_instagram_block() -> None:
    model = SequenceModel([brand_brain()])

    await write_brand_brain(model, inputs())

    assert "<instagram>" not in model.contents[0][0]["text"]
