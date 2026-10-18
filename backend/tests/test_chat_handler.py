import asyncio
import json

import pytest

from app.channels.base import InboundMessage
from app.channels.inbound import EchoHandler
from app.channels.kapso_webhook import parse_message
from app.config import Settings
from app.conversation.button_router import ButtonRouter
from app.conversation.chat import MAX_STEPS, ChatHandler
from app.conversation.factory import build_inbound_handler
from app.conversation.history import InMemoryHistory
from app.conversation.photos import InMemoryPhotos, Photo, local_now
from app.copy import messages_es
from app.llm.client import Step
from app.media.public import PublicImages
from app.posts.drafts import CarouselDraft, PostCopy, PostDrafter, SlideDraft
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import InMemoryPosts
from app.publishing.mock import MOCK_ACCOUNT_ID, MockPublisher
from tests.conftest import FIXTURES, make_image
from tests.fakes import CountingImageGen, FakeChannel, ScriptedModel, call_reply, text_reply

SENDER = "59899000001"
REPLY_TEXT = "¡Hola! ¿Qué vendés?"
DRAFT = PostCopy(caption="Mesa de roble", hashtags=["#muebles"])
# Long enough for photos handled one after the other to land in one batch.
DEBOUNCE_S = 0.2
MAX_PHOTO_MB = 1


def carousel_draft(slides: int) -> CarouselDraft:
    return CarouselDraft(
        caption="Mesa de roble a medida",
        hashtags=["#muebles", "#roble"],
        style_prompt="warm",
        style_notes="cálido",
        slides=[
            SlideDraft(role="content", headline=f"Slide {n}", body="", scene_prompt=f"scene {n}")
            for n in range(1, slides + 1)
        ],
    )


def message(name: str, **changes: object) -> InboundMessage:
    body = json.loads((FIXTURES / f"kapso_message_{name}.json").read_text())["body"]
    return parse_message(body).model_copy(update=changes)


class FakeLibrary:
    """The wizard's photos, as `BrandLibrary` returns them."""

    def __init__(self, *descriptions: str) -> None:
        self._photos = [
            Photo(f"b{n}", make_image((900, 1200)), text, local_now(), seen=True)
            for n, text in enumerate(descriptions, start=1)
        ]

    async def photos(self, sender: str) -> list[Photo]:
        return self._photos


def build(
    model: ScriptedModel,
    image_gen: CountingImageGen | None = None,
    max_posts_per_day: int = 5,
    keep_alive_s: float = 60.0,
    library: FakeLibrary | None = None,
) -> tuple[ChatHandler, PostMaker]:
    model.drafts.setdefault(PostCopy, DRAFT)
    model.drafts.setdefault(CarouselDraft, carousel_draft(1))
    photos, history, store, images = (
        InMemoryPhotos(),
        InMemoryHistory(),
        InMemoryPosts(),
        PublicImages(),
    )
    posts = PostMaker(
        PostDrafter(model),
        image_gen or CountingImageGen(),
        photos,
        history,
        images,
        store,
        "https://backend.test",
        max_posts_per_day,
    )
    publishing = PostPublisher(
        MockPublisher(delay_s=0), store, history, images, "https://backend.test", MOCK_ACCOUNT_ID
    )
    chat = ChatHandler(
        model,
        history,
        photos,
        posts,
        publishing,
        store,
        ButtonRouter(store, posts, publishing, history, sessions=None),
        library,
        assistant_name="Mora",
        max_photo_mb=MAX_PHOTO_MB,
        photo_debounce_s=DEBOUNCE_S,
        keep_alive_s=keep_alive_s,
    )
    return chat, posts


def handler(model: ScriptedModel) -> ChatHandler:
    return build(model)[0]


def last_user_text(history: list[Step]) -> str:
    return next(step for step in reversed(history) if step["type"] == "user_input")["content"][0][
        "text"
    ]


async def test_text_gets_the_model_reply_with_typing() -> None:
    model, channel = ScriptedModel(), FakeChannel()

    await handler(model).handle(message("text"), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert channel.read == [("wamid.FAKE0000000000000000000001", True)]
    assert last_user_text(model.calls[0]) == "hola bot"
    assert model.tools_seen[0] and model.tools_seen[0][0]["name"] == "create_post"


async def test_second_turn_resends_history_with_thought_steps() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat = handler(model)

    await chat.handle(message("text"), channel)
    await chat.handle(message("text", text="vendo muebles"), channel)

    assert [step["type"] for step in model.calls[1]] == [
        "user_input",
        "thought",
        "model_output",
        "user_input",
    ]


async def test_the_context_block_is_sent_but_not_stored() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat = handler(model)

    await chat.handle(message("text"), channel)
    await chat.handle(message("text", text="vendo muebles"), channel)

    stored_user, *_, current_user = model.calls[1]
    assert len(stored_user["content"]) == 1
    assert current_user["content"][1]["text"] == "<recent_photos>\nnone\n</recent_photos>"


async def test_a_slow_reply_sends_one_holding_message_and_typing_again() -> None:
    model, channel = ScriptedModel(delay_s=0.25), FakeChannel()
    chat, _ = build(model, keep_alive_s=0.1)

    await chat.handle(message("text"), channel)

    assert channel.sent == [(SENDER, messages_es.STILL_WORKING), (SENDER, REPLY_TEXT)]
    assert len(channel.read) >= 2


async def test_a_fast_reply_sends_no_holding_message() -> None:
    model, channel = ScriptedModel(delay_s=0.05), FakeChannel()
    chat, _ = build(model, keep_alive_s=0.2)

    await chat.handle(message("text"), channel)
    await asyncio.sleep(0.3)

    assert channel.sent == [(SENDER, REPLY_TEXT)]


async def test_a_slow_reply_about_new_photos_says_it_is_looking_at_them() -> None:
    model, channel = ScriptedModel(delay_s=0.25), FakeChannel()
    chat, _ = build(model, keep_alive_s=0.1)

    await chat.handle(message("image"), channel)
    await chat.join()

    assert channel.sent[0] == (SENDER, messages_es.LOOKING_AT_PHOTOS)


async def test_voice_note_is_answered_from_its_transcript() -> None:
    model, channel = ScriptedModel(), FakeChannel()

    await handler(model).handle(message("audio"), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert last_user_text(model.calls[0]) == "[audio] Quiero un post para la promo del sábado"


async def test_voice_note_without_transcript_asks_again() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    incoming = message("audio")
    incoming.audio.provider_transcript = None

    await handler(model).handle(incoming, channel)

    assert channel.sent == [(SENDER, messages_es.AUDIO_UNCLEAR)]
    assert model.calls == []


async def test_a_button_gets_the_stale_button_message() -> None:
    model, channel = ScriptedModel(), FakeChannel()

    await handler(model).handle(message("interactive"), channel)

    assert channel.sent == [(SENDER, messages_es.STALE_BUTTON)]
    assert model.calls == []


async def test_a_photo_without_caption_is_kept_and_offered() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat = handler(model)

    await chat.handle(message("image", text=None), channel)
    await chat.join()

    assert channel.sent == []
    assert channel.buttons == [(SENDER, messages_es.PHOTO_KEPT, ["photo_post:f1", "noop"])]
    assert model.calls == []


async def test_an_album_is_answered_once_with_all_its_photos() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat = handler(model)

    await chat.handle(message("text", kind="album", text=None), channel)
    await chat.handle(message("image", text="armame un post con estos muebles"), channel)
    await chat.handle(message("image", text=None), channel)
    await chat.handle(message("image", text=None), channel)
    await chat.join()

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert len(model.calls) == 1
    current = model.calls[0][-1]
    assert current["content"][0]["text"] == "[fotos f1 f2 f3] armame un post con estos muebles"
    assert "Attached below, in this order: f1, f2, f3" in current["content"][1]["text"]
    assert [part["type"] for part in current["content"][2:]] == ["image"] * 3


async def test_a_text_right_after_the_photos_joins_them() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat = handler(model)

    await chat.handle(message("image", text=None), channel)
    await chat.handle(message("text", text="armame algo"), channel)
    await chat.join()

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert last_user_text(model.calls[0]) == "[foto f1] armame algo"


async def test_photos_are_attached_once_but_listed_while_recent() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    chat = handler(model)

    await chat.handle(message("image"), channel)
    await chat.join()
    await chat.handle(message("text", text="la 2"), channel)

    later = model.calls[1][-1]
    assert [part["type"] for part in later["content"]] == ["text", "text"]
    assert "f1 sent" in later["content"][1]["text"]


async def test_a_photo_declared_too_big_is_not_downloaded() -> None:
    model, channel = ScriptedModel(), FakeChannel()
    incoming = message("image")
    incoming.media.byte_size = MAX_PHOTO_MB * 1024 * 1024 + 1

    await handler(model).handle(incoming, channel)

    assert channel.sent == [(SENDER, messages_es.photo_too_big(MAX_PHOTO_MB))]
    assert channel.downloads == []


async def test_a_photo_that_downloads_too_big_is_refused() -> None:
    model = ScriptedModel()
    channel = FakeChannel(media=b"x" * (MAX_PHOTO_MB * 1024 * 1024 + 1))
    chat = handler(model)

    await chat.handle(message("image"), channel)
    await chat.join()

    assert channel.sent == [(SENDER, messages_es.photo_too_big(MAX_PHOTO_MB))]
    assert model.calls == []


async def test_an_unreadable_photo_asks_again() -> None:
    model, channel = ScriptedModel(), FakeChannel(media=b"not an image")

    await handler(model).handle(message("image"), channel)

    assert channel.sent == [(SENDER, messages_es.PHOTO_UNREADABLE)]


@pytest.mark.parametrize("text", ["hola", "¿cuánto sale un post?"])
async def test_chat_without_a_post_request_generates_nothing(text: str) -> None:
    model, channel, image_gen = ScriptedModel(), FakeChannel(), CountingImageGen()

    await build(model, image_gen)[0].handle(message("text", text=text), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]
    assert image_gen.calls == []


async def test_a_post_request_sends_one_ack_then_the_image_with_its_text() -> None:
    model = ScriptedModel(
        replies=[
            call_reply("create_post", brief="mesa nueva", asset_ids=["f1"], style="photos"),
            text_reply("Dale, lo armo con la foto de la mesa ⏳"),
        ]
    )
    channel, image_gen = FakeChannel(), CountingImageGen()
    chat, posts = build(model, image_gen)

    await chat.handle(message("image", text=None), channel)
    await chat.handle(message("text", text="armame un post con esta mesa, así nomás"), channel)
    await posts.join()

    assert channel.sent == [(SENDER, "Dale, lo armo con la foto de la mesa ⏳")]
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
            text_reply("Te lo rehago"),
        ]
    )
    channel = FakeChannel()
    chat, posts = build(model)

    await chat.handle(message("image", text="armala así nomás"), channel)
    await chat.join()
    await posts.join()
    await chat.handle(message("text", text="cambiale el texto"), channel)

    *_, note, current = model.calls[-1]
    assert note["content"][0]["text"].startswith("[post ")
    assert 'Text: "Mesa de roble\n\n#muebles"' in note["content"][0]["text"]
    assert current["content"][0]["text"] == "cambiale el texto"


async def test_a_second_request_while_generating_gets_generation_in_progress() -> None:
    gate = asyncio.Event()
    request = call_reply("create_post", brief="mesa", asset_ids=["f1"], style="design")
    model = ScriptedModel(replies=[request, text_reply("Dale ⏳"), request, text_reply("Esperá")])
    channel, image_gen = FakeChannel(), CountingImageGen(gate=gate)
    chat, posts = build(model, image_gen)

    await chat.handle(message("image", text=None), channel)
    await chat.handle(message("text", text="armame un post"), channel)
    await asyncio.sleep(0)
    await chat.handle(message("text", text="y otro"), channel)
    gate.set()
    await posts.join()

    second_result = json.loads(model.calls[3][-1]["result"])
    assert second_result == {"error": "generation_in_progress"}
    assert len(image_gen.calls) == 1


async def test_the_request_past_the_daily_limit_gets_daily_limit() -> None:
    request = call_reply("create_post", brief="mesa", asset_ids=["f1"], style="design")
    model = ScriptedModel(
        replies=[request, text_reply("Dale ⏳"), request, text_reply("Dale ⏳"), request]
        + [text_reply("Mañana")]
    )
    channel, image_gen = FakeChannel(), CountingImageGen()
    chat, posts = build(model, image_gen, max_posts_per_day=2)

    await chat.handle(message("image", text=None), channel)
    for _ in range(3):
        await chat.handle(message("text", text="armame un post"), channel)
        await posts.join()

    assert json.loads(model.calls[-1][-1]["result"]) == {"error": "daily_limit"}
    assert len(image_gen.calls) == 2


async def test_a_model_that_keeps_calling_tools_gets_the_fixed_message() -> None:
    model = ScriptedModel(replies=[call_reply("unknown_tool")])
    channel = FakeChannel()
    chat = handler(model)

    await chat.handle(message("text"), channel)
    model.replies = [text_reply(REPLY_TEXT)]
    await chat.handle(message("text", text="otra vez"), channel)

    assert len(model.calls) == MAX_STEPS + 1
    assert channel.sent[0] == (SENDER, messages_es.REPLY_FAILED)
    assert [step["type"] for step in model.calls[-1]] == ["user_input"]


async def test_model_failure_sends_fixed_message_and_keeps_history_clean() -> None:
    model, channel = ScriptedModel(fail=True), FakeChannel()
    chat = handler(model)

    await chat.handle(message("text"), channel)
    model.fail = False
    await chat.handle(message("text", text="otra vez"), channel)

    assert channel.sent[0] == (SENDER, messages_es.REPLY_FAILED)
    assert [step["type"] for step in model.calls[1]] == ["user_input"]


async def test_a_failing_mark_read_does_not_block_the_reply() -> None:
    channel = FakeChannel(fail_mark_read=True)

    await handler(ScriptedModel()).handle(message("text"), channel)

    assert channel.sent == [(SENDER, REPLY_TEXT)]


async def test_messages_from_one_sender_are_answered_in_order() -> None:
    model, channel = ScriptedModel(delay_s=0.01), FakeChannel()
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


def test_chat_handler_needs_a_gemini_key_and_a_public_url() -> None:
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        build_inbound_handler(
            Settings(inbound_handler="chat", gemini_api_key=None),
            PublicImages(),
            MockPublisher(),
        )
    with pytest.raises(ValueError, match="PUBLIC_BACKEND_URL"):
        build_inbound_handler(
            Settings(inbound_handler="chat", gemini_api_key="key", public_backend_url=None),
            PublicImages(),
            MockPublisher(),
        )


def test_factory_builds_each_handler() -> None:
    chat = build_inbound_handler(
        Settings(
            inbound_handler="chat",
            gemini_api_key="key",
            public_backend_url="https://backend.test",
            image_gen="mock",
        ),
        PublicImages(),
        MockPublisher(),
    )
    echo = build_inbound_handler(Settings(inbound_handler="echo"), PublicImages(), MockPublisher())

    assert isinstance(chat, ChatHandler)
    assert isinstance(echo, EchoHandler)


async def test_the_wizard_photos_are_listed_for_the_model() -> None:
    model = ScriptedModel()
    chat, _ = build(model, library=FakeLibrary("Mesa nórdica: Mesa de roble en un living."))

    await chat.handle(
        message("text", text="hacé un post de la mesa nórdica"), channel := FakeChannel()
    )

    context = model.calls[0][-1]["content"][1]["text"]
    assert (
        "<brand_photos>\n- b1: Mesa nórdica: Mesa de roble en un living.\n</brand_photos>"
        in context
    )
    assert [block["type"] for block in model.calls[0][-1]["content"]] == ["text", "text"]
    assert channel.sent == [(SENDER, model.replies[0].text)]


async def test_a_post_can_use_a_wizard_photo() -> None:
    model = ScriptedModel(
        replies=[
            call_reply("create_post", brief="la mesa nórdica", asset_ids=["b1"], style="photos"),
            text_reply("Dale, lo armo con la foto de la mesa ⏳"),
        ]
    )
    channel = FakeChannel()
    chat, posts = build(model, library=FakeLibrary("Mesa nórdica: Mesa de roble."))

    await chat.handle(message("text", text="hacé un post de la mesa nórdica así nomás"), channel)
    await posts.join()

    assert json.loads(model.calls[1][-1]["result"])["status"] == "generating"
    assert len(channel.images) == 1
