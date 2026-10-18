import pytest

from app.posts.drafts import (
    MAX_HASHTAGS,
    CarouselDraft,
    PostCopy,
    PostDrafter,
    SlideDraft,
    clean_hashtags,
)
from tests.fakes import ScriptedModel

SIX = ["#muebles", "#Roble", "#montevideo", "#hechoamano", "#mesas", "#sillas"]


def test_clean_hashtags_caps_at_five_and_keeps_order():
    assert clean_hashtags(SIX) == SIX[:MAX_HASHTAGS]


def test_clean_hashtags_adds_hash_removes_spaces_and_duplicates():
    assert clean_hashtags(["muebles", "# hecho a mano", "#MUEBLES", "#", ""]) == [
        "#muebles",
        "#hechoamano",
    ]


@pytest.mark.asyncio
async def test_copy_caps_hashtags():
    model = ScriptedModel(drafts={PostCopy: PostCopy(caption="c", hashtags=SIX)})
    copy = await PostDrafter(model).copy("una mesa", [b"x"])
    assert copy.hashtags == SIX[:5]


@pytest.mark.asyncio
async def test_design_caps_hashtags():
    draft = CarouselDraft(
        caption="c",
        hashtags=SIX,
        style_prompt="warm",
        style_notes="cálido",
        slides=[SlideDraft(role="cover", headline="h", body="", scene_prompt="s")],
    )
    model = ScriptedModel(drafts={CarouselDraft: draft})
    copy, _ = await PostDrafter(model).design("una mesa", [b"x"], ["a1"], 1)
    assert copy.hashtags == SIX[:5]
