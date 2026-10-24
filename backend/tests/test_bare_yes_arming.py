"""A bare "sí" approves only the post the assistant's reply ended by asking to publish (#107)."""

import asyncio
import json

import pytest

from app.posts.store import Post, PostImage
from tests.conftest import make_image
from tests.fakes import CountingImageGen, FakeChannel, ScriptedModel, call_reply, text_reply
from tests.test_chat_handler import SENDER, build, message

POST_ID = "abcdef12"
APPROVE = call_reply("approve_post", post_id=POST_ID, next="publish_now")


async def answer_with_a_yes(question: str, yes: str) -> tuple[dict[str, str], str]:
    """The tool result the model got for `approve_post` after `yes`, and the post's status."""
    model = ScriptedModel(replies=[text_reply(question), APPROVE, text_reply("ok")])
    chat, _ = build(model)
    chat.lifecycle.add(Post(POST_ID, SENDER, [PostImage("/media/a.jpg", b"x")], "Mesa de roble"))
    channel = FakeChannel()

    await chat.handler.handle(message("text", text="¿cómo quedó?"), channel)
    await chat.handler.handle(message("text", text=yes), channel)

    post = chat.lifecycle.get(SENDER, POST_ID)
    assert post
    return json.loads(model.calls[-1][-1]["result"]), post.status


async def test_a_publish_question_mid_text_does_not_arm_a_bare_yes() -> None:
    question = "¿Lo subo? Antes contame si el precio de la mesa es el correcto, ¿sí?"

    result, status = await answer_with_a_yes(question, "bien")

    assert result == {"error": "approval_not_explicit"}
    assert status == "pending_approval"


async def test_a_publish_question_followed_by_another_does_not_arm_a_bare_yes() -> None:
    result, status = await answer_with_a_yes("¿Lo subo? ¿O preferís otro horario?", "bien")

    assert result == {"error": "approval_not_explicit"}
    assert status == "pending_approval"


COMPOUND = "¡Listo! ¿Te gusta? ¿Lo subo, o le cambio algo?"
SINGLE = "¡Listo! ¿Lo subo así o le cambio algo?"


@pytest.mark.parametrize(
    "yes", ["sí", "dale", "ok", "de una", "bueno", "joya", "👍", "buenísimo, dale"]
)
async def test_a_reply_ending_with_the_publish_question_arms_a_bare_yes(yes: str) -> None:
    result, status = await answer_with_a_yes(SINGLE, yes)

    assert "error" not in result
    assert status != "pending_approval"


@pytest.mark.parametrize("answer", ["sí", "genial"])
async def test_another_question_before_the_publish_question_does_not_arm_a_yes(answer: str) -> None:
    result, status = await answer_with_a_yes(COMPOUND, answer)

    assert result == {"error": "approval_not_explicit"}
    assert status == "pending_approval"


@pytest.mark.parametrize(
    "praise",
    ["genial", "buenísimo", "perfecto", "excelente", "bárbaro", "bien", "está muy bien"],
)
async def test_praise_after_the_publish_question_does_not_approve(praise: str) -> None:
    result, status = await answer_with_a_yes(SINGLE, praise)

    assert result == {"error": "approval_not_explicit"}
    assert status == "pending_approval"


@pytest.mark.parametrize("words", ["subilo", "sí", "dale subilo"])
async def test_subilo_or_a_yes_during_a_revision_publishes_nothing(words: str) -> None:
    """BUG-3: the Owner asked for a change, then said "subilo" before the new version came."""
    revise = call_reply("revise_post", post_id=POST_ID, change="fondo verde", part="images")
    model = ScriptedModel(
        replies=[
            text_reply(SINGLE),
            revise,
            text_reply("Dale, le cambio el fondo ⏳"),
            APPROVE,
            text_reply("Ya casi está la versión nueva ⏳"),
        ]
    )
    gate, channel = asyncio.Event(), FakeChannel()
    chat, background = build(model, CountingImageGen(gate=gate))
    photo = chat.photos.add(SENDER, make_image((800, 1000)), None)
    old = Post(
        POST_ID,
        SENDER,
        [PostImage("/media/a.jpg", b"x")],
        "Mesa de roble",
        style="design",
        source_photos=[photo],
    )
    chat.lifecycle.add(old)

    await chat.handler.handle(message("text", text="¿cómo quedó?"), channel)
    await chat.handler.handle(message("text", text="cambiale el fondo a verde"), channel)
    await chat.handler.handle(message("text", text=words), channel)

    assert json.loads(model.calls[-1][-1]["result"]) == {"error": "revision_in_progress"}
    assert old.status == "revising"
    gate.set()
    await background.join()
    assert old.status == "replaced"
    assert [post.id for post in chat.lifecycle.pending(SENDER)] != [POST_ID]
    assert len(chat.lifecycle.pending(SENDER)) == 1
