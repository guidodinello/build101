"""A bare "sí" approves only the post the assistant's reply ended by asking to publish (#107)."""

import json

import pytest

from app.conversation.events import BrandSummaryReady, Event, JobFailed
from app.posts.store import Post, PostImage
from tests.fakes import FakeChannel, ScriptedModel, call_reply, text_reply
from tests.test_chat_handler import JOB_UUID, SENDER, build, message

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


async def test_a_reply_ending_with_the_publish_question_arms_a_bare_yes() -> None:
    result, status = await answer_with_a_yes("¡Listo! ¿Te gusta? ¿Lo subo, o le cambio algo?", "sí")

    assert "error" not in result
    assert status != "pending_approval"


@pytest.mark.parametrize(
    "event",
    [BrandSummaryReady("Katei", "• cálidos"), JobFailed(JOB_UUID, "generate_brand")],
    ids=lambda event: type(event).__name__,
)
async def test_a_verbatim_event_after_the_publish_question_disarms_a_bare_yes(
    event: Event,
) -> None:
    model = ScriptedModel(replies=[text_reply("¿Lo subo?"), APPROVE, text_reply("ok")])
    chat, _ = build(model)
    chat.lifecycle.add(Post(POST_ID, SENDER, [PostImage("/media/a.jpg", b"x")], "Mesa de roble"))
    channel = FakeChannel()
    await chat.handler.handle(message("text", text="¿cómo quedó?"), channel)

    await chat.notify(SENDER, event, channel)
    await chat.handler.handle(message("text", text="sí"), channel)

    assert json.loads(model.calls[-1][-1]["result"]) == {"error": "approval_not_explicit"}
    post = chat.lifecycle.get(SENDER, POST_ID)
    assert post
    assert post.status == "pending_approval"
