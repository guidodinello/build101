"""Photos sent before the wizard is submitted: kept as Brand assets, one reply per batch."""

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.schemas import AssetAnalysis
from app.background import BackgroundWork
from app.channels.base import InboundMessage
from app.conversation.library import BrandLibrary
from app.conversation.onboarding import EarlyPhotos, OnboardingGate
from app.conversation.photo_batches import PhotoBatches
from app.conversation.photo_keeper import PhotoKeeper
from app.conversation.photos import InMemoryPhotos
from app.copy import messages_es
from app.db.models import BrandAsset, Business
from tests.conftest import requires_db
from tests.fakes import EventLog, FakeChannel, FakeStorage, ScriptedModel
from tests.test_asset_analysis import analysis
from tests.test_onboarding_gate import ASSISTANT, FRONTEND, PHONE, FakeChat, message, text

pytestmark = requires_db

CAP = 3
# Long enough for an album's photos to land in one batch, even with a database round trip each.
DEBOUNCE_S = 0.2


@dataclass
class Rig:
    gate: OnboardingGate
    chat: FakeChat
    channel: FakeChannel
    model: ScriptedModel
    events: EventLog
    storage: FakeStorage
    background: BackgroundWork
    sessions: async_sessionmaker[AsyncSession]

    async def send(self, *messages: InboundMessage) -> None:
        for incoming in messages:
            await self.gate.handle(incoming, self.channel)
            await self.background.join()

    async def send_together(self, *messages: InboundMessage) -> None:
        for incoming in messages:
            await self.gate.handle(incoming, self.channel)
        await self.background.join()

    async def business(self) -> Business:
        async with self.sessions() as db:
            return await db.scalar(select(Business).where(Business.owner_phone == PHONE))

    async def assets(self) -> list[BrandAsset]:
        async with self.sessions() as db:
            return list((await db.scalars(select(BrandAsset))).all())

    def replies(self) -> list[str]:
        return [reply for _, reply in self.channel.sent]


@pytest.fixture
def rig(sessions: async_sessionmaker[AsyncSession]) -> Rig:
    chat, channel, events = FakeChat(), FakeChannel(), EventLog()
    model = ScriptedModel(drafts={AssetAnalysis: analysis([])})
    storage, background = FakeStorage(), BackgroundWork()
    batches = PhotoBatches(InMemoryPhotos(), None, 1, events, DEBOUNCE_S, background=background)
    keeper = PhotoKeeper(model, sessions, storage)
    gate = OnboardingGate(
        chat,
        sessions,
        FRONTEND,
        ASSISTANT,
        photos=EarlyPhotos(batches, keeper, background, max_kept=CAP),
    )
    return Rig(gate, chat, channel, model, events, storage, background, sessions)


def photo(message_id: str = "wamid.P1") -> InboundMessage:
    return message("image", text="me llegó esta mesa", message_id=message_id)


async def add_business(rig: Rig, state: str) -> uuid.UUID:
    async with rig.sessions() as db:
        business = Business(owner_phone=PHONE, name="Muebles Ramírez", onboarding_state=state)
        db.add(business)
        await db.commit()
        return business.id


async def test_a_first_photo_is_kept_and_answered_with_the_welcome(rig: Rig) -> None:
    await rig.send(photo())

    [asset] = await rig.assets()
    assert (asset.kind, asset.source, asset.status) == ("photo", "whatsapp", "ready")
    assert asset.owner_hint == "me llegó esta mesa"
    assert asset.analysis is not None
    assert asset.analysis["description"] == "Mesa de roble en el living"
    assert rig.replies() == [messages_es.welcome_with_photos(ASSISTANT, 1)]
    assert (await rig.business()).onboarding_state == "awaiting_name"
    assert rig.chat.handled == []


async def test_a_photo_while_waiting_for_the_name_is_kept_and_asks_for_it(rig: Rig) -> None:
    await add_business(rig, "awaiting_name")

    await rig.send(photo())

    assert len(await rig.assets()) == 1
    assert rig.replies() == [messages_es.photos_kept_ask_name(1)]
    business = await rig.business()
    assert (business.onboarding_state, business.name) == ("awaiting_name", "Muebles Ramírez")


async def test_a_photo_while_waiting_for_the_form_is_kept_and_points_to_the_wizard(
    rig: Rig,
) -> None:
    await add_business(rig, "awaiting_web_form")

    await rig.send(photo())

    assert len(await rig.assets()) == 1
    [reply] = rig.replies()
    assert reply.startswith(messages_es.photos_kept(1))
    assert f"{FRONTEND}/o/" in reply


async def test_a_photo_right_after_a_reminder_points_to_the_wizard_without_a_new_link(
    rig: Rig,
) -> None:
    await add_business(rig, "awaiting_web_form")

    await rig.send(text("¿y ahora?"), photo())

    reminder, reply = rig.replies()
    assert f"{FRONTEND}/o/" in reminder
    assert reply == messages_es.photos_kept_form(1)
    assert len(await rig.assets()) == 1


async def test_an_album_gets_one_reply(rig: Rig) -> None:
    await add_business(rig, "awaiting_name")

    await rig.send_together(
        message("text", kind="album", text=None), photo("wamid.P1"), photo("wamid.P2")
    )

    assert rig.replies() == [messages_es.photos_kept_ask_name(2)]
    assert len(await rig.assets()) == 2


async def test_past_the_cap_photos_are_answered_but_not_kept_or_described(rig: Rig) -> None:
    await add_business(rig, "awaiting_name")

    await rig.send(*(photo(f"wamid.P{n}") for n in range(CAP + 2)))

    assert len(await rig.assets()) == CAP
    assert len(rig.model.structured_calls) == CAP
    assert rig.replies() == [messages_es.photos_kept_ask_name(1)] * (CAP + 2)


async def test_an_unreadable_photo_gets_the_chat_answer_and_onboarding_goes_on(rig: Rig) -> None:
    await add_business(rig, "awaiting_name")
    rig.channel.media = b"not an image"

    await rig.send(photo(), text("Muebles Ramírez"))

    assert [type(event).__name__ for _, event in rig.events.events] == ["PhotoUnreadable"]
    assert await rig.assets() == []
    assert (await rig.business()).onboarding_state == "awaiting_web_form"


async def test_a_too_big_photo_gets_the_chat_answer(rig: Rig) -> None:
    await add_business(rig, "awaiting_name")
    rig.channel.media = b"x" * (2 * 1024 * 1024)

    await rig.send(photo())

    assert [type(event).__name__ for _, event in rig.events.events] == ["PhotoTooBig"]
    assert await rig.assets() == []
    assert rig.replies() == []


async def test_a_photo_kept_before_the_form_is_among_the_photos_after_onboarding(
    rig: Rig,
) -> None:
    await add_business(rig, "awaiting_web_form")
    await rig.send(photo())
    async with rig.sessions() as db:
        business = await db.scalar(select(Business).where(Business.owner_phone == PHONE))
        assert business is not None
        business.onboarding_state = "active"
        await db.commit()

    photos = await BrandLibrary(rig.sessions, rig.storage).photos(PHONE)

    [kept] = await rig.assets()
    assert [found.asset_id for found in photos] == [kept.id]
    assert photos[0].caption == "Mesa de roble en el living"


async def test_after_the_form_photos_go_to_the_chat(rig: Rig) -> None:
    await add_business(rig, "active")
    incoming = photo()

    await rig.send(incoming)

    assert rig.chat.handled == [incoming]
    assert rig.replies() == []
    assert await rig.assets() == []
