from app.posts.drafts import PostCopy, PostDrafter
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
