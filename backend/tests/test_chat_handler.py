import asyncio
import json
from dataclasses import dataclass, field

import pytest

from app.channels.base import ChannelError, InboundMessage
from app.channels.inbound import EchoHandler
from app.channels.kapso_webhook import parse_message
from app.config import Settings
from app.conversation.chat import ChatHandler
from app.conversation.factory import build_inbound_handler
from app.conversation.history import InMemoryHistory
from app.copy import messages_es
from app.llm.client import LLMError, Reply, Step
from tests.conftest import FIXTURES

SENDER = "59899000001"
REPLY_TEXT = "¡Hola! ¿Qué vendés?"


@dataclass
class FakeChannel:
    sent: list[tuple[str, str]] = field(default_factory=list)
    read: list[tuple[str, bool]] = field(default_factory=list)
    fail_mark_read: bool = False

    async def send_text(self, to: str, text: str) -> str:
        self.sent.append((to, text))
        return "wamid.OUT"

    async def mark_read(self, message_id: str, typing: bool = False) -> None:
        if self.fail_mark_read:
            raise ChannelError("boom")
        self.read.append((message_id, typing))


@dataclass
class FakeModel:
    """Stands in for Gemini: a fixed answer, recording each history it was sent."""

    calls: list[list[Step]] = field(default_factory=list)
    fail: bool = False
    delay_s: float = 0.0

    async def reply(self, agent: str, system: str, history: list[Step], thinking_level: str):
        self.calls.append(history)
        await asyncio.sleep(self.delay_s)
        if self.fail:
            raise LLMError("boom")
        steps = [
            {"type": "thought", "signature": "sig"},
            {"type": "model_output", "content": [{"type": "text", "text": REPLY_TEXT}]},
        ]
        return Reply(text=REPLY_TEXT, steps=steps)


def message(name: str, **changes: object) -> InboundMessage:
    body = json.loads((FIXTURES / f"kapso_message_{name}.json").read_text())["body"]
    return parse_message(body).model_copy(update=changes)


def handler(model: FakeModel) -> ChatHandler:
    return ChatHandler(model, InMemoryHistory(), assistant_name="Mora")


async def test_text_gets_the_model_reply_with_typing() -> None:
    model, channel = FakeModel(), FakeChannel()

    await handler(model).handle(message("text"), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert channel.read == [("wamid.FAKE0000000000000000000001", True)]
    assert model.calls[0][-1]["content"][0]["text"] == "hola bot"


async def test_second_turn_resends_history_with_thought_steps() -> None:
    model, channel = FakeModel(), FakeChannel()
    chat = handler(model)

    await chat.handle(message("text"), channel)
    await chat.handle(message("text", text="vendo muebles"), channel)

    assert [step["type"] for step in model.calls[1]] == [
        "user_input",
        "thought",
        "model_output",
        "user_input",
    ]


async def test_voice_note_is_answered_from_its_transcript() -> None:
    model, channel = FakeModel(), FakeChannel()

    await handler(model).handle(message("audio"), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    sent_text = model.calls[0][-1]["content"][0]["text"]
    assert sent_text == "Quiero un post para la promo del sábado"


async def test_voice_note_without_transcript_asks_again() -> None:
    model, channel = FakeModel(), FakeChannel()
    incoming = message("audio")
    incoming.audio.provider_transcript = None

    await handler(model).handle(incoming, channel)

    assert channel.sent == [(SENDER, messages_es.AUDIO_UNCLEAR)]
    assert model.calls == []


@pytest.mark.parametrize(
    ("fixture", "reply"),
    [
        ("interactive", messages_es.STALE_BUTTON),
        ("image", messages_es.PHOTO_NOT_SAVED_YET),
    ],
)
async def test_other_kinds_get_fixed_messages(fixture: str, reply: str) -> None:
    model, channel = FakeModel(), FakeChannel()

    await handler(model).handle(message(fixture), channel)

    assert channel.sent == [(SENDER, reply)]
    assert model.calls == []


async def test_model_failure_sends_fixed_message_and_keeps_history_clean() -> None:
    model, channel = FakeModel(fail=True), FakeChannel()
    chat = handler(model)

    await chat.handle(message("text"), channel)
    model.fail = False
    await chat.handle(message("text", text="otra vez"), channel)

    assert channel.sent[0] == (SENDER, messages_es.REPLY_FAILED)
    assert [step["type"] for step in model.calls[1]] == ["user_input"]


async def test_a_failing_mark_read_does_not_block_the_reply() -> None:
    channel = FakeChannel(fail_mark_read=True)

    await handler(FakeModel()).handle(message("text"), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]


async def test_messages_from_one_sender_are_answered_in_order() -> None:
    model, channel = FakeModel(delay_s=0.01), FakeChannel()
    chat = handler(model)

    await asyncio.gather(
        chat.handle(message("text", text="uno"), channel),
        chat.handle(message("text", text="dos"), channel),
    )

    # The second turn saw the first one's answer: turns ran one at a time.
    assert len(model.calls[1]) == 4


def test_history_is_trimmed_to_start_with_a_user_turn() -> None:
    history = InMemoryHistory(max_steps=3)
    user: Step = {"type": "user_input"}
    model_step: Step = {"type": "model_output"}

    history.extend(SENDER, [user, model_step, user, model_step])

    assert history.get(SENDER) == [user, model_step]


def test_chat_handler_needs_a_gemini_key() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_inbound_handler(Settings(inbound_handler="chat", gemini_api_key=None))


def test_factory_builds_each_handler() -> None:
    chat = build_inbound_handler(Settings(inbound_handler="chat", gemini_api_key="key"))
    echo = build_inbound_handler(Settings(inbound_handler="echo"))

    assert isinstance(chat, ChatHandler)
    assert isinstance(echo, EchoHandler)
