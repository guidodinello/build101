"""Multi-turn evals of the orchestrator on the real model (ADR 0030).

Each scenario is a short conversation an Owner could have; the checks are on what the model did
(tools, stored notes, post status) or on words its reply must contain. Run with `-m live`.
"""

import uuid
from dataclasses import dataclass, field

import pytest

from app.agents.schemas import BrandBrain
from app.channels.base import InboundMessage
from app.config import get_settings
from app.conversation.button_router import ButtonRouter
from app.conversation.chat import ChatHandler
from app.conversation.events import PostSent
from app.conversation.history import Compactor, InMemoryHistory
from app.conversation.notes import InMemoryNotes
from app.conversation.photos import InMemoryPhotos
from app.knowledge.base import BusinessKnowledge, CatalogItem
from app.llm.client import GeminiChat
from app.media.public import PublicImages
from app.posts.drafts import PostDrafter
from app.posts.lifecycle import PostLifecycle
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import Post, PostImage
from app.publishing.mock import MOCK_ACCOUNT_ID, MockPublisher
from app.rendering.mock import MockRenderer
from tests.conftest import make_image
from tests.fakes import CountingImageGen, FakeChannel, brand_brain

pytestmark = pytest.mark.live

PHONE = "59899000777"
POST_ID = "live0001"


@dataclass
class FixedKnowledge:
    brand: BrandBrain
    catalog: list[CatalogItem] = field(default_factory=list)

    async def of(self, sender: str) -> BusinessKnowledge:
        return BusinessKnowledge(brand=self.brand, catalog=self.catalog)


@dataclass
class Rig:
    chat: ChatHandler
    history: InMemoryHistory
    notes: InMemoryNotes
    store: PostLifecycle
    photos: InMemoryPhotos
    image_gen: CountingImageGen
    channel: FakeChannel

    async def say(self, text: str) -> str:
        sent = len(self.channel.sent)
        await self.chat.handle(text_message(text), self.channel)
        await self.chat.join()
        return " ".join(body for _, body in self.channel.sent[sent:])

    async def tools_called(self) -> list[str]:
        return [
            step["name"]
            for step in await self.history.get(PHONE)
            if step["type"] == "function_call"
        ]


def text_message(text: str) -> InboundMessage:
    return InboundMessage(
        kind="text",
        message_id=f"wamid.{uuid.uuid4().hex}",
        sender=PHONE,
        phone_number_id="live",
        text=text,
        raw={},
    )


def rig(compactor_budget: tuple[int, int] | None = None) -> Rig:
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not set")
    model = GeminiChat.from_api_key(settings.gemini_api_key, settings.gemini_chat_model)
    history, notes, store = InMemoryHistory(), InMemoryNotes(), PostLifecycle()
    photos = InMemoryPhotos()
    images, image_gen = PublicImages(), CountingImageGen()
    posts = PostMaker(
        PostDrafter(model),
        image_gen,
        MockRenderer(),
        photos,
        images,
        store,
        "https://backend.test",
        5,
    )
    publisher = PostPublisher(
        MockPublisher(delay_s=0), store, images, "https://backend.test", MOCK_ACCOUNT_ID
    )
    compactor = Compactor(history, model, *compactor_budget) if compactor_budget else None
    chat = ChatHandler(
        model,
        history,
        photos,
        posts,
        publisher,
        store,
        ButtonRouter(store, posts, publisher, sessions=None),
        None,
        assistant_name="Neitor",
        max_photo_mb=10,
        notes=notes,
        knowledge=FixedKnowledge(
            brand_brain(),
            [CatalogItem("Mesa nórdica de roble", "$U 18.500", "Mesa de comedor para 6")],
        ),
        compactor=compactor,
    )
    posts.on_event(chat.notify)
    publisher.on_event(chat.notify)
    return Rig(chat, history, notes, store, photos, image_gen, FakeChannel())


async def sent_post(rig: Rig, caption: str) -> None:
    """A photos post that reached the Owner, and the model's own message about it."""
    photo = rig.photos.add(PHONE, make_image((800, 1000)), None)
    photo.used = True
    rig.store.add(
        Post(
            POST_ID,
            PHONE,
            [PostImage("/media/live.jpg", make_image((1080, 1350)))],
            caption,
            brief="Mesa nórdica de roble",
            source_photos=[photo],
        )
    )
    event = PostSent(POST_ID, 1, "photos", (photo.id,), (), caption)
    await rig.chat.notify(PHONE, event, rig.channel)


async def test_it_knows_the_business_without_asking() -> None:
    live = rig()

    reply = await live.say("¿Cómo se llama mi negocio y cuánto sale la mesa nórdica?")

    assert "katei" in reply.lower()
    assert "18.500" in reply


async def test_a_standing_preference_becomes_a_note() -> None:
    live = rig()

    await live.say("Una cosa importante: nunca pongas precios en los posts, ¿sí?")

    notes = await live.notes.list(PHONE)
    assert any("precio" in note.text.lower() for note in notes), notes


async def test_a_yes_to_the_publish_question_publishes() -> None:
    live = rig()
    await sent_post(live, "Mesa nórdica de roble, hecha a mano en Montevideo.\n\n#muebles")

    await live.say("dale")

    assert live.store.get(PHONE, POST_ID).status in {"publishing", "publish_pending", "published"}


async def test_a_change_to_the_caption_edits_it_without_generating_images() -> None:
    live = rig()
    await sent_post(
        live,
        "Esta mesa nórdica de roble macizo fue hecha a mano en nuestro taller de Montevideo, "
        "con encastres tradicionales y una terminación al aceite que resalta la veta. Ideal "
        "para comedores familiares de hasta seis personas. Escribinos por WhatsApp.\n\n#muebles",
    )

    await live.say("el texto está muy largo, acortalo")

    assert "revise_post" in await live.tools_called()
    assert live.image_gen.calls == []


async def test_what_was_said_survives_compaction() -> None:
    live = rig(compactor_budget=(1_500, 400))

    await live.say("Te cuento: el envío es gratis en todo Montevideo, y al interior lo cobramos.")
    for small_talk in ("¿Qué tal tu día?", "Hoy hubo mucho movimiento en el taller", "Jaja sí"):
        await live.say(small_talk)
    reply = await live.say("¿Qué te había dicho del envío?")

    assert await live.history.summary(PHONE), "the conversation was never compacted"
    assert "gratis" in reply.lower()
