import logging

import pytest

from app.conversation.photos import InMemoryPhotos
from app.knowledge.base import BusinessKnowledge, CatalogItem
from app.posts.checks import MAX_HASHTAGS, clean_hashtags, cut_unsourced, known_figures
from app.posts.drafts import CarouselDraft, PostCopy, PostDrafter, PreviousPost, SlideDraft
from tests.conftest import make_image
from tests.fakes import CountingImageGen, FakeChannel, ScriptedModel, brand_brain
from tests.test_post_maker import NOON, SENDER, FakeKnowledge, drop, maker

MESSY = [
    "#Muebles",
    "roble",
    "#muebles de madera",
    "#ROBLE",
    "#hecho-a-mano",
    "#2026",
    "#mvd",
    "#x",
]
CLEAN = ["#Muebles", "#roble", "#mueblesdemadera", "#hechoamano", "#mvd"]
PREVIOUS = PreviousPost("Mesa de roble", "Mesa de roble #muebles", [], None, "más corto")


def photo_copy(caption: str, hashtags: list[str] | None = None) -> ScriptedModel:
    return ScriptedModel(drafts={PostCopy: PostCopy(caption=caption, hashtags=hashtags or [])})


def slide(**changes: object) -> SlideDraft:
    fields = {"role": "content", "kicker": "", "headline": "Mesa", "body": "", "scene_prompt": "s"}
    return SlideDraft.model_validate(fields | changes)


def design_model(slides: list[SlideDraft], caption: str = "Mesa de roble.") -> ScriptedModel:
    draft = CarouselDraft(
        caption=caption,
        hashtags=MESSY,
        family="editorial",
        style_prompt="warm",
        style_notes="cálido",
        slides=slides,
    )
    return ScriptedModel(drafts={CarouselDraft: draft})


def test_hashtags_are_cleaned_deduplicated_and_capped() -> None:
    assert clean_hashtags(MESSY) == CLEAN
    assert len(CLEAN) == MAX_HASHTAGS


async def test_photo_posts_get_clean_hashtags() -> None:
    copy = await PostDrafter(photo_copy("Mesa de roble.", MESSY)).copy("Mesa", [])

    assert copy.hashtags == CLEAN


async def test_a_caption_only_change_gets_clean_hashtags() -> None:
    copy = await PostDrafter(photo_copy("Mesa de roble.", MESSY)).recaption([], PREVIOUS)

    assert copy.hashtags == CLEAN


async def test_a_design_gets_clean_hashtags() -> None:
    copy, _ = await PostDrafter(design_model([slide()])).design("Mesa", [b"a"], ["f1"], 1)

    assert copy.hashtags == CLEAN


@pytest.mark.parametrize(
    "figure", ["$U 18.500", "15% off", "U$S 300", "el 20/11", "8 de diciembre"]
)
async def test_a_sentence_with_an_unsourced_figure_is_removed(figure: str) -> None:
    caption = f"Mesa de roble hecha a mano. Ahora {figure} en el taller. Escribinos."

    copy = await PostDrafter(photo_copy(caption)).copy("Mesa de roble", [])

    assert copy.caption == "Mesa de roble hecha a mano. Escribinos."


async def test_paragraphs_survive_a_removed_sentence() -> None:
    caption = "Mesa de roble.\n\nSolo hoy 20% off.\n\nEscribinos."

    copy = await PostDrafter(photo_copy(caption)).copy("Mesa de roble", [])

    assert copy.caption == "Mesa de roble.\n\nEscribinos."


async def test_a_figure_in_a_product_price_is_kept_comparing_digits() -> None:
    caption = "Mesa de roble a $4.900. Escribinos."

    copy = await PostDrafter(photo_copy(caption)).copy("Mesa de roble", [], prices=["4900"])

    assert copy.caption == caption


@pytest.mark.parametrize(
    ("note", "brief"),
    [("Las sillas tienen 15% off hasta fin de mes", "Sillas"), (None, "Sillas con 15% off")],
)
async def test_a_figure_from_an_owner_note_or_the_brief_is_kept(
    note: str | None, brief: str
) -> None:
    caption = "Sillas de roble con 15% off. Escribinos."

    drafter = PostDrafter(photo_copy(caption))
    copy = await drafter.copy(brief, [], notes=[note] if note else None)

    assert copy.caption == caption


async def test_a_figure_from_the_brand_brain_is_kept() -> None:
    brand = brand_brain(value_props=["Envío gratis en compras de más de $3000"])
    caption = "Envío gratis desde $3.000. Escribinos."

    copy = await PostDrafter(photo_copy(caption)).copy("Mesa", [], brand)

    assert copy.caption == caption


async def test_the_onboarding_promo_in_the_brand_summary_is_no_source() -> None:
    brand = brand_brain(whatsapp_summary="• *Promo:* 15% en sillas (te pregunto antes de usarla)")

    copy = await PostDrafter(photo_copy("Sillas. Ahora 15% off.")).copy("Sillas", [], brand)

    assert copy.caption == "Sillas."


async def test_a_remake_may_keep_a_figure_from_the_owners_change() -> None:
    previous = PreviousPost("Mesa", "Mesa #muebles", [], None, "poné que sale $U 9.900")
    caption = "Mesa de roble a $U 9.900."

    copy = await PostDrafter(photo_copy(caption)).recaption([], previous)

    assert copy.caption == caption


async def test_vale_la_pena_is_left_untouched() -> None:
    caption = "Una mesa de roble que vale la pena. Escribinos y te contamos."

    copy = await PostDrafter(photo_copy(caption)).copy("Mesa de roble", [])

    assert copy.caption == caption


async def test_when_every_sentence_is_unsourced_the_brands_cta_stands_in() -> None:
    caption = "Mesa a $U 18.500. Solo hoy 15% off."

    drafter = PostDrafter(photo_copy(caption))
    with_brand = await drafter.copy("Mesa", [], brand_brain(ctas=["Escribinos por WhatsApp"]))
    without_brand = await drafter.copy("Mesa", [])

    assert with_brand.caption == "Escribinos por WhatsApp"
    assert without_brand.caption == ""


async def test_unsourced_figures_never_reach_the_slides() -> None:
    slides = [
        slide(kicker="20% off", headline="Mesas a $U 18.500", body="Roble macizo. Hasta el 30/11."),
        slide(headline="$4.900", items=["Roble", "Desde $2.000"], role="content"),
        slide(kicker="Precio", headline="Sillas $4.900", body="Precio de lista."),
    ]

    copy, _ = await PostDrafter(design_model(slides)).design(
        "Mesas", [b"a"], ["f1"], 3, prices=["$4900"]
    )

    cover, second, third = copy.slides
    assert (cover.kicker, cover.headline, cover.body) == (None, "Mesas", "Roble macizo.")
    assert second.headline == "$4.900"
    assert second.items == ["Roble"]
    assert (third.kicker, third.headline) == ("Precio", "Sillas $4.900")


async def test_a_headline_that_is_only_a_figure_gets_the_kicker_or_the_business_name() -> None:
    slides = [slide(kicker="Oferta", headline="$U 18.500"), slide(headline="15% off")]

    copy, _ = await PostDrafter(design_model(slides)).design(
        "Mesas", [b"a"], ["f1"], 2, brand_brain()
    )

    assert [s.headline for s in copy.slides] == ["Oferta", "Katei"]


def test_cutting_a_figure_drops_the_words_left_dangling() -> None:
    assert cut_unsourced("Sillas a $U 18.500", set(), "headline") == "Sillas"
    assert cut_unsourced("Sillas: 15% off", set(), "headline") == "Sillas"


def test_known_figures_compare_digits() -> None:
    assert known_figures(["$4.900", "15 %", "el 05/11"]) == {"4900", "15", "511"}


async def test_removals_are_logged_without_the_owners_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="app.posts")

    await PostDrafter(photo_copy("Mesa de roble. Ahora $U 18.500.")).copy("Mesa", [])

    removals = [r for r in caplog.records if "unsourced" in r.getMessage()]
    assert removals and all(r.levelno == logging.INFO for r in removals)
    assert all("18.500" not in r.getMessage() for r in caplog.records)


async def test_the_post_maker_lets_a_catalog_price_through() -> None:
    photos = InMemoryPhotos(now=lambda: NOON)
    photos.add(SENDER, make_image((100, 100)), None)
    model = photo_copy("Mesa de roble a $4.900. Silla a $U 1.200.")
    knowledge = FakeKnowledge(BusinessKnowledge(catalog=[CatalogItem("Mesa", "$ 4900", "")]))
    channel = FakeChannel()
    posts, background = maker(model, CountingImageGen(), photos, knowledge=knowledge)

    posts.create_post(
        SENDER, {"brief": "Mesa", "asset_ids": ["f1"], "style": "photos"}, channel, drop
    )
    await background.join()

    assert channel.images[0][2] == "Mesa de roble a $4.900."
