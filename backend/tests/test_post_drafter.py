from app.posts.drafts import (
    SLOT_LIMITS,
    CarouselDraft,
    PostCopy,
    PostDrafter,
    SlideDraft,
    clip_slots,
)
from tests.fakes import ScriptedModel

NOTES = "- [hook] Pieza heredable, no descartable."


def scripted() -> ScriptedModel:
    return ScriptedModel(drafts={PostCopy: PostCopy(caption="Mesa de roble", hashtags=[])})


async def test_trend_notes_reach_the_request() -> None:
    model = scripted()

    await PostDrafter(model, trend_notes=NOTES).copy("Mesa de roble", [])

    request = model.structured_calls[0][0]["text"]
    assert request.endswith(f"Trend notes (what works in the niche this week):\n{NOTES}")


async def test_without_a_report_there_are_no_trend_notes() -> None:
    model = scripted()

    await PostDrafter(model).copy("Mesa de roble", [])

    assert "Trend notes" not in model.structured_calls[0][0]["text"]


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
