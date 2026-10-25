import pytest

from app.posts.drafts import PostCopy, PostDrafter
from app.posts.voseo import tuteo_forms
from tests.fakes import SequenceModel


@pytest.mark.parametrize(
    "text",
    [
        "Tenés que verla: mirá cómo queda en tu living.",
        "Escribinos y coordinamos. ¿Querés una igual?",
        "Casas, mesas y sillas de roble",
    ],
)
def test_voseo_and_shared_forms_are_not_tuteo(text: str) -> None:
    assert tuteo_forms(text) == []


def test_tuteo_forms_are_found_once_each() -> None:
    found = tuteo_forms("¿Tú quieres una? Puedes pasar, tú decidís.", "Ven y haz tu pedido")

    assert found == ["tú", "quieres", "puedes", "ven", "haz"]


async def test_a_draft_in_tuteo_is_rewritten_once() -> None:
    model = SequenceModel(
        [
            PostCopy(caption="Si quieres una mesa, ven", hashtags=[]),
            PostCopy(caption="Si querés", hashtags=[]),
        ]
    )

    copy = await PostDrafter(model).copy("Mesa", [])

    assert copy.caption == "Si querés"
    assert len(model.contents) == 2
    assert "quieres, ven" in model.contents[1][-1]["text"]


async def test_a_draft_in_voseo_is_not_asked_again() -> None:
    model = SequenceModel([PostCopy(caption="Mirá esta mesa", hashtags=[])])

    await PostDrafter(model).copy("Mesa", [])

    assert len(model.contents) == 1


async def test_a_second_draft_in_tuteo_is_sent_on() -> None:
    tuteo = PostCopy(caption="Tienes que verla", hashtags=[])
    model = SequenceModel([tuteo, tuteo])

    copy = await PostDrafter(model).copy("Mesa", [])

    assert copy.caption == "Tienes que verla"
    assert len(model.contents) == 2
