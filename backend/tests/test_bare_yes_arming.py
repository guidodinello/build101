"""A bare "sí" approves only the post the assistant's reply ended by asking to publish (#107)."""

import json

from app.posts.store import Post, PostImage
from tests.fakes import FakeChannel, ScriptedModel, call_reply, text_reply
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


async def test_a_reply_ending_with_the_publish_question_arms_a_bare_yes() -> None:
    result, status = await answer_with_a_yes("¡Listo! ¿Te gusta? ¿Lo subo, o le cambio algo?", "sí")

    assert "error" not in result
    assert status != "pending_approval"
