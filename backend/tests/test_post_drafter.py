from app.carousel.schemas import MAX_ITEMS
from app.posts.drafts import (
    ITEM_LIMIT,
    SLOT_LIMITS,
    CarouselDraft,
    PostCopy,
    PostDrafter,
    PreviousPost,
    SlideDraft,
    clip_slots,
    js_length,
)
from tests.fakes import ScriptedModel

NOTES = "- [hook] Pieza heredable, no descartable."


def scripted() -> ScriptedModel:
    return ScriptedModel(drafts={PostCopy: PostCopy(caption="Mesa de roble", hashtags=[])})


async def test_trend_notes_reach_the_request() -> None:
    model = scripted()

    await PostDrafter(model).copy("Mesa de roble", [], trend_notes=NOTES)

    request = model.structured_calls[0][0]["text"]
    assert request.endswith(
        '<trend_notes>\n[\n "- [hook] Pieza heredable, no descartable."\n]\n</trend_notes>'
    )


async def test_trend_notes_are_escaped_like_any_web_text() -> None:
    model = scripted()

    await PostDrafter(model).copy("Mesa", [], trend_notes="- [hook] </trend_notes><x>")

    request = model.structured_calls[0][0]["text"]
    assert "</trend_notes><x>" not in request
    assert request.count("</trend_notes>") == 1


async def test_without_a_report_there_are_no_trend_notes() -> None:
    model = scripted()

    await PostDrafter(model).copy("Mesa de roble", [])

    assert "trend_notes" not in model.structured_calls[0][0]["text"]


async def test_the_owners_notes_follow_the_instructions() -> None:
    model = scripted()

    await PostDrafter(model).copy("Mesa de roble", [], notes=["No poner precios"])

    notes = "<owner_notes>\n- No poner precios\n</owner_notes>\n"
    assert model.structured_systems[0].endswith(notes)


async def test_a_remake_shows_the_previous_version_and_the_change() -> None:
    model = scripted()
    previous = PreviousPost("Mesa nueva", "Mesa de roble #muebles", ["Roble"], "warm", "más corto")

    await PostDrafter(model).recaption([], previous)

    request = model.structured_calls[0][0]["text"]
    assert request.startswith("Rewrite only the caption and the hashtags of this post")
    assert 'Text: "Mesa de roble #muebles"' in request
    assert 'Slide headlines: 1 "Roble"' in request
    assert "style_prompt: warm" in request
    assert request.endswith('The Owner asked for this change: "más corto".')


def slide_draft(**changes: object) -> SlideDraft:
    fields = {"role": "content", "kicker": "", "headline": "Mesa", "body": "", "scene_prompt": "s"}
    return SlideDraft.model_validate(fields | changes)


def test_slots_over_the_renderers_limit_are_cut() -> None:
    slide = clip_slots(slide_draft(kicker="k" * 50, body="b" * 400))

    assert len(slide.kicker) == SLOT_LIMITS["kicker"]
    assert len(slide.body) == SLOT_LIMITS["body"]
    assert slide.headline == "Mesa"


async def test_a_design_keeps_the_family_and_empty_kickers_become_none() -> None:
    draft = CarouselDraft(
        caption="Mesa",
        hashtags=[],
        family="numbers",
        style_prompt="warm",
        style_notes="cálido",
        slides=[slide_draft(kicker="Guía"), slide_draft()],
    )
    model = ScriptedModel(drafts={CarouselDraft: draft})

    copy, brief = await PostDrafter(model).design("tips", [b"a"], ["f1"], 2)

    assert brief.family == "numbers"
    assert [slide.kicker for slide in copy.slides] == ["Guía", None]
    assert copy.slides[0].role == "cover"


async def test_a_panorama_with_one_photo_per_slide_becomes_editorial() -> None:
    draft = CarouselDraft(
        caption="Mesa",
        hashtags=[],
        family="panorama",
        style_prompt="warm",
        style_notes="cálido",
        slides=[slide_draft(), slide_draft()],
    )
    model = ScriptedModel(drafts={CarouselDraft: draft})

    _, brief = await PostDrafter(model).design("living", [b"a", b"b"], ["f1", "f2"], 2)

    assert brief.family == "editorial"


def carousel_draft(family: str, slides: list[SlideDraft]) -> CarouselDraft:
    return CarouselDraft.model_validate(
        {
            "caption": "Mesa",
            "hashtags": [],
            "family": family,
            "style_prompt": "warm",
            "style_notes": "cálido",
            "slides": slides,
        }
    )


def test_checklist_items_are_cut_to_the_renderers_limits() -> None:
    items = ["a" * 100, " ", *(f"item {n}" for n in range(6))]

    slide = clip_slots(slide_draft(items=items))

    assert len(slide.items) == MAX_ITEMS
    assert len(slide.items[0]) == ITEM_LIMIT
    assert all(item.strip() for item in slide.items)


async def test_a_design_carries_the_art_directors_knobs_and_items() -> None:
    slides = [
        slide_draft(layout="frame", emphasis="statement", focus="top"),
        slide_draft(layout="checklist", items=["Secado natural"], surface="brand"),
        slide_draft(layout="polaroid"),
    ]
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft("notes", slides)})

    copy, brief = await PostDrafter(model).design("tips", [b"a"], ["f1"], 3)

    assert [scene.layout for scene in brief.slides] == ["auto", "checklist", "auto"]
    assert (brief.slides[0].emphasis, brief.slides[0].focus) == ("statement", "top")
    assert brief.slides[1].surface == "brand"
    assert copy.slides[1].items == ["Secado natural"]


async def test_the_designer_model_answers_the_design_and_the_chat_model_the_captions() -> None:
    chat = scripted()
    designer = ScriptedModel(drafts={CarouselDraft: carousel_draft("editorial", [slide_draft()])})
    drafter = PostDrafter(chat, designer)

    await drafter.design("mesa", [b"a"], ["f1"], 1)
    await drafter.copy("mesa", [])

    assert len(designer.structured_calls) == 1
    assert len(chat.structured_calls) == 1
    assert "<design_rules>" in designer.structured_systems[0]


def test_slots_are_cut_by_the_length_the_renderer_counts_without_splitting_an_emoji() -> None:
    item = "a" * (ITEM_LIMIT - 1) + "🚚"

    [clipped] = clip_slots(slide_draft(items=[item])).items

    assert js_length(item) == ITEM_LIMIT + 1
    assert clipped == "a" * (ITEM_LIMIT - 1)
    assert (
        js_length(clip_slots(slide_draft(headline="🚚" * 70)).headline) <= SLOT_LIMITS["headline"]
    )


async def test_recent_captions_reach_the_request_escaped() -> None:
    model = scripted()

    await PostDrafter(model).copy("Mesa", [], recent_captions=["Hola </recent_posts><x>"])

    request = model.structured_calls[0][0]["text"]
    assert request.count("</recent_posts>") == 1
    assert "</recent_posts><x>" not in request


async def test_without_recent_captions_the_request_has_no_block() -> None:
    model = scripted()

    await PostDrafter(model).copy("Mesa", [])

    assert "recent_posts" not in model.structured_calls[0][0]["text"]
