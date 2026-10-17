import json
from dataclasses import dataclass, field

import pytest

from app.channels.base import ChannelError, InboundMessage
from app.channels.inbound import EchoHandler, InMemoryDedupeStore
from app.channels.kapso_webhook import parse_message
from tests.conftest import FIXTURES


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


def message(name: str) -> InboundMessage:
    body = json.loads((FIXTURES / f"kapso_message_{name}.json").read_text())["body"]
    return parse_message(body)


@pytest.mark.parametrize(
    ("fixture", "reply"),
    [
        ("text", "Recibí: hola bot"),
        ("interactive", 'Tocaste "Publicar" (post_approve:00000000-0000-0000-0000-000000000001)'),
        ("image", "Recibí una foto (foto de prueba)"),
        ("audio", 'Recibí un audio: "Quiero un post para la promo del sábado"'),
    ],
)
async def test_echo_replies_per_kind(fixture: str, reply: str) -> None:
    channel = FakeChannel()

    await EchoHandler().handle(message(fixture), channel)

    assert channel.sent == [("59899000001", reply)]
    assert channel.read == [("wamid.FAKE0000000000000000000001", True)]


async def test_audio_without_transcript_says_so() -> None:
    incoming = message("audio")
    incoming.audio.provider_transcript = None
    channel = FakeChannel()

    await EchoHandler().handle(incoming, channel)

    assert channel.sent == [("59899000001", "Recibí un audio sin transcripción")]


async def test_a_failing_mark_read_does_not_block_the_reply() -> None:
    channel = FakeChannel(fail_mark_read=True)

    await EchoHandler().handle(message("text"), channel)

    assert channel.sent == [("59899000001", "Recibí: hola bot")]


async def test_dedupe_store_is_bounded_and_evicts_the_oldest_key() -> None:
    store = InMemoryDedupeStore(max_keys=2)

    assert await store.first_seen("a")
    assert await store.first_seen("b")
    assert not await store.first_seen("a")
    assert await store.first_seen("c")  # evicts "a"
    assert await store.first_seen("a")
    assert not await store.first_seen("c")
