"""`Toolbox`: what the model may call and what each call does (ADR 0007, ADR 0026)."""

from sqlalchemy.exc import SQLAlchemyError

from app.conversation.approval import Approval
from app.conversation.notes import InMemoryNotes, Note
from app.conversation.toolbox import Toolbox
from app.llm.client import FunctionCall
from app.videogen.mock import MockVideoGen
from tests.fakes import EventLog, FakeChannel, ScriptedModel
from tests.test_chat_handler import SENDER, build

OWNER_WORDS = Approval()


class BrokenNotes(InMemoryNotes):
    async def add(self, sender: str, text: str) -> Note | None:
        raise SQLAlchemyError("down")


def toolbox(notes: InMemoryNotes | None = None, **options: object) -> Toolbox:
    chat, _ = build(ScriptedModel(), **options)
    return Toolbox(
        chat.posts,
        chat.publishing,
        chat.lifecycle,
        notes or InMemoryNotes(),
        None,
        chat.video_maker,
    )


async def run(
    box: Toolbox, name: str, owner_request: bool = True, **arguments: object
) -> dict[str, object]:
    return await box.run(
        FunctionCall("call_1", name, arguments),
        SENDER,
        FakeChannel(),
        EventLog(),
        OWNER_WORDS,
        owner_request,
    )


async def test_a_remembered_note_can_be_forgotten() -> None:
    box = toolbox()

    saved = await run(box, "remember", note="vende mesas")
    forgotten = await run(box, "forget", note_id=saved["saved"])

    assert forgotten == {"forgotten": True}
    assert await run(box, "forget", note_id="nope") == {"error": "unknown_note"}


async def test_the_tools_that_act_on_the_owners_words_are_refused_in_a_note_turn() -> None:
    box = toolbox()

    for name in ("create_post", "revise_post", "remember", "forget", "update_brand"):
        assert await run(box, name, owner_request=False) == {"error": "not_owner_request"}
    # Listing is read-only: a note turn may do it.
    assert await run(box, "list_posts", owner_request=False) == {"posts": []}


async def test_an_unknown_tool_is_an_error_the_model_reads() -> None:
    assert await run(toolbox(), "dance") == {"error": "unknown_tool"}


async def test_a_database_failure_is_an_action_failed_result_not_an_exception() -> None:
    box = toolbox(BrokenNotes())

    assert await run(box, "remember", note="vende mesas") == {"error": "action_failed"}


async def test_update_brand_is_not_available_without_a_database() -> None:
    assert await run(toolbox(), "update_brand", change="más formal") == {"error": "not_available"}


async def test_create_video_is_declared_and_dispatched_only_with_a_video_maker() -> None:
    without = toolbox()
    with_video = toolbox(video_gen=MockVideoGen())

    names = lambda box: [tool["name"] for tool in box.declarations]  # noqa: E731
    assert "create_video" not in names(without) and not without.with_video
    assert "create_video" in names(with_video) and with_video.with_video
    assert await run(without, "create_video", post_id="p1") == {"error": "unknown_tool"}
