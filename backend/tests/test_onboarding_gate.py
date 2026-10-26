import asyncio
import json
import time
from dataclasses import dataclass, field

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import ChannelPort, InboundMessage
from app.channels.kapso_webhook import parse_message
from app.conversation import onboarding
from app.conversation.onboarding import OnboardingGate
from app.copy import messages_es
from app.db.models import Business, MagicLink
from tests.conftest import FIXTURES, requires_db
from tests.fakes import FakeChannel

pytestmark = requires_db

PHONE = "59899000001"
FRONTEND = "https://app.test"
ASSISTANT = "Mora"


def message(name: str, **changes: object) -> InboundMessage:
    body = json.loads((FIXTURES / f"kapso_message_{name}.json").read_text())["body"]
    return parse_message(body).model_copy(update=changes)


def text(words: str, timestamp: int | None = None) -> InboundMessage:
    return message("text", text=words, timestamp=timestamp)


def after_the_welcome() -> int:
    return int(time.time()) + 1


@dataclass
class FakeChat:
    handled: list[InboundMessage] = field(default_factory=list)

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        self.handled.append(message)


@dataclass
class Rig:
    gate: OnboardingGate
    chat: FakeChat
    channel: FakeChannel
    sessions: async_sessionmaker[AsyncSession]

    async def business(self) -> Business:
        async with self.sessions() as db:
            return await db.scalar(select(Business).where(Business.owner_phone == PHONE))

    async def links(self) -> int:
        async with self.sessions() as db:
            return await db.scalar(select(func.count()).select_from(MagicLink))

    def replies(self) -> list[str]:
        return [reply for _, reply in self.channel.sent]


@pytest.fixture
def rig(sessions: async_sessionmaker[AsyncSession]) -> Rig:
    chat = FakeChat()
    return Rig(OnboardingGate(chat, sessions, FRONTEND, ASSISTANT), chat, FakeChannel(), sessions)


async def add_business(rig: Rig, state: str) -> None:
    async with rig.sessions() as db:
        db.add(Business(owner_phone=PHONE, name="Muebles Ramírez", onboarding_state=state))
        await db.commit()


async def test_an_unknown_number_gets_the_welcome(rig: Rig) -> None:
    await rig.gate.handle(text("Hola"), rig.channel)

    assert rig.replies() == [messages_es.welcome(ASSISTANT)]
    assert (await rig.business()).onboarding_state == "awaiting_name"
    assert rig.chat.handled == []


async def test_a_reaction_during_onboarding_is_silent_and_never_becomes_the_name(
    rig: Rig,
) -> None:
    reaction = message("text", kind="reaction", reaction_emoji="👍")

    await rig.gate.handle(reaction, rig.channel)

    assert rig.channel.sent == []
    assert rig.channel.read == [(reaction.message_id, False)]
    assert await rig.business() is None
    assert rig.chat.handled == []


async def test_the_name_is_saved_and_the_link_sent(rig: Rig) -> None:
    await rig.gate.handle(text("Hola"), rig.channel)
    await rig.gate.handle(text("  Muebles Ramírez ", after_the_welcome()), rig.channel)

    business = await rig.business()
    assert business.name == "Muebles Ramírez"
    assert business.onboarding_state == "awaiting_web_form"
    assert await rig.links() == 1
    reply = rig.replies()[-1]
    assert reply.startswith("¡Buenísimo, Muebles Ramírez!")
    assert f"{FRONTEND}/o/" in reply
    assert rig.chat.handled == []


async def test_a_message_written_before_the_welcome_is_not_the_name(rig: Rig) -> None:
    sent_at = int(time.time())  # the same second as the welcome
    await rig.gate.handle(text("Hola", sent_at), rig.channel)
    await rig.gate.handle(text("¿Hay alguien?", sent_at), rig.channel)

    assert rig.replies() == [messages_es.welcome(ASSISTANT)]
    business = await rig.business()
    assert business.name is None
    assert business.onboarding_state == "awaiting_name"


async def test_a_voice_note_transcript_is_the_name(rig: Rig) -> None:
    await add_business(rig, "awaiting_name")

    await rig.gate.handle(message("audio"), rig.channel)

    assert (await rig.business()).name == "Quiero un post para la promo del sábado"
    assert (await rig.business()).onboarding_state == "awaiting_web_form"


async def test_a_photo_instead_of_the_name_asks_again(rig: Rig) -> None:
    await add_business(rig, "awaiting_name")

    await rig.gate.handle(message("image", text=None), rig.channel)

    assert rig.replies() == [messages_es.welcome(ASSISTANT)]
    assert (await rig.business()).onboarding_state == "awaiting_name"
    assert await rig.links() == 0


async def test_an_album_instead_of_the_name_asks_again_once(rig: Rig) -> None:
    await add_business(rig, "awaiting_name")

    await rig.gate.handle(message("image", text=None), rig.channel)
    await rig.gate.handle(message("image", text=None), rig.channel)

    assert rig.replies() == [messages_es.welcome(ASSISTANT)]


async def test_writing_before_the_form_resends_a_link_once(rig: Rig) -> None:
    await add_business(rig, "awaiting_web_form")

    await rig.gate.handle(text("¿y ahora?"), rig.channel)
    await rig.gate.handle(message("image"), rig.channel)

    [reply] = rig.replies()
    assert reply.startswith("Para arrancar me falta")
    assert f"{FRONTEND}/o/" in reply
    assert await rig.links() == 1
    assert rig.chat.handled == []


async def test_the_reminder_comes_back_after_the_cooldown(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    chat = FakeChat()
    gate = OnboardingGate(chat, sessions, FRONTEND, ASSISTANT, reminder_cooldown_s=0)
    rig = Rig(gate, chat, FakeChannel(), sessions)
    await add_business(rig, "awaiting_web_form")

    await rig.gate.handle(text("hola"), rig.channel)
    await rig.gate.handle(text("hola?"), rig.channel)

    assert len(rig.replies()) == 2
    assert await rig.links() == 2


@pytest.mark.parametrize("state", ["generating_brand", "awaiting_brand_confirmation", "active"])
async def test_after_the_form_the_chat_answers(rig: Rig, state: str) -> None:
    await add_business(rig, state)
    hello = text("armame un post")

    await rig.gate.handle(hello, rig.channel)

    assert rig.chat.handled == [hello]
    assert rig.channel.sent == []
    assert (await rig.business()).onboarding_state == state


async def test_two_first_messages_at_once_make_one_business(rig: Rig) -> None:
    sent_at = int(time.time())
    await asyncio.gather(
        rig.gate.handle(text("Hola", sent_at), rig.channel),
        rig.gate.handle(text("¿Hay alguien?", sent_at), rig.channel),
    )

    async with rig.sessions() as db:
        count = await db.scalar(select(func.count()).select_from(Business))
    assert count == 1
    assert rig.replies() == [messages_es.welcome(ASSISTANT)]


async def test_the_per_sender_state_stays_bounded_under_many_numbers(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(onboarding, "MAX_TRACKED_KEYS", 3)
    chat, channel = FakeChat(), FakeChannel()
    gate = OnboardingGate(chat, sessions, FRONTEND, ASSISTANT)

    for number in range(10):
        await gate.handle(message("text", text="Hola", sender=f"598990000{number:02d}"), channel)

    assert len(channel.sent) == 10  # every number still got its welcome
    assert len(gate._welcomed_at) == 3
    assert len(gate._last_prompt) == 3
    assert len(gate._locks) == 0  # no lock outlives its turn
