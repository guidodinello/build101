from app.posts.drafts import (
    SLOT_LIMITS,
    CarouselDraft,
    PostCopy,
    PostDrafter,
    PreviousPost,
    SlideDraft,
    clip_slots,
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


def slide_draft(**changes: str) -> SlideDraft:
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


def test_hashtags_are_cleaned_deduplicated_and_capped():
    many = [f"#t{i}" for i in range(20)]
    messy = ["#Roble", "roble", "# mesa ratona", "#2026", "#", "nórdico!", *many]

    cleaned = PostCopy(caption="x", hashtags=messy).hashtags

    assert cleaned[:4] == ["#Roble", "#mesaratona", "#nórdico", "#t0"]
    assert len(cleaned) == 10
