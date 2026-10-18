import pytest

from app.config import get_settings
from app.llm.client import GeminiChat
from app.posts.drafts import PostDrafter
from tests.conftest import make_image

pytestmark = pytest.mark.live


def live_drafter() -> PostDrafter:
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not set")
    return PostDrafter(GeminiChat.from_api_key(settings.gemini_api_key, settings.gemini_chat_model))


async def test_design_draft_matches_the_generator_input() -> None:
    copy, brief = await live_drafter().design(
        "Mesa ratona de roble nueva, destacar la veta", [make_image((400, 500))], ["f1"], 3
    )

    assert len(copy.slides) == 3
    assert copy.slides[0].role == "cover"
    assert [scene.index for scene in brief.slides] == [1, 2, 3]
    assert brief.reference_asset_ids == ["f1"]
