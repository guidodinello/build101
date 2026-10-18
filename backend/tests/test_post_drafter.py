from app.posts.drafts import PostCopy, PostDrafter, PreviousPost
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
