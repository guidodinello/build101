import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import ChannelError, ChannelPort, InboundMessage
from app.channels.inbound import InMemoryDedupeStore
from app.channels.router import (
    get_channel,
    get_clock,
    get_conversation,
    get_dedupe_store,
    get_inbound_handler,
)
from app.config import Settings, get_settings
from app.conversation.events import Event
from app.conversation.factory import Conversation
from app.conversation.onboarding import OnboardingGate
from app.copy import messages_es
from app.db.models import Business, Job, MagicLink, PilotSender
from app.db.session import create_engine
from app.main import app
from app.pilot import (
    PILOT_LIST_TTL_S,
    WAITLIST_REPLY_EVERY_S,
    PilotGate,
    PilotList,
    build_pilot_list,
    configured_numbers,
    get_pilot_list,
)
from app.ratelimit import TURNS_BURST
from tests.conftest import requires_db, sign
from tests.fakes import CountingImageGen, FakeChannel, ScriptedModel
from tests.test_chat_handler import build, message
from tests.test_ratelimit import Clock
from tests.test_whatsapp_router import FIXTURE_TIME, SECRET, post, raw_fixture

STRANGER = "59899000001"  # the fixtures' sender
PILOT = "59899000002"
ASSISTANT = "Mora"
WAITLIST = messages_es.waitlist(ASSISTANT)
KINDS = ("text", "audio", "image", "album", "button")
# Nothing listens there, so asyncpg's connect fails as it does for a database that is down.
UNREACHABLE_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:1/nothing"


@dataclass
class RecordingHandler:
    handled: list[InboundMessage] = field(default_factory=list)

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        self.handled.append(message)


def inbound(kind: str, sender: str = STRANGER, message_id: str = "wamid.1") -> InboundMessage:
    """Each kind as Kapso delivers it; an album announcement has no fixture of its own."""
    if kind == "album":
        return InboundMessage(
            kind="album", message_id=message_id, sender=sender, phone_number_id="1", raw={}
        )
    fixture = "interactive" if kind == "button" else kind
    return message(fixture, sender=sender, message_id=message_id)


def pilot_list(*numbers: str, clock: Clock | None = None) -> PilotList:
    return PilotList(frozenset(numbers), None, open_when_empty=False, clock=clock or Clock())


def gated(
    *numbers: str, clock: Clock | None = None, max_keys: int = 100
) -> tuple[PilotGate, RecordingHandler]:
    inner = RecordingHandler()
    clock = clock or Clock()
    gate = PilotGate(inner, pilot_list(*numbers), WAITLIST, max_keys=max_keys, clock=clock)
    return gate, inner


async def test_numbers_match_whatever_their_formatting() -> None:
    pilot = PilotList(
        configured_numbers(" +598 99 000 002, 598 99 000 003 ,,"), None, open_when_empty=False
    )

    assert await pilot.numbers() == {"59899000002", "59899000003"}
    assert await pilot.allows("59899000002")
    assert await pilot.allows("+598 99 000 003")
    assert not await pilot.allows(STRANGER)


async def test_an_empty_list_lets_everyone_in_outside_production_and_nobody_in_it() -> None:
    local = build_pilot_list(Settings(env="local"))
    prod = build_pilot_list(Settings(env="prod"))
    configured = build_pilot_list(Settings(env="prod", pilot_senders="+598 99 000 002"))

    assert await local.allows(STRANGER)
    assert not await prod.allows(STRANGER)
    assert await configured.allows(PILOT)
    assert not await configured.allows(STRANGER)


async def test_the_boot_log_warns_when_production_lets_nobody_in(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="app.pilot"):
        await build_pilot_list(Settings(env="prod")).log_at_boot()
        await build_pilot_list(Settings(env="local")).log_at_boot()
        await build_pilot_list(Settings(env="prod", pilot_senders=PILOT)).log_at_boot()

    warning, local, configured = caplog.records
    assert warning.levelno == logging.WARNING
    assert "nobody gets in" in warning.getMessage()
    assert (local.levelno, "everyone gets in" in local.getMessage()) == (logging.INFO, True)
    assert configured.getMessage() == "pilot list: 1 numbers get in"
    assert PILOT not in caplog.text


def boot(pilot: PilotList) -> None:
    get_channel.cache_clear()
    app.dependency_overrides[get_inbound_handler] = RecordingHandler
    app.dependency_overrides[get_pilot_list] = lambda: pilot
    try:
        with TestClient(app):
            pass
    finally:
        app.dependency_overrides.clear()


def test_the_app_says_at_boot_that_nobody_gets_in(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.pilot"):
        boot(build_pilot_list(Settings(env="prod")))

    assert "pilot list is empty with ENV=prod: nobody gets in" in caplog.text


def unreachable_sessions() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(create_engine(UNREACHABLE_DATABASE_URL))


def test_the_app_boots_with_the_database_unreachable(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="app.pilot"):
        boot(PilotList(frozenset(), unreachable_sessions(), open_when_empty=False))

    assert "pilot_senders could not be read at boot" in caplog.text


@pytest.mark.parametrize("kind", KINDS)
async def test_a_number_on_the_list_reaches_the_agency(kind: str) -> None:
    gate, inner = gated(PILOT)
    channel = FakeChannel()

    await gate.handle(inbound(kind, sender=PILOT), channel)

    assert [m.kind for m in inner.handled] == [kind]
    assert channel.sent == []


@pytest.mark.parametrize("kind", KINDS)
async def test_a_number_not_on_the_list_gets_the_waitlist_reply_and_nothing_else(
    kind: str,
) -> None:
    gate, inner = gated(PILOT)
    channel = FakeChannel()

    await gate.handle(inbound(kind), channel)

    assert inner.handled == []
    assert channel.sent == [(STRANGER, WAITLIST)]
    assert channel.read == []
    assert channel.downloads == []


async def test_the_waitlist_reply_goes_out_at_most_once_a_day() -> None:
    clock = Clock()
    gate, inner = gated(PILOT, clock=clock)
    channel = FakeChannel()

    for number, kind in enumerate(KINDS * 4):
        await gate.handle(inbound(kind, message_id=f"wamid.{number}"), channel)
    clock.now += WAITLIST_REPLY_EVERY_S - 1
    await gate.handle(inbound("text"), channel)
    assert len(channel.sent) == 1

    clock.now += 1
    await gate.handle(inbound("text"), channel)
    assert channel.sent == [(STRANGER, WAITLIST)] * 2
    assert inner.handled == []


async def test_many_numbers_writing_at_once_keep_memory_bounded() -> None:
    gate, _ = gated(PILOT, max_keys=3)
    channel = FakeChannel()

    for number in range(50):
        await gate.handle(inbound("text", sender=f"5989910{number:04d}"), channel)

    assert len(gate._replied) == 3
    assert len(channel.sent) == 50  # one each: none of them wrote twice


async def test_a_failing_waitlist_reply_does_not_break_the_webhook_task() -> None:
    class BrokenChannel(FakeChannel):
        async def send_text(self, to: str, text: str) -> str:
            raise ChannelError("kapso 500")

    gate, inner = gated(PILOT)

    await gate.handle(inbound("text"), BrokenChannel())

    assert inner.handled == []


@dataclass
class FlakyChannel(FakeChannel):
    failures: int = 1

    async def send_text(self, to: str, text: str) -> str:
        if self.failures:
            self.failures -= 1
            raise ChannelError("kapso 500")
        return await super().send_text(to, text)


async def test_a_failed_waitlist_reply_goes_out_on_the_next_message() -> None:
    gate, _ = gated(PILOT)
    channel = FlakyChannel()

    await gate.handle(inbound("text", message_id="wamid.1"), channel)
    assert channel.sent == []

    await gate.handle(inbound("text", message_id="wamid.2"), channel)
    await gate.handle(inbound("text", message_id="wamid.3"), channel)
    assert channel.sent == [(STRANGER, WAITLIST)]


async def test_messages_arriving_together_get_one_waitlist_reply() -> None:
    class SlowChannel(FakeChannel):
        async def send_text(self, to: str, text: str) -> str:
            await asyncio.sleep(0)
            return await super().send_text(to, text)

    gate, _ = gated(PILOT)
    channel = SlowChannel()

    await asyncio.gather(
        *(gate.handle(inbound(kind, message_id=f"wamid.{kind}"), channel) for kind in KINDS)
    )

    assert channel.sent == [(STRANGER, WAITLIST)]


async def test_the_log_lines_mask_the_number(caplog: pytest.LogCaptureFixture) -> None:
    gate, _ = gated(PILOT)

    with caplog.at_level(logging.INFO, logger="app.pilot"):
        await gate.handle(inbound("text"), FakeChannel())
        await gate.handle(inbound("audio"), FakeChannel())

    assert len(caplog.records) == 2
    assert "***0001" in caplog.text
    assert STRANGER not in caplog.text


async def test_an_off_list_reaction_is_read_and_gets_only_the_waitlist_reply() -> None:
    gate, inner = gated(PILOT)
    channel = FakeChannel()
    reaction = inbound("text", message_id="wamid.reaction").model_copy(
        update={
            "kind": "reaction",
            "reaction_emoji": "👍",
            "reaction_message_id": "wamid.target",
        }
    )

    await gate.handle(reaction, channel)

    assert inner.handled == []
    assert channel.read == [("wamid.reaction", False)]
    assert channel.sent == [(STRANGER, WAITLIST)]


async def test_an_off_list_reaction_is_read_even_when_waitlist_reply_was_recent() -> None:
    gate, inner = gated(PILOT)
    channel = FakeChannel()
    first = inbound("text", message_id="wamid.first").model_copy(update={"kind": "reaction"})
    second = inbound("text", message_id="wamid.second").model_copy(update={"kind": "reaction"})

    await gate.handle(first, channel)
    await gate.handle(second, channel)

    assert inner.handled == []
    assert channel.read == [("wamid.first", False), ("wamid.second", False)]
    assert channel.sent == [(STRANGER, WAITLIST)]


class BrokenSessions:
    def __call__(self) -> AsyncSession:
        raise OperationalError("select", {}, Exception("database down"))


@pytest.mark.parametrize(
    "down", [BrokenSessions, unreachable_sessions], ids=lambda down: down.__name__
)
async def test_without_a_list_read_yet_a_database_failure_drops_the_message(
    down: Callable[[], Callable[[], AsyncSession]], caplog: pytest.LogCaptureFixture
) -> None:
    inner = RecordingHandler()
    pilot = PilotList(frozenset(), down(), open_when_empty=True)
    gate = PilotGate(inner, pilot, WAITLIST)
    channel = FakeChannel()

    with caplog.at_level(logging.ERROR, logger="app.pilot"):
        await gate.handle(inbound("text"), channel)

    assert inner.handled == []
    assert channel.sent == []
    assert "pilot list unavailable" in caplog.text
    assert STRANGER not in caplog.text


async def test_without_a_database_no_ai_call_happens_for_a_number_not_on_the_list() -> None:
    model, image_gen, channel = ScriptedModel(), CountingImageGen(), FakeChannel()
    chat, background = build(model, image_gen)
    gate = PilotGate(chat.handler, pilot_list(PILOT), WAITLIST)

    for number, kind in enumerate(KINDS):
        await gate.handle(inbound(kind, message_id=f"wamid.{number}"), channel)
    await background.join()

    assert model.calls == []
    assert model.structured_calls == []
    assert image_gen.calls == []
    assert channel.downloads == []
    assert channel.sent == [(STRANGER, WAITLIST)]

    await gate.handle(inbound("text", sender=PILOT, message_id="wamid.pilot"), channel)
    assert len(model.calls) == 1
    assert channel.sent[-1][0] == PILOT


def test_the_webhook_puts_the_pilot_list_in_front_of_the_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Guard for #186: goes red if the webhook's handler stops checking the pilot list first.

    Only the factory's handler, the list, the channel and the dedupe store are replaced;
    `get_conversation`, which puts the gate in front, is the real one. Past the rate limit's burst
    the stranger still gets one waitlist reply and never the rate limit's notice.
    """
    inner = RecordingHandler()
    channel = FakeChannel()

    async def notify(sender: str, event: Event, channel: ChannelPort) -> None:
        pass

    monkeypatch.setattr(
        "app.channels.router.build_conversation",
        lambda *args: Conversation(handler=inner, notify=notify),
    )
    monkeypatch.setattr("app.channels.router.get_pilot_list", lambda: pilot_list(PILOT))
    get_conversation.cache_clear()
    store = InMemoryDedupeStore()
    app.dependency_overrides[get_settings] = lambda: Settings(kapso_webhook_secret=SECRET)
    app.dependency_overrides[get_dedupe_store] = lambda: store
    app.dependency_overrides[get_clock] = lambda: float(FIXTURE_TIME)
    app.dependency_overrides[get_channel] = lambda: channel
    body = json.loads(raw_fixture("text"))
    try:
        with TestClient(app) as test_client:
            for number in range(TURNS_BURST + 1):
                body["message"]["id"] = f"wamid.{number}"
                raw = json.dumps(body).encode()
                assert post(test_client, raw, signature=sign(raw, SECRET)).status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_conversation.cache_clear()

    assert inner.handled == []
    assert channel.sent == [(STRANGER, messages_es.waitlist(Settings().assistant_name))]


@requires_db
async def test_the_table_lets_a_number_in_and_out_within_a_minute(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    clock = Clock()
    pilot = PilotList(frozenset(), sessions, open_when_empty=False, clock=clock)
    assert not await pilot.allows(PILOT)

    async with sessions() as db:
        db.add(PilotSender(phone=PILOT))
        await db.commit()
    clock.now += PILOT_LIST_TTL_S
    assert await pilot.allows("+598 99 000 002")
    assert not await pilot.allows(STRANGER)

    async with sessions() as db:
        await db.delete(await db.get_one(PilotSender, PILOT))
        await db.commit()
    clock.now += PILOT_LIST_TTL_S - 1
    assert await pilot.allows(PILOT)  # still the list read a moment ago
    clock.now += 1
    assert not await pilot.allows(PILOT)


@requires_db
async def test_the_table_takes_digits_only(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as db:
        db.add(PilotSender(phone="+598 99 000 002"))
        with pytest.raises(IntegrityError):
            await db.commit()


@dataclass
class FlakySessions:
    sessions: async_sessionmaker[AsyncSession]
    down: bool = False
    unreachable: async_sessionmaker[AsyncSession] = field(default_factory=unreachable_sessions)

    def __call__(self) -> AsyncSession:
        return self.unreachable() if self.down else self.sessions()


@requires_db
async def test_a_failed_read_keeps_the_last_list(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        db.add(PilotSender(phone=PILOT))
        await db.commit()
    clock, flaky = Clock(), FlakySessions(sessions)
    pilot = PilotList(frozenset(), flaky, open_when_empty=False, clock=clock)
    assert await pilot.allows(PILOT)

    flaky.down = True
    clock.now += PILOT_LIST_TTL_S

    assert await pilot.allows(PILOT)
    assert not await pilot.allows(STRANGER)


@requires_db
async def test_with_no_list_read_a_configured_number_gets_in_while_the_database_is_down(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    listed = "59899000003"
    async with sessions() as db:
        db.add(PilotSender(phone=listed))
        await db.commit()
    flaky = FlakySessions(sessions, down=True)
    inner = RecordingHandler()
    pilot = PilotList(frozenset({PILOT}), flaky, open_when_empty=True)
    gate = PilotGate(inner, pilot, WAITLIST)
    channel = FakeChannel()

    await gate.handle(inbound("text", sender=PILOT), channel)
    await gate.handle(inbound("text", sender=listed), channel)
    assert [m.sender for m in inner.handled] == [PILOT]
    assert channel.sent == []

    flaky.down = False
    await gate.handle(inbound("text", sender=listed), channel)
    await gate.handle(inbound("text", sender=STRANGER), channel)
    assert [m.sender for m in inner.handled] == [PILOT, listed]
    assert channel.sent == [(STRANGER, WAITLIST)]


@pytest.fixture
def onboarding_rig(
    sessions: async_sessionmaker[AsyncSession],
) -> tuple[PilotGate, RecordingHandler]:
    chat = RecordingHandler()
    pilot = PilotList(frozenset(), sessions, open_when_empty=False)
    onboarding = OnboardingGate(chat, sessions, "https://app.test", ASSISTANT)
    return PilotGate(onboarding, pilot, WAITLIST), chat


async def counts(sessions: async_sessionmaker[AsyncSession]) -> tuple[int, int, int]:
    async with sessions() as db:
        businesses = await db.scalar(select(func.count()).select_from(Business))
        links = await db.scalar(select(func.count()).select_from(MagicLink))
        jobs = await db.scalar(select(func.count()).select_from(Job))
    return businesses or 0, links or 0, jobs or 0


@requires_db
async def test_with_the_database_a_number_not_on_the_list_gets_no_business_link_or_job(
    sessions: async_sessionmaker[AsyncSession],
    onboarding_rig: tuple[PilotGate, RecordingHandler],
) -> None:
    gate, chat = onboarding_rig
    channel = FakeChannel()
    async with sessions() as db:
        db.add(PilotSender(phone=PILOT))
        await db.commit()

    for number, kind in enumerate(KINDS):
        await gate.handle(inbound(kind, message_id=f"wamid.{number}"), channel)

    assert await counts(sessions) == (0, 0, 0)
    assert chat.handled == []
    assert channel.sent == [(STRANGER, WAITLIST)]

    await gate.handle(inbound("text", sender=PILOT), channel)
    assert channel.sent[-1] == (PILOT, messages_es.welcome(ASSISTANT))
    assert (await counts(sessions))[0] == 1


@requires_db
async def test_a_business_taken_off_the_list_gets_the_waitlist_reply_and_keeps_its_data(
    sessions: async_sessionmaker[AsyncSession],
    onboarding_rig: tuple[PilotGate, RecordingHandler],
) -> None:
    gate, chat = onboarding_rig
    channel = FakeChannel()
    async with sessions() as db:
        db.add(Business(owner_phone=STRANGER, name="Muebles Ramírez", onboarding_state="active"))
        db.add(PilotSender(phone=PILOT))
        await db.commit()

    for number, kind in enumerate(KINDS):
        await gate.handle(inbound(kind, message_id=f"wamid.{number}"), channel)

    assert chat.handled == []
    assert channel.sent == [(STRANGER, WAITLIST)]
    async with sessions() as db:
        business = await db.scalar(select(Business).where(Business.owner_phone == STRANGER))
    assert business is not None
    assert (business.name, business.onboarding_state) == ("Muebles Ramírez", "active")
