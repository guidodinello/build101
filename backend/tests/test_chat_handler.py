import asyncio
import json
import uuid
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.background import BackgroundWork
from app.channels.base import Button, ChannelError, InboundMessage
from app.channels.inbound import EchoHandler
from app.channels.kapso_webhook import parse_message
from app.config import Settings
from app.conversation.chat import ChatHandler
from app.conversation.events import (
    ActionFailed,
    AudioUnclear,
    BrandConfirmed,
    BrandFixAsked,
    BrandGenerating,
    BrandSummaryReady,
    Event,
    JobFailed,
    JobRetried,
    PhotosReceived,
    PhotoTooBig,
    PhotoUnreadable,
    PostApproved,
    PostChangeAsked,
    PostDiscarded,
    PostFailed,
    PostNotStarted,
    PostSent,
    PostStarted,
    Published,
    PublishFailed,
    PublishNotConnected,
    PublishPending,
    PublishStarted,
    PublishUnconfirmed,
    StaleButton,
    UnsupportedMedia,
)
from app.conversation.factory import Chat, ChatParts, build_chat, build_conversation
from app.conversation.history import InMemoryHistory
from app.conversation.outbound import FixedReplies
from app.conversation.photos import Photo, local_now
from app.conversation.turns import MAX_STEPS
from app.copy import messages_es
from app.llm.client import Step, user_step
from app.media.public import PublicImages
from app.posts.drafts import CarouselDraft, PostCopy, SlideDraft
from app.posts.store import Post, PostImage
from app.publishing.mock import MOCK_ACCOUNT_ID, MockPublisher
from app.rendering.mock import MockRenderer
from app.storage import StorageError
from tests.conftest import FIXTURES, make_image
from tests.fakes import (
    PERMALINK,
    CountingImageGen,
    FakeChannel,
    ScriptedModel,
    call_reply,
    text_reply,
)

SENDER = "59899000001"
REPLY_TEXT = "¡Hola! ¿Qué vendés?"
FOLLOW_UP = "¡Listo! ¿Te gusta? ¿Lo subo, o le cambio algo?"
EVENT_REPLY = "Mandámelo de nuevo, porfa 🙏"
DRAFT = PostCopy(caption="Mesa de roble", hashtags=["#muebles"])
# Long enough for photos handled one after the other to land in one batch.
DEBOUNCE_S = 0.2
MAX_PHOTO_MB = 1


def carousel_draft(slides: int) -> CarouselDraft:
    return CarouselDraft(
        caption="Mesa de roble a medida",
        hashtags=["#muebles", "#roble"],
        family="editorial",
        style_prompt="warm",
        style_notes="cálido",
        slides=[
            SlideDraft(
                role="content",
                kicker="",
                headline=f"Slide {n}",
                body="",
                scene_prompt=f"scene {n}",
            )
            for n in range(1, slides + 1)
        ],
    )


def message(name: str, **changes: object) -> InboundMessage:
    body = json.loads((FIXTURES / f"kapso_message_{name}.json").read_text())["body"]
    return parse_message(body).model_copy(update=changes)


class FakeLibrary:
    """The wizard's photos and logo, as `BrandLibrary` returns them."""

    def __init__(
        self, *descriptions: str, logo: bytes | None = None, logo_fails_after: int | None = None
    ) -> None:
        self._photos = [
            Photo(f"b{n}", make_image((900, 1200)), text, local_now(), seen=True)
            for n, text in enumerate(descriptions, start=1)
        ]
        self._logo = logo
        self._logo_fails_after = logo_fails_after
        self._logo_calls = 0

    async def photos(self, sender: str) -> list[Photo]:
        return self._photos

    async def logo(self, sender: str) -> bytes | None:
        self._logo_calls += 1
        if self._logo_fails_after is not None and self._logo_calls > self._logo_fails_after:
            raise StorageError("download failed")
        return self._logo


def build(
    model: ScriptedModel,
    image_gen: CountingImageGen | None = None,
    max_posts_per_day: int = 5,
    keep_alive_s: float = 60.0,
    library: FakeLibrary | None = None,
    **options: Any,
) -> tuple[Chat, BackgroundWork]:
    model.drafts.setdefault(PostCopy, DRAFT)
    model.drafts.setdefault(CarouselDraft, carousel_draft(1))
    background = BackgroundWork()
    chat = build_chat(
        ChatParts(
            model=model,
            image_gen=image_gen or CountingImageGen(),
            renderer=MockRenderer(),
            publisher=MockPublisher(delay_s=0),
            images=PublicImages(),
            background=background,
            public_backend_url="https://backend.test",
            account_id=MOCK_ACCOUNT_ID,
            assistant_name="Mora",
            max_photo_mb=MAX_PHOTO_MB,
            max_posts_per_day=max_posts_per_day,
            max_videos_per_day=2,
            photo_debounce_s=DEBOUNCE_S,
            keep_alive_s=keep_alive_s,
            library=library,
            **options,
        )
    )
    return chat, background


def step_text(step: Step) -> str:
    return step["content"][0]["text"] if step["type"] == "user_input" else ""


def last_user_text(history: list[Step]) -> str:
    return next(step for step in reversed(history) if step["type"] == "user_input")["content"][0][
        "text"
    ]


async def test_text_gets_the_model_reply_with_typing() -> None:
    model, channel = ScriptedModel(), FakeChannel()

    await build(model)[0].handler.handle(message("text"), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert channel.read == [("wamid.FAKE0000000000000000000001", True)]
    assert last_user_text(model.calls[0]) == "hola bot"
    assert model.tools_seen[0] and model.tools_seen[0][0]["name"] == "create_post"


async def test_second_turn_resends_history_with_thought_steps() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat, _ = build(model)

    await chat.handler.handle(message("text"), channel)
    await chat.handler.handle(message("text", text="vendo muebles"), channel)

    assert [step["type"] for step in model.calls[1]] == [
        "user_input",
        "thought",
        "model_output",
        "user_input",
    ]


async def test_the_context_block_is_sent_but_not_stored() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat, _ = build(model)

    await chat.handler.handle(message("text"), channel)
    await chat.handler.handle(message("text", text="vendo muebles"), channel)

    stored_user, *_, current_user = model.calls[1]
    assert len(stored_user["content"]) == 1
    assert current_user["content"][1]["text"].endswith("<recent_photos>\nnone\n</recent_photos>")


async def test_a_slow_reply_sends_one_holding_message_and_typing_again() -> None:
    model, channel = ScriptedModel(delay_s=0.25), FakeChannel()
    chat, _ = build(model, keep_alive_s=0.1)

    await chat.handler.handle(message("text"), channel)

    assert channel.sent == [(SENDER, messages_es.STILL_WORKING), (SENDER, REPLY_TEXT)]
    assert len(channel.read) >= 2


async def test_a_fast_reply_sends_no_holding_message() -> None:
    model, channel = ScriptedModel(delay_s=0.05), FakeChannel()
    chat, _ = build(model, keep_alive_s=0.2)

    await chat.handler.handle(message("text"), channel)
    await asyncio.sleep(0.3)

    assert channel.sent == [(SENDER, REPLY_TEXT)]


async def test_a_slow_reply_about_new_photos_says_it_is_looking_at_them() -> None:
    model, channel = ScriptedModel(delay_s=0.25), FakeChannel()
    chat, background = build(model, keep_alive_s=0.1)

    await chat.handler.handle(message("image"), channel)
    await background.join()

    assert channel.sent[0] == (SENDER, messages_es.LOOKING_AT_PHOTOS)


async def test_voice_note_is_answered_from_its_transcript() -> None:
    model, channel = ScriptedModel(), FakeChannel()

    await build(model)[0].handler.handle(message("audio"), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert last_user_text(model.calls[0]) == "[audio] Quiero un post para la promo del sábado"


async def test_voice_note_without_transcript_is_an_event_the_model_answers() -> None:
    model, channel = ScriptedModel(replies=[text_reply(EVENT_REPLY)]), FakeChannel()
    incoming = message("audio")
    incoming.audio.provider_transcript = None

    await build(model)[0].handler.handle(incoming, channel)

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert len(model.calls) == 1
    assert step_text(model.calls[0][-1]) == AudioUnclear().note()


async def test_a_button_is_a_stale_button_event() -> None:
    model, channel = ScriptedModel(replies=[text_reply(EVENT_REPLY)]), FakeChannel()

    await build(model)[0].handler.handle(message("interactive"), channel)

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert len(model.calls) == 1
    assert step_text(model.calls[0][-1]) == StaleButton().note()


async def test_an_unsupported_kind_is_an_event_the_model_answers() -> None:
    model, channel = ScriptedModel(replies=[text_reply(EVENT_REPLY)]), FakeChannel()

    await build(model)[0].handler.handle(message("text", kind="sticker", text=None), channel)

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert step_text(model.calls[0][-1]) == UnsupportedMedia().note()


async def test_a_photo_without_caption_is_an_event_the_model_answers() -> None:
    model, channel = ScriptedModel(replies=[text_reply(EVENT_REPLY)]), FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(message("image", text=None), channel)
    await background.join()

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert len(model.calls) == 1
    assert step_text(model.calls[0][-1]) == PhotosReceived(("f1",)).note()


async def test_photos_without_text_attach_the_images_but_store_only_the_note() -> None:
    model, channel = ScriptedModel(replies=[text_reply(EVENT_REPLY)]), FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(message("image", text=None), channel)
    await chat.handler.handle(message("image", text=None), channel)
    await background.join()

    current = model.calls[0][-1]
    assert step_text(current) == "[photos f1 f2 received, no text]"
    assert "Attached below, in this order: f1, f2" in current["content"][1]["text"]
    assert [part["type"] for part in current["content"][2:]] == ["image"] * 2
    stored = (await chat.history.get(SENDER))[0]
    assert len(stored["content"]) == 1
    assert all(photo.seen for photo in chat.photos.recent(SENDER))


async def test_photos_stay_unseen_when_their_turn_fails() -> None:
    model, channel = ScriptedModel(fail=True), FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(message("image", text=None), channel)
    await background.join()

    assert channel.sent == [(SENDER, messages_es.PHOTO_KEPT)]
    assert not chat.photos.recent(SENDER)[0].seen


async def test_several_photos_without_text_fall_back_to_the_plural_text() -> None:
    model, channel = ScriptedModel(fail=True), FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(message("image", text=None), channel)
    await chat.handler.handle(message("image", text=None), channel)
    await background.join()

    assert channel.sent == [(SENDER, messages_es.PHOTOS_KEPT)]


async def test_photos_without_text_proceed_with_the_post_the_owner_already_asked_for() -> None:
    model = ScriptedModel(
        replies=[
            text_reply("¡Dale! Mandame las fotos 📸"),
            call_reply("create_post", brief="Navidad", asset_ids=["f1"], style="photos"),
            text_reply("Dale, lo armo con la foto ⏳"),
            text_reply(FOLLOW_UP),
        ]
    )
    channel = FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(message("text", text="armame algo para Navidad"), channel)
    await chat.handler.handle(message("image", text=None), channel)
    await background.join()

    assert [text for _, text in channel.sent] == [
        "¡Dale! Mandame las fotos 📸",
        "Dale, lo armo con la foto ⏳",
        FOLLOW_UP,
    ]
    assert len(channel.images) == 1


async def test_an_album_is_answered_once_with_all_its_photos() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(message("text", kind="album", text=None), channel)
    await chat.handler.handle(message("image", text="armame un post con estos muebles"), channel)
    await chat.handler.handle(message("image", text=None), channel)
    await chat.handler.handle(message("image", text=None), channel)
    await background.join()

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert len(model.calls) == 1
    current = model.calls[0][-1]
    assert current["content"][0]["text"] == "[fotos f1 f2 f3] armame un post con estos muebles"
    assert "Attached below, in this order: f1, f2, f3" in current["content"][1]["text"]
    assert [part["type"] for part in current["content"][2:]] == ["image"] * 3


async def test_a_text_right_after_the_photos_joins_them() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(message("image", text=None), channel)
    await chat.handler.handle(message("text", text="armame algo"), channel)
    await background.join()

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert last_user_text(model.calls[0]) == "[foto f1] armame algo"


async def test_photos_are_attached_once_but_listed_while_recent() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(message("image"), channel)
    await background.join()
    await chat.handler.handle(message("text", text="la 2"), channel)

    later = model.calls[1][-1]
    assert [part["type"] for part in later["content"]] == ["text", "text"]
    assert "f1 sent" in later["content"][1]["text"]


async def test_a_photo_declared_too_big_is_not_downloaded() -> None:
    model, channel = ScriptedModel(replies=[text_reply(EVENT_REPLY)]), FakeChannel()
    incoming = message("image")
    incoming.media.byte_size = MAX_PHOTO_MB * 1024 * 1024 + 1

    await build(model)[0].handler.handle(incoming, channel)

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert channel.downloads == []
    assert step_text(model.calls[0][-1]) == PhotoTooBig(MAX_PHOTO_MB).note()


async def test_a_photo_that_downloads_too_big_is_refused() -> None:
    model = ScriptedModel(replies=[text_reply(EVENT_REPLY)])
    channel = FakeChannel(media=b"x" * (MAX_PHOTO_MB * 1024 * 1024 + 1))
    chat, background = build(model)

    await chat.handler.handle(message("image"), channel)
    await background.join()

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert len(model.calls) == 1
    assert step_text(model.calls[0][-1]) == PhotoTooBig(MAX_PHOTO_MB).note()


async def test_an_unreadable_photo_is_an_event_the_model_answers() -> None:
    model = ScriptedModel(replies=[text_reply(EVENT_REPLY)])
    channel = FakeChannel(media=b"not an image")

    await build(model)[0].handler.handle(message("image"), channel)

    assert channel.sent == [(SENDER, EVENT_REPLY)]
    assert step_text(model.calls[0][-1]) == PhotoUnreadable().note()


@pytest.mark.parametrize("text", ["hola", "¿cuánto sale un post?"])
async def test_chat_without_a_post_request_generates_nothing(text: str) -> None:
    model, channel, image_gen = ScriptedModel(), FakeChannel(), CountingImageGen()

    await build(model, image_gen)[0].handler.handle(message("text", text=text), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert image_gen.calls == []


async def test_a_post_request_sends_one_ack_then_the_image_with_its_text() -> None:
    model = ScriptedModel(
        replies=[
            call_reply("create_post", brief="mesa nueva", asset_ids=["f1"], style="photos"),
            text_reply("Dale, lo armo con la foto de la mesa ⏳"),
            text_reply(FOLLOW_UP),
        ]
    )
    channel, image_gen = FakeChannel(), CountingImageGen()
    chat, background = build(model, image_gen)

    await chat.handler.handle(message("image", text=None), channel)
    await chat.handler.handle(
        message("text", text="armame un post con esta mesa, así nomás"), channel
    )
    await background.join()

    assert channel.sent == [
        (SENDER, "Dale, lo armo con la foto de la mesa ⏳"),
        (SENDER, FOLLOW_UP),
    ]
    assert len(channel.images) == 1
    _, url, caption = channel.images[0]
    assert url.startswith("https://backend.test/media/")
    assert caption == "Mesa de roble\n\n#muebles"
    assert image_gen.calls == []
    result = model.calls[1][-1]
    assert result["type"] == "function_result" and result["call_id"] == "call_1"
    assert json.loads(result["result"])["status"] == "generating"


async def test_the_next_turn_sees_the_note_of_the_sent_post() -> None:
    model = ScriptedModel(
        replies=[
            call_reply("create_post", brief="mesa", asset_ids=["f1"], style="photos"),
            text_reply("Dale ⏳"),
            text_reply(FOLLOW_UP),
            text_reply("Te lo rehago"),
        ]
    )
    channel = FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(message("image", text="armala así nomás"), channel)
    await background.join()
    await chat.handler.handle(message("text", text="cambiale el texto"), channel)

    history = model.calls[-1]
    note = next(step for step in history if step_text(step).startswith("[post "))
    assert 'Text: "Mesa de roble\n\n#muebles"' in step_text(note)
    assert step_text(history[-1]) == "cambiale el texto"


async def test_a_second_request_while_generating_gets_generation_in_progress() -> None:
    gate = asyncio.Event()
    request = call_reply("create_post", brief="mesa", asset_ids=["f1"], style="design")
    model = ScriptedModel(replies=[request, text_reply("Dale ⏳"), request, text_reply("Esperá")])
    channel, image_gen = FakeChannel(), CountingImageGen(gate=gate)
    chat, background = build(model, image_gen)

    await chat.handler.handle(message("image", text=None), channel)
    await chat.handler.handle(message("text", text="armame un post"), channel)
    await asyncio.sleep(0)
    await chat.handler.handle(message("text", text="y otro"), channel)
    gate.set()
    await background.join()

    second_result = json.loads(model.calls[3][-1]["result"])
    assert second_result == {"error": "generation_in_progress"}
    assert len(image_gen.calls) == 1


async def test_the_request_past_the_daily_limit_gets_daily_limit() -> None:
    request = call_reply("create_post", brief="mesa", asset_ids=["f1"], style="design")
    model = ScriptedModel(
        replies=[request, text_reply("Dale ⏳"), text_reply(FOLLOW_UP)] * 2
        + [request, text_reply("Mañana")]
    )
    channel, image_gen = FakeChannel(), CountingImageGen()
    chat, background = build(model, image_gen, max_posts_per_day=2)

    await chat.handler.handle(message("image", text=None), channel)
    for _ in range(3):
        await chat.handler.handle(message("text", text="armame un post"), channel)
        await background.join()

    assert json.loads(model.calls[-1][-1]["result"]) == {"error": "daily_limit"}
    assert len(image_gen.calls) == 2


async def test_a_model_that_keeps_calling_tools_gets_the_fixed_message() -> None:
    model = ScriptedModel(replies=[call_reply("unknown_tool")])
    channel = FakeChannel()
    chat, _ = build(model)

    await chat.handler.handle(message("text"), channel)
    model.replies = [text_reply(REPLY_TEXT)]
    await chat.handler.handle(message("text", text="otra vez"), channel)

    assert len(model.calls) == MAX_STEPS + 1
    assert channel.sent[0] == (SENDER, messages_es.REPLY_FAILED)
    assert [step["type"] for step in model.calls[-1]] == ["user_input"]


async def test_model_failure_sends_fixed_message_and_keeps_history_clean() -> None:
    model, channel = ScriptedModel(fail=True), FakeChannel()
    chat, _ = build(model)

    await chat.handler.handle(message("text"), channel)
    model.fail = False
    await chat.handler.handle(message("text", text="otra vez"), channel)

    assert channel.sent[0] == (SENDER, messages_es.REPLY_FAILED)
    assert [step["type"] for step in model.calls[1]] == ["user_input"]


async def test_a_failing_mark_read_does_not_block_the_reply() -> None:
    channel = FakeChannel(fail_mark_read=True)

    await build(ScriptedModel())[0].handler.handle(message("text"), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]


async def test_messages_from_one_sender_are_answered_in_order() -> None:
    model, channel = ScriptedModel(delay_s=0.01), FakeChannel()
    chat, _ = build(model)

    await asyncio.gather(
        chat.handler.handle(message("text", text="uno"), channel),
        chat.handler.handle(message("text", text="dos"), channel),
    )

    # The second turn saw the first one's answer: turns ran one at a time.
    assert len(model.calls[1]) == 4


def test_chat_handler_needs_a_gemini_key_and_a_public_url() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_conversation(
            Settings(inbound_handler="chat", gemini_api_key=None),
            PublicImages(),
            MockPublisher(),
        )
    with pytest.raises(ValueError, match="PUBLIC_BACKEND_URL"):
        build_conversation(
            Settings(inbound_handler="chat", gemini_api_key="key", public_backend_url=None),
            PublicImages(),
            MockPublisher(),
        )


def test_factory_builds_each_handler() -> None:
    chat = build_conversation(
        Settings(
            inbound_handler="chat",
            gemini_api_key="key",
            public_backend_url="https://backend.test",
            image_gen="mock",
        ),
        PublicImages(),
        MockPublisher(),
    )
    echo = build_conversation(Settings(inbound_handler="echo"), PublicImages(), MockPublisher())

    assert isinstance(chat.handler, ChatHandler)
    assert isinstance(echo.handler, EchoHandler)
    assert isinstance(echo.notify, FixedReplies)


POST_ID = "abcdef12"
JOB_UUID = uuid.UUID("22222222-2222-2222-2222-222222222222")
CREATE = call_reply("create_post", brief="mesa", asset_ids=["f1"], style="design")


async def start_gated_post(
    model: ScriptedModel, monkeypatch: pytest.MonkeyPatch
) -> tuple[Chat, BackgroundWork, FakeChannel, asyncio.Event]:
    """A design post asked for and generating: it is sent once the returned gate is set."""
    monkeypatch.setattr(
        "app.posts.maker.uuid", SimpleNamespace(uuid4=lambda: SimpleNamespace(hex=POST_ID * 2))
    )
    gate, channel = asyncio.Event(), FakeChannel()
    chat, background = build(model, CountingImageGen(gate=gate))
    await chat.handler.handle(message("image", text=None), channel)
    await chat.handler.handle(message("text", text="armame un post"), channel)
    return chat, background, channel, gate


async def test_the_model_answers_the_sent_note_with_its_own_words(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = ScriptedModel(replies=[CREATE, text_reply("Dale ⏳"), text_reply(FOLLOW_UP)])
    chat, background, channel, gate = await start_gated_post(model, monkeypatch)

    gate.set()
    await background.join()

    assert len(model.calls) == 3
    assert step_text(model.calls[2][-1]).startswith(f"[post {POST_ID} sent to the Owner]")
    assert channel.sent[-1] == (SENDER, FOLLOW_UP)
    assert [step_text(step) for step in (await chat.history.get(SENDER))][-1:] == [""]  # the reply
    assert chat.lifecycle.get(SENDER, POST_ID).status == "pending_approval"


async def test_the_note_turn_cannot_approve_and_keeps_the_numbered_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    approve = call_reply("approve_post", post_id=POST_ID, next="publish_now")
    model = ScriptedModel(replies=[CREATE, text_reply("Dale ⏳"), approve, text_reply("¿Lo subo?")])
    chat, background, channel, gate = await start_gated_post(model, monkeypatch)
    show_numbered_list(chat, "o1", "o2")

    gate.set()
    await background.join()

    result = json.loads(model.calls[3][-1]["result"])
    assert result == {"error": "approval_not_explicit"}
    assert chat.lifecycle.get(SENDER, POST_ID).status == "pending_approval"
    assert second_listed(chat) == "o2"
    assert channel.sent[-1] == (SENDER, "¿Lo subo?")


async def test_the_note_turn_cannot_start_another_post(monkeypatch: pytest.MonkeyPatch) -> None:
    model = ScriptedModel(replies=[CREATE, text_reply("Dale ⏳"), CREATE, text_reply("Listo")])
    chat, background, channel, gate = await start_gated_post(model, monkeypatch)

    gate.set()
    await background.join()

    assert json.loads(model.calls[3][-1]["result"]) == {"error": "not_owner_request"}
    assert len(channel.images) == 1
    assert len(chat.lifecycle.pending(SENDER)) == 1


async def test_the_follow_up_waits_for_an_owner_turn_in_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = ScriptedModel(replies=[CREATE, text_reply("Dale ⏳"), text_reply(FOLLOW_UP)])
    chat, background, channel, gate = await start_gated_post(model, monkeypatch)

    async with chat.history.lock(SENDER):  # an Owner turn is being answered
        gate.set()
        for _ in range(100):
            if channel.images:
                break
            await asyncio.sleep(0.01)
        await asyncio.sleep(0.05)
        assert len(model.calls) == 2
        assert channel.sent == [(SENDER, "Dale ⏳")]
        await chat.history.extend(SENDER, [user_step("gracias")])
    await background.join()

    texts = [step_text(step) for step in (await chat.history.get(SENDER))]
    assert texts.index("gracias") < texts.index(next(t for t in texts if t.startswith("[post ")))
    assert channel.sent[-1] == (SENDER, FOLLOW_UP)


async def test_a_post_approved_before_the_follow_up_gets_no_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = ScriptedModel(replies=[CREATE, text_reply("Dale ⏳"), text_reply(FOLLOW_UP)])
    chat, background, channel, gate = await start_gated_post(model, monkeypatch)

    async with chat.history.lock(SENDER):
        gate.set()
        for _ in range(100):
            if chat.lifecycle.get(SENDER, POST_ID):
                break
            await asyncio.sleep(0.01)
        chat.lifecycle.approve(SENDER, POST_ID)
    await background.join()

    assert len(model.calls) == 2
    assert channel.sent == [(SENDER, "Dale ⏳")]
    texts = [step_text(step) for step in (await chat.history.get(SENDER))]
    assert any(text.startswith(f"[post {POST_ID} sent") for text in texts)


async def test_a_failing_follow_up_sends_only_the_buttons_and_keeps_the_post(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = ScriptedModel(replies=[CREATE, text_reply("Dale ⏳")])
    chat, background, channel, gate = await start_gated_post(model, monkeypatch)
    model.fail = True

    gate.set()
    await background.join()

    # No follow-up and no JOB_FAILED: only the post's buttons, with their fixed line.
    assert channel.sent == [(SENDER, "Dale ⏳"), (SENDER, messages_es.post_actions())]
    assert len(channel.images) == 1
    assert chat.lifecycle.get(SENDER, POST_ID).status == "pending_approval"
    texts = [step_text(step) for step in (await chat.history.get(SENDER))]
    assert any(text.startswith(f"[post {POST_ID} sent") for text in texts)


async def test_text_next_to_tool_calls_on_the_last_step_is_not_a_reply() -> None:
    with_text = replace(call_reply("unknown_tool"), text="Un momento")
    model, channel = ScriptedModel(replies=[with_text]), FakeChannel()

    await build(model)[0].handler.handle(message("text"), channel)

    assert len(model.calls) == MAX_STEPS
    assert channel.sent == [(SENDER, messages_es.REPLY_FAILED)]


def pending_post(chat: Chat) -> None:
    chat.lifecycle.add(Post(POST_ID, SENDER, [PostImage("/media/x.jpg", b"jpeg")], "Texto"))


def show_numbered_list(chat: Chat, *post_ids: str) -> None:
    """The Owner said "subilo" with several posts pending and was shown them as a numbered list."""
    for post_id in post_ids:
        chat.lifecycle.add(Post(post_id, SENDER, [PostImage("/media/y.jpg", b"jpeg")], "Otro"))
    approval = chat.lifecycle.approval_for(SENDER, "subilo", attached=False, recent_photos=[])
    assert approval.reason == "several_pending"


def second_listed(chat: Chat) -> str | None:
    """The post "la segunda" names, so whether the numbered list is still the one the Owner saw."""
    return chat.lifecycle.approval_for(
        SENDER, "la segunda", attached=False, recent_photos=[]
    ).post_id


SENT = PostSent(POST_ID, 1, "photos", ("f1",), (), "Texto")
BUTTON_EVENTS: list[Event] = [
    BrandConfirmed(),
    BrandFixAsked(),
    JobRetried("generate_brand"),
    PostApproved(POST_ID),
    PostChangeAsked(POST_ID),
    PostDiscarded(POST_ID),
    PostStarted(POST_ID, "Sí, otro"),
    PostNotStarted("daily_limit"),
    PublishStarted(POST_ID),
    PublishNotConnected(POST_ID),
    ActionFailed(),
]
EVENTS: list[Event] = [
    SENT,
    PostFailed(POST_ID, "design", ("f1",), "mesa"),
    Published(POST_ID, PERMALINK),
    PublishPending(POST_ID),
    PublishFailed(POST_ID),
    PublishUnconfirmed(POST_ID),
    PhotosReceived(("f1",)),
    AudioUnclear(),
    UnsupportedMedia(),
    PhotoUnreadable(),
    PhotoTooBig(MAX_PHOTO_MB),
    StaleButton(),
    *BUTTON_EVENTS,
]


VERBATIM_EVENTS = [
    (
        BrandSummaryReady("Katei", "• cálidos"),
        messages_es.brand_summary("Katei", "• cálidos"),
        ["brand_ok", "brand_fix"],
    ),
    (JobFailed(JOB_UUID, "generate_brand"), messages_es.JOB_FAILED, [f"retry:{JOB_UUID}"]),
    (BrandGenerating(), messages_es.BRAND_GENERATING, None),
]


@pytest.mark.parametrize(
    ("event", "text", "button_ids"), VERBATIM_EVENTS, ids=lambda e: type(e).__name__
)
async def test_a_verbatim_event_is_sent_as_written_with_no_model_turn(
    event: Event, text: str, button_ids: list[str] | None
) -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat, _ = build(model)

    await chat.notify(SENDER, event, channel)

    assert model.calls == []
    assert channel.sent == [(SENDER, text)]
    assert [ids for _, _, ids in channel.buttons] == ([button_ids] if button_ids else [])
    assert [step_text(step) for step in await chat.history.get(SENDER)] == [event.note()]


async def test_a_verbatim_events_delivery_failure_reaches_the_caller_and_leaves_no_note() -> None:
    class Down(FakeChannel):
        async def send_text(self, to: str, text: str) -> str:
            raise ChannelError("boom")

    chat, _ = build(ScriptedModel())

    with pytest.raises(ChannelError):
        await chat.notify(SENDER, BrandGenerating(), Down())

    assert await chat.history.get(SENDER) == []


class BrokenHistory(InMemoryHistory):
    """A database that fails when the turn reads the history."""

    async def get(self, sender: str) -> list[Step]:
        raise SQLAlchemyError("boom")


@pytest.mark.parametrize(
    ("event", "_text", "_button_ids"), VERBATIM_EVENTS, ids=lambda e: type(e).__name__
)
async def test_a_verbatim_event_that_fails_before_the_send_reaches_the_caller(
    event: Event, _text: str, _button_ids: list[str] | None
) -> None:
    channel = FakeChannel()
    chat, _ = build(ScriptedModel(), history=BrokenHistory())

    with pytest.raises(SQLAlchemyError):
        await chat.notify(SENDER, event, channel)

    assert channel.sent == []
    assert channel.buttons == []


async def test_any_other_events_failure_is_only_logged(caplog: pytest.LogCaptureFixture) -> None:
    channel = FakeChannel()
    chat, _ = build(ScriptedModel(), history=BrokenHistory())

    await chat.notify(SENDER, StaleButton(), channel)

    assert "StaleButton event failed" in caplog.text
    assert channel.sent == []


@pytest.mark.parametrize("event", EVENTS, ids=lambda event: type(event).__name__)
async def test_every_event_is_one_model_turn_that_cannot_approve(event: Event) -> None:
    approve = call_reply("approve_post", post_id=POST_ID, next="publish_now")
    model, channel = ScriptedModel(replies=[approve, text_reply("Ok")]), FakeChannel()
    chat, _ = build(model)
    pending_post(chat)
    show_numbered_list(chat, "other")

    await chat.notify(SENDER, event, channel)

    assert len(model.calls) == 2  # the event, then the tool result
    assert step_text(model.calls[0][-1]) == event.note()
    assert json.loads(model.calls[1][-1]["result"]) == {"error": "approval_not_explicit"}
    assert chat.lifecycle.get(SENDER, POST_ID).status == "pending_approval"
    assert second_listed(chat) == "other"
    assert channel.sent[0][1].startswith("Ok")
    history = await chat.history.get(SENDER)
    assert step_text(history[0]) == event.note()
    assert history[-1]["type"] == "model_output"


@pytest.mark.parametrize(
    "event",
    [e for e in EVENTS if not isinstance(e, PhotosReceived)],
    ids=lambda e: type(e).__name__,
)
async def test_only_photos_without_text_may_start_a_post(event: Event) -> None:
    model, channel, image_gen = (
        ScriptedModel(replies=[CREATE, text_reply("Listo")]),
        FakeChannel(),
        CountingImageGen(),
    )
    chat, _ = build(model, image_gen)
    pending_post(chat)

    await chat.notify(SENDER, event, channel)

    assert json.loads(model.calls[1][-1]["result"]) == {"error": "not_owner_request"}
    assert image_gen.calls == []


async def test_the_permalink_is_appended_when_the_reply_leaves_it_out() -> None:
    model, channel = ScriptedModel(replies=[text_reply("¡Publicado! 🎉")]), FakeChannel()

    await build(model)[0].notify(SENDER, Published(POST_ID, PERMALINK), channel)

    assert channel.sent == [(SENDER, f"¡Publicado! 🎉\n{PERMALINK}")]


async def test_the_permalink_is_not_repeated_when_the_reply_has_it() -> None:
    reply = f"¡Publicado! 🎉 {PERMALINK}"
    model, channel = ScriptedModel(replies=[text_reply(reply)]), FakeChannel()

    await build(model)[0].notify(SENDER, Published(POST_ID, PERMALINK), channel)

    assert channel.sent == [(SENDER, reply)]


async def test_a_published_event_without_a_link_adds_nothing() -> None:
    model, channel = ScriptedModel(replies=[text_reply("Listo")]), FakeChannel()
    chat, _ = build(model)

    await chat.notify(SENDER, Published(POST_ID, None), channel)

    assert channel.sent == [(SENDER, "Listo")]
    assert "No link came back" in step_text(model.calls[0][-1])


FALLBACKS = [
    (PostFailed(POST_ID, "design", ("f1",), "mesa"), messages_es.JOB_FAILED),
    (Published(POST_ID, PERMALINK), messages_es.published(PERMALINK)),
    (PublishPending(POST_ID), messages_es.PUBLISH_PENDING),
    (PublishFailed(POST_ID), messages_es.PUBLISH_FAILED),
    (PublishUnconfirmed(POST_ID), messages_es.PUBLISH_UNCONFIRMED),
    (PhotosReceived(("f1",)), messages_es.PHOTO_KEPT),
    (PhotosReceived(("f1", "f2")), messages_es.PHOTOS_KEPT),
    (AudioUnclear(), messages_es.AUDIO_UNCLEAR),
    (UnsupportedMedia(), messages_es.UNSUPPORTED_MEDIA),
    (PhotoUnreadable(), messages_es.PHOTO_UNREADABLE),
    (PhotoTooBig(MAX_PHOTO_MB), messages_es.photo_too_big(MAX_PHOTO_MB)),
    (StaleButton(), messages_es.STALE_BUTTON),
    (BrandConfirmed(), messages_es.READY_OPEN_CHAT),
    (BrandFixAsked(), messages_es.BRAND_FIX_PROMPT),
    (JobRetried("generate_brand"), messages_es.RETRYING),
    (PostApproved(POST_ID), messages_es.PUBLISH_NOW_ASK),
    (PostChangeAsked(POST_ID), messages_es.POST_CHANGE_PROMPT),
    (PostDiscarded(POST_ID), messages_es.POST_DISCARDED),
    (PostStarted(POST_ID, "Sí, otro"), messages_es.POST_GENERATING),
    (PostNotStarted("generation_in_progress"), messages_es.GENERATION_BUSY),
    (PostNotStarted("unknown_asset"), messages_es.PHOTOS_GONE),
    (PublishStarted(POST_ID), messages_es.PUBLISHING),
    (PublishNotConnected(POST_ID), messages_es.NEED_IG),
    (ActionFailed(), messages_es.REPLY_FAILED),
]


@pytest.mark.parametrize(("event", "expected"), FALLBACKS, ids=lambda x: type(x).__name__)
async def test_when_the_model_is_down_each_event_sends_its_fixed_text(
    event: Event, expected: str
) -> None:
    model, channel = ScriptedModel(fail=True), FakeChannel()
    chat, _ = build(model)

    await chat.notify(SENDER, event, channel)

    assert channel.sent == [(SENDER, expected)]
    # The next turn knows what the Owner was told.
    [note] = await chat.history.get(SENDER)
    assert f'{event.note()}\nThe Owner was told: "{expected}"' == step_text(note)


async def test_a_model_that_never_answers_an_event_counts_as_down() -> None:
    model, channel = ScriptedModel(replies=[call_reply("unknown_tool")]), FakeChannel()

    await build(model)[0].notify(SENDER, StaleButton(), channel)

    assert len(model.calls) == MAX_STEPS
    assert channel.sent == [(SENDER, messages_es.STALE_BUTTON)]


async def test_a_sent_post_event_with_the_model_down_still_sends_its_buttons() -> None:
    model, channel = ScriptedModel(fail=True), FakeChannel()
    chat, background = build(model)
    pending_post(chat)

    await chat.notify(SENDER, SENT, channel)

    body = messages_es.post_actions()
    assert channel.buttons == [
        (
            SENDER,
            body,
            [f"post_approve:{POST_ID}", f"post_change:{POST_ID}", f"post_discard:{POST_ID}"],
        )
    ]
    assert [step_text(step) for step in (await chat.history.get(SENDER))] == [
        f'{SENT.note()}\nThe Owner was told: "{body}"'
    ]


async def test_another_event_turn_does_not_mark_pending_photos_seen() -> None:
    model = ScriptedModel(replies=[text_reply("Ok"), text_reply(EVENT_REPLY)])
    channel = FakeChannel()
    chat, background = build(model)

    await chat.handler.handle(
        message("image", text=None), channel
    )  # the batch waits out its debounce
    await chat.notify(SENDER, StaleButton(), channel)  # a successful turn that shows no photos
    assert not chat.photos.recent(SENDER)[0].seen
    await background.join()

    current = model.calls[1][-1]
    assert step_text(current) == PhotosReceived(("f1",)).note()
    assert "Attached below, in this order: f1" in current["content"][1]["text"]
    assert [part["type"] for part in current["content"][2:]] == ["image"]
    assert chat.photos.recent(SENDER)[0].seen


async def test_the_wizard_photos_are_listed_for_the_model() -> None:
    model = ScriptedModel()
    chat, _ = build(model, library=FakeLibrary("Mesa nórdica: Mesa de roble en un living."))
    channel = FakeChannel()

    await chat.handler.handle(message("text", text="hacé un post de la mesa nórdica"), channel)

    context = model.calls[0][-1]["content"][1]["text"]
    listed = "- b1: Mesa nórdica: Mesa de roble en un living."
    assert f"<brand_photos>\n{listed}\n</brand_photos>" in context
    assert [block["type"] for block in model.calls[0][-1]["content"]] == ["text", "text"]


async def test_a_post_can_use_a_wizard_photo() -> None:
    model = ScriptedModel(
        replies=[
            call_reply("create_post", brief="la mesa nórdica", asset_ids=["b1"], style="photos"),
            text_reply("Dale, lo armo con la foto de la mesa ⏳"),
        ]
    )
    channel = FakeChannel()
    chat, background = build(model, library=FakeLibrary("Mesa nórdica: Mesa de roble."))

    await chat.handler.handle(
        message("text", text="hacé un post de la mesa nórdica así nomás"), channel
    )
    await background.join()

    assert json.loads(model.calls[1][-1]["result"])["status"] == "generating"
    assert len(channel.images) == 1


async def test_a_tap_is_answered_by_the_model_with_the_next_button() -> None:
    model, channel = ScriptedModel(replies=[text_reply("¡Aprobado! ¿Lo subo ya?")]), FakeChannel()
    chat, _ = build(model)
    pending_post(chat)
    tap = message("interactive").model_copy(
        update={"button": Button(id=f"post_approve:{POST_ID}", title="Aprobar")}
    )

    await chat.handler.handle(tap, channel)

    assert step_text(model.calls[0][-1]) == PostApproved(POST_ID).note()
    assert channel.buttons == [(SENDER, "¡Aprobado! ¿Lo subo ya?", [f"post_publish:{POST_ID}"])]
    assert chat.lifecycle.get(SENDER, POST_ID).status == "approved"


async def test_a_noop_tap_gets_no_answer() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    tap = message("interactive").model_copy(update={"button": Button(id="noop", title="No")})

    await build(model)[0].handler.handle(tap, channel)

    assert model.calls == []
    assert channel.sent == []


async def test_the_model_is_told_when_the_owner_uploaded_a_logo() -> None:
    model = ScriptedModel()
    chat, _ = build(model, library=FakeLibrary("Mesa", logo=make_image((200, 80), format="PNG")))

    await chat.handler.handle(message("text", text="ponele el logo"), FakeChannel())

    assert "<brand_logo>uploaded</brand_logo>" in model.calls[0][-1]["content"][1]["text"]


async def test_a_post_with_the_logo_needs_an_uploaded_logo() -> None:
    model = ScriptedModel(
        replies=[
            call_reply(
                "create_post", brief="mesa", asset_ids=["b1"], style="photos", with_logo=True
            ),
            text_reply("Todavía no tengo tu logo"),
        ]
    )
    chat, background = build(model, library=FakeLibrary("Mesa"))

    await chat.handler.handle(message("text", text="subí la mesa con mi logo"), FakeChannel())
    await background.join()

    assert "<brand_logo>" not in model.calls[0][-1]["content"][1]["text"]
    assert json.loads(model.calls[-1][-1]["result"]) == {"error": "no_logo"}


async def test_a_failed_logo_download_keeps_the_logo_already_loaded() -> None:
    model = ScriptedModel()
    library = FakeLibrary("Mesa", logo=make_image((200, 80), format="PNG"), logo_fails_after=1)
    chat, _ = build(model, library=library)

    await chat.handler.handle(message("text", text="hola"), FakeChannel())
    await chat.handler.handle(message("text", text="ponele el logo"), FakeChannel())

    assert "<brand_logo>uploaded</brand_logo>" in model.calls[1][-1]["content"][1]["text"]
