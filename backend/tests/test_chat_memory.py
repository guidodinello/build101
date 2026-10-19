"""The orchestrator's memory and understanding (ADR 0030): context, notes, compaction, approval."""

import json
from datetime import datetime, timedelta

import pytest

from app.agents.schemas import AssetAnalysis
from app.conversation.chat import ChatHandler
from app.conversation.events import PostSent, StaleButton
from app.conversation.history import Compactor, ConversationSummary
from app.conversation.notes import InMemoryNotes
from app.conversation.photo_keeper import PhotoKeeper
from app.conversation.photos import LOCAL_TZ
from app.posts.store import Post, PostImage
from tests.conftest import make_image
from tests.fakes import FakeChannel, ScriptedModel, call_reply, text_reply
from tests.test_chat_handler import (
    CREATE,
    FOLLOW_UP,
    POST_ID,
    SENDER,
    build,
    message,
    start_gated_post,
    step_text,
)

SATURDAY = datetime(2026, 10, 17, 14, 30, tzinfo=LOCAL_TZ)


def tool_result(model: ScriptedModel, call: int) -> dict[str, object]:
    return json.loads(model.calls[call][-1]["result"])


def yes_names(chat: ChatHandler) -> str | None:
    """The post a bare "sí" would approve now: the one the last reply asked to publish."""
    return chat._lifecycle.approval_for(SENDER, "sí", attached=False, recent_photos=[]).post_id


def add_pending_post(chat: ChatHandler, created_at: datetime | None = None) -> Post:
    post = Post(POST_ID, SENDER, [PostImage("/media/x.jpg", b"jpeg")], "Mesa de roble")
    if created_at:
        post.created_at = created_at
    chat._lifecycle.add(post)
    return post


async def test_a_yes_to_the_publish_question_publishes(monkeypatch: pytest.MonkeyPatch) -> None:
    approve = call_reply("approve_post", post_id=POST_ID, next="publish_now")
    model = ScriptedModel(
        replies=[
            CREATE,
            text_reply("Dale ⏳"),
            text_reply(FOLLOW_UP),
            approve,
            text_reply("¡Dale, lo subo! ⏳"),
            text_reply("¡Publicado!"),
        ]
    )
    chat, posts, channel, gate = await start_gated_post(model, monkeypatch)
    gate.set()
    await posts.join()

    await chat.handle(message("text", text="sí"), channel)

    assert tool_result(model, 4)["status"] == "publishing"
    assert chat._lifecycle.get(SENDER, POST_ID).status != "pending_approval"


async def test_a_yes_to_another_question_publishes_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approve = call_reply("approve_post", post_id=POST_ID, next="publish_now")
    model = ScriptedModel(
        replies=[
            CREATE,
            text_reply("Dale ⏳"),
            text_reply("¿Le cambio el título?"),
            approve,
            text_reply("¿Lo subo?"),
        ]
    )
    chat, posts, channel, gate = await start_gated_post(model, monkeypatch)
    gate.set()
    await posts.join()

    await chat.handle(message("text", text="sí"), channel)

    assert tool_result(model, 4) == {"error": "approval_not_explicit"}
    assert chat._lifecycle.get(SENDER, POST_ID).status == "pending_approval"


async def test_a_fallback_publish_question_counts_too() -> None:
    model = ScriptedModel(fail=True)
    chat, _ = build(model)
    add_pending_post(chat)

    sent = PostSent(POST_ID, 1, "photos", ("f1",), (), "Texto")

    await chat.notify(SENDER, sent, FakeChannel())  # "¿Lo subo o le cambio algo?"
    assert yes_names(chat) == POST_ID
    await chat.notify(SENDER, StaleButton(), FakeChannel())  # a newer message asks nothing
    assert yes_names(chat) is None


async def test_older_unused_photos_do_not_block_an_approval() -> None:
    approve = call_reply("approve_post", post_id=POST_ID, next="publish_now")
    model = ScriptedModel(replies=[approve, text_reply("¡Dale, lo subo! ⏳"), text_reply("Listo")])
    chat, _ = build(model)
    chat._photos.add(SENDER, make_image((100, 100)), None)
    add_pending_post(chat, created_at=datetime.now(LOCAL_TZ) + timedelta(seconds=1))

    await chat.handle(message("text", text="subilo"), FakeChannel())

    assert tool_result(model, 1)["status"] == "publishing"


async def test_photos_sent_after_the_post_make_subilas_a_new_request() -> None:
    approve = call_reply("approve_post", post_id=POST_ID, next="publish_now")
    model = ScriptedModel(replies=[approve, text_reply("¿Armo uno nuevo?")])
    chat, _ = build(model)
    add_pending_post(chat, created_at=datetime.now(LOCAL_TZ) - timedelta(minutes=1))
    chat._photos.add(SENDER, make_image((100, 100)), None)

    await chat.handle(message("text", text="subilas así"), FakeChannel())

    assert tool_result(model, 1) == {"error": "approval_not_explicit"}


async def test_a_remembered_note_reaches_the_next_system_prompt() -> None:
    remember = call_reply("remember", note="No poner precios en los posts")
    model = ScriptedModel(replies=[remember, text_reply("Anotado ✍️"), text_reply("¡Hola!")])
    chat, _ = build(model, notes=InMemoryNotes())

    await chat.handle(message("text", text="nunca pongas precios"), FakeChannel())
    await chat.handle(message("text", text="hola"), FakeChannel())

    assert tool_result(model, 1) == {"saved": "n1"}
    assert "<owner_notes>\n" not in model.systems[0]
    assert "- n1: No poner precios en los posts" in model.systems[2]


async def test_a_forgotten_note_leaves_the_system_prompt() -> None:
    notes = InMemoryNotes()
    await notes.add(SENDER, "Prefiere carruseles")
    forget = call_reply("forget", note_id="n1")
    model = ScriptedModel(replies=[forget, text_reply("Listo"), text_reply("¡Hola!")])
    chat, _ = build(model, notes=notes)

    await chat.handle(message("text", text="ya no quiero carruseles"), FakeChannel())
    await chat.handle(message("text", text="hola"), FakeChannel())

    assert tool_result(model, 1) == {"forgotten": True}
    assert "Prefiere carruseles" in model.systems[0]
    assert "<owner_notes>\n" not in model.systems[2]


async def test_an_event_cannot_remember_or_change_the_brand() -> None:
    model = ScriptedModel(
        replies=[call_reply("remember", note="x"), call_reply("update_brand", change="x")]
        + [text_reply("Ok")]
    )
    chat, _ = build(model)

    await chat.notify(SENDER, StaleButton(), FakeChannel())

    assert tool_result(model, 1) == {"error": "not_owner_request"}
    assert tool_result(model, 2) == {"error": "not_owner_request"}


async def test_update_brand_needs_the_database() -> None:
    update = call_reply("update_brand", change="más formal")
    model = ScriptedModel(replies=[update, text_reply("Ok")])
    chat, _ = build(model)

    await chat.handle(message("text", text="quiero sonar más formal"), FakeChannel())

    assert tool_result(model, 1) == {"error": "not_available"}


async def test_list_posts_shows_each_post_and_its_status() -> None:
    model = ScriptedModel(replies=[call_reply("list_posts"), text_reply("Tenés uno pendiente")])
    chat, _ = build(model)
    add_pending_post(chat)

    await chat.handle(message("text", text="¿qué tengo pendiente?"), FakeChannel())

    [listed] = tool_result(model, 1)["posts"]
    assert (listed["post_id"], listed["status"]) == (POST_ID, "pending_approval")


async def test_owner_turns_think_more_than_event_turns() -> None:
    model = ScriptedModel(replies=[text_reply("¡Hola!")])
    chat, _ = build(model)

    await chat.handle(message("text", text="hola"), FakeChannel())
    await chat.notify(SENDER, StaleButton(), FakeChannel())

    assert model.thinking == ["medium", "low"]


async def test_the_owner_turn_says_when_it_is() -> None:
    model = ScriptedModel(replies=[text_reply("¡Hola!")])
    chat, _ = build(model, now=lambda: SATURDAY)

    await chat.handle(message("text", text="hola"), FakeChannel())

    assert model.calls[0][-1]["content"][1]["text"].startswith("<now>sábado 17/10/2026 14:30</now>")


async def test_old_turns_are_folded_into_the_summary() -> None:
    model = ScriptedModel(
        replies=[text_reply("¡Hola! ¿Qué vendés?")],
        drafts={ConversationSummary: ConversationSummary(summary="Vende mesas de roble.")},
    )
    chat, _ = build(model)
    chat._compactor = Compactor(chat._history, model, max_tokens=100, keep_tokens=40)

    for text in ("hola", "vendo mesas de roble", "y sillas también"):
        await chat.handle(message("text", text=text), FakeChannel())
        await chat.join()
    await chat.handle(message("text", text="¿qué te conté?"), FakeChannel())

    history = await chat._history.get(SENDER)
    assert await chat._history.summary(SENDER) == "Vende mesas de roble."
    assert history[0]["type"] == "user_input"
    assert step_text(history[0]) != "hola"
    assert (
        "<conversation_summary>\nVende mesas de roble.\n</conversation_summary>"
        in (model.systems[-1])
    )
    assert "Owner or system: hola" in model.structured_calls[0][0]["text"]


async def test_a_failed_summary_keeps_the_history_until_the_hard_limit() -> None:
    model = ScriptedModel(replies=[text_reply("¡Hola!")])  # no summary draft: it fails
    chat, _ = build(model)
    chat._compactor = Compactor(
        chat._history, model, max_tokens=50, keep_tokens=20, hard_limit_tokens=10_000
    )

    for text in ("hola", "vendo mesas"):
        await chat.handle(message("text", text=text), FakeChannel())
        await chat.join()

    assert step_text((await chat._history.get(SENDER))[0]) == "hola"


async def test_a_photo_is_described_for_the_next_turns() -> None:
    analysis = AssetAnalysis(
        description="Mesa ratona de roble, vista de frente",
        subjects=["mesa"],
        product_ids=[],
        quality="high",
        orientation="portrait",
        has_people=False,
        has_text=False,
        dominant_colors=[],
        best_for=["hero"],
        safe_crop_focus="center",
    )
    model = ScriptedModel(replies=[text_reply("¡Linda!")], drafts={AssetAnalysis: analysis})
    chat, _ = build(model, keeper=PhotoKeeper(model))

    await chat.handle(message("image", text=None), FakeChannel())
    await chat.join()
    await chat.handle(message("text", text="¿qué te mandé?"), FakeChannel())

    context = model.calls[-1][-1]["content"][1]["text"]
    assert "- f1 sent" in context
    assert ": Mesa ratona de roble, vista de frente" in context
