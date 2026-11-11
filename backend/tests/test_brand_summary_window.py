"""The brand summary and WhatsApp's 24 h window (#204)."""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import ChannelPort, InboundMessage
from app.channels.kapso_webhook import failure_codes
from app.conversation.brand import BrandFlow
from app.conversation.brand_summary import window_open
from app.conversation.events import BrandSummaryReady
from app.conversation.history import DbHistory
from app.conversation.onboarding import OnboardingGate
from app.conversation.outbound import FixedReplies
from app.copy import messages_es
from app.db.models import BrandBrainVersion, Business
from app.jobs.brand import generate_brand
from app.jobs.runner import JobContext
from app.knowledge.db import DbKnowledge
from app.llm.client import user_step
from tests.conftest import requires_db
from tests.fakes import FakeChannel, SequenceModel, brand_brain

PHONE = "59899123456"
SUMMARY = "• *Cómo hablamos:* cálidos"


def test_the_window_is_24_hours_from_the_last_message() -> None:
    now = datetime(2026, 10, 28, 12, tzinfo=UTC)

    assert window_open(now - timedelta(hours=23, minutes=59), now)
    assert not window_open(now - timedelta(hours=24), now)
    assert not window_open(None, now)


def test_failure_codes_are_read_wherever_the_errors_array_is() -> None:
    payload = {
        "message": {
            "id": "wamid.OUT",
            "kapso": {"statuses": [{"status": "failed", "errors": [{"code": 131047}]}]},
        },
        "errors": [{"code": "131026", "title": "undeliverable"}, {"title": "no code"}],
    }

    assert sorted(failure_codes(payload)) == ["131026", "131047"]
    assert failure_codes({"message": {"id": "wamid.OUT"}}) == []


@dataclass
class FakeChat:
    handled: list[InboundMessage] = field(default_factory=list)
    sent_before: list[int] = field(default_factory=list)
    channel: FakeChannel = field(default_factory=FakeChannel)

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        # How many buttons messages had gone out when the chat got the message.
        self.sent_before.append(len(self.channel.buttons))
        self.handled.append(message)


@dataclass
class Rig:
    sessions: async_sessionmaker[AsyncSession]
    chat: FakeChat
    gate: OnboardingGate
    history: DbHistory

    @property
    def channel(self) -> FakeChannel:
        return self.chat.channel

    async def write(self, words: str = "Listo", at: datetime | None = None) -> None:
        sent = at or datetime.now(UTC)
        message = InboundMessage(
            message_id=f"wamid.{uuid.uuid4().hex}",
            sender=PHONE,
            phone_number_id="123",
            kind="text",
            text=words,
            timestamp=int(sent.timestamp()),
            raw={},
        )
        await self.gate.handle(message, self.channel)

    async def generate(self, **payload: Any) -> dict[str, Any]:
        business = await self.business()
        context = JobContext(
            uuid.uuid4(),
            business.id,
            self.sessions,
            None,  # type: ignore[arg-type]
            self.channel,
            SequenceModel([brand_brain(whatsapp_summary=SUMMARY)]),
            FixedReplies(self.history),
        )
        return await generate_brand(context, payload)

    async def business(self) -> Business:
        async with self.sessions() as db:
            return await db.scalar(select(Business).where(Business.owner_phone == PHONE))

    async def summary_sent(self) -> bool:
        async with self.sessions() as db:
            sent_at = await db.scalar(
                select(BrandBrainVersion.summary_sent_at)
                .order_by(BrandBrainVersion.version.desc())
                .limit(1)
            )
        return sent_at is not None

    def summaries(self) -> list[str]:
        return [body for _, body, ids in self.channel.buttons if ids == ["brand_ok", "brand_fix"]]


@pytest.fixture
def rig(sessions: async_sessionmaker[AsyncSession]) -> Rig:
    chat, history = FakeChat(), DbHistory(sessions)
    gate = OnboardingGate(chat, FixedReplies(history), sessions, "https://app.test", "Mora")
    return Rig(sessions, chat, gate, history)


async def add_business(rig: Rig, last_inbound_at: datetime | None) -> None:
    async with rig.sessions() as db:
        db.add(
            Business(
                owner_phone=PHONE,
                name="Katei",
                onboarding_state="generating_brand",
                last_inbound_at=last_inbound_at,
            )
        )
        await db.commit()


SUMMARY_TEXT = messages_es.brand_summary("Katei", SUMMARY)
SUMMARY_NOTE = user_step(BrandSummaryReady("Katei", SUMMARY).note())


@requires_db
async def test_inside_the_window_the_summary_goes_out_at_once(rig: Rig) -> None:
    await add_business(rig, datetime.now(UTC) - timedelta(hours=23))

    await rig.generate()

    assert rig.summaries() == [SUMMARY_TEXT]
    assert await rig.summary_sent()
    assert await rig.history.get(PHONE) == [SUMMARY_NOTE]


@requires_db
@pytest.mark.parametrize("last_inbound", [timedelta(hours=25), None], ids=["old", "never"])
async def test_outside_the_window_the_summary_waits(
    rig: Rig, last_inbound: timedelta | None
) -> None:
    await add_business(rig, datetime.now(UTC) - last_inbound if last_inbound else None)

    result = await rig.generate()

    assert result == {"version": 1, "summary": "pending"}
    assert rig.channel.sent == []
    assert not await rig.summary_sent()
    # Nothing tells the orchestrator the Owner saw it.
    assert await rig.history.get(PHONE) == []
    known = await DbKnowledge(rig.sessions).of(PHONE)
    assert known.brand is not None and not known.brand_summary_sent
    assert (await rig.business()).onboarding_state == "awaiting_brand_confirmation"


@requires_db
async def test_the_next_message_brings_the_summary_first_then_once(rig: Rig) -> None:
    await add_business(rig, datetime.now(UTC) - timedelta(days=2))
    await rig.generate()

    await rig.write("Listo")

    assert rig.summaries() == [SUMMARY_TEXT]
    # The summary went out before the chat handled the message.
    assert rig.chat.sent_before == [1]
    assert await rig.history.get(PHONE) == [SUMMARY_NOTE]
    assert (await DbKnowledge(rig.sessions).of(PHONE)).brand_summary_sent

    await rig.write("¿Hola?")

    assert rig.summaries() == [SUMMARY_TEXT]
    assert len(rig.chat.handled) == 2
    # "Sí, es mi marca" then activates the Business.
    assert await BrandFlow(rig.sessions).confirm(PHONE)
    assert (await rig.business()).onboarding_state == "active"


@requires_db
async def test_a_message_while_the_brand_is_studied_opens_the_window(rig: Rig) -> None:
    await add_business(rig, None)

    await rig.write("Listo")
    await rig.generate()

    assert rig.summaries() == [SUMMARY_TEXT]
    assert rig.chat.sent_before == [0]


@requires_db
async def test_the_last_message_time_survives_a_restart(
    rig: Rig, sessions: async_sessionmaker[AsyncSession]
) -> None:
    await add_business(rig, None)
    written = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=5)

    await rig.write("Listo", at=written)

    async with sessions() as db:
        business = await db.scalar(select(Business).where(Business.owner_phone == PHONE))
    assert business and business.last_inbound_at == written


@requires_db
async def test_an_older_message_handled_late_doesnt_close_the_window(rig: Rig) -> None:
    await add_business(rig, None)
    now = datetime.now(UTC).replace(microsecond=0)

    await rig.write("segundo", at=now)
    await rig.write("primero", at=now - timedelta(minutes=1))

    assert (await rig.business()).last_inbound_at == now


@requires_db
async def test_the_summary_after_a_correction_follows_the_same_rules(rig: Rig) -> None:
    await add_business(rig, datetime.now(UTC))
    await rig.generate()
    async with rig.sessions() as db:
        business = await db.scalar(select(Business).where(Business.owner_phone == PHONE))
        assert business
        business.last_inbound_at = datetime.now(UTC) - timedelta(days=3)
        business.onboarding_state = "generating_brand"
        await db.commit()

    result = await rig.generate(correction="más formales")

    assert result == {"version": 2, "summary": "pending"}
    assert rig.summaries() == [SUMMARY_TEXT]

    await rig.write("dale")

    assert rig.summaries() == [SUMMARY_TEXT, SUMMARY_TEXT]


@requires_db
async def test_a_summary_whose_send_failed_goes_out_with_the_next_message(rig: Rig) -> None:
    class FailsOnce(FakeChannel):
        failed = False

        async def send_buttons(self, to: str, body: str, buttons: Any, **headers: Any) -> str:
            if not self.failed:
                self.failed = True
                raise RuntimeError("boom")
            return await super().send_buttons(to, body, buttons, **headers)

    rig.chat.channel = FailsOnce()
    await add_business(rig, datetime.now(UTC))

    await rig.generate()

    assert not await rig.summary_sent()

    await rig.write("¿Y?")

    assert rig.summaries() == [SUMMARY_TEXT]
    assert await rig.summary_sent()
