"""The WhatsApp video flow (T61, ADR 0033): `create_video`, the video message, approval, reel."""

import json

import pytest

from app.channels.base import Button
from app.config import Settings
from app.conversation.button_router import ButtonRouter
from app.conversation.chat import ChatHandler
from app.conversation.events import StaleButton, VideoFailed
from app.conversation.factory import build_conversation
from app.conversation.history import InMemoryHistory
from app.conversation.photos import InMemoryPhotos, Photo, local_now
from app.copy import messages_es
from app.media.public import PublicImages, PublicVideos
from app.posts.drafts import PostDrafter
from app.posts.lifecycle import PostLifecycle
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import Post, PostImage, PostVideo
from app.posts.video_maker import VideoMaker
from app.publishing.mock import MOCK_ACCOUNT_ID
from app.rendering.mock import MockRenderer
from app.videogen.base import (
    GeneratedVideo,
    VideoGenBlocked,
    VideoGenError,
    VideoGenNoVideo,
    VideoGenRejected,
    VideoGenTimeout,
    VideoGenUnavailable,
)
from app.videogen.mock import MockVideoGen
from tests.conftest import make_image
from tests.fakes import (
    CountingImageGen,
    FakeChannel,
    FakePublisher,
    ScriptedModel,
    call_reply,
    text_reply,
)
from tests.test_chat_handler import SENDER, message

BASE_URL = "https://backend.test"
STARTED = text_reply("Dale, lo armo en video ⏳")
READY = text_reply("¡Listo el video! ¿Te gusta? ¿Lo subo, o le cambio algo?")
FAILED = text_reply("Uy, no me salió el video. El post sigue ahí.")
TOLD = text_reply("Listo, ya está.")


class CountingVideoGen:
    """The mock clip, counting calls; raises `error` instead when set."""

    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[str, list[bytes]]] = []
        self._error = error
        self._mock = MockVideoGen(delay_s=0)

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        *,
        aspect_ratio: str = "9:16",
        duration_seconds: int = 8,
    ) -> GeneratedVideo:
        self.calls.append((prompt, reference_images))
        if self._error is not None:
            raise self._error
        return await self._mock.generate(prompt, reference_images)


class Rig:
    def __init__(
        self, model: ScriptedModel, video_gen: CountingVideoGen | None, max_videos: int = 2
    ) -> None:
        self.model, self.video_gen = model, video_gen
        self.channel, self.publisher = FakeChannel(), FakePublisher()
        photos, store = InMemoryPhotos(), PostLifecycle()
        images, self.videos = PublicImages(), PublicVideos()
        self.store = store
        publishing = PostPublisher(
            self.publisher, store, images, BASE_URL, MOCK_ACCOUNT_ID, videos=self.videos
        )
        maker = PostMaker(
            PostDrafter(model),
            CountingImageGen(),
            MockRenderer(),
            photos,
            images,
            store,
            BASE_URL,
            max_posts_per_day=5,
        )
        self.maker = (
            VideoMaker(video_gen, store, self.videos, BASE_URL, max_videos) if video_gen else None
        )
        self.chat = ChatHandler(
            model,
            InMemoryHistory(),
            photos,
            maker,
            publishing,
            store,
            ButtonRouter(store, maker, publishing, sessions=None, videos=self.maker),
            None,
            assistant_name="Mora",
            max_photo_mb=1,
            keep_alive_s=60.0,
            videos=self.maker,
        )
        maker.on_event(self.chat.notify)
        publishing.on_event(self.chat.notify)
        if self.maker:
            self.maker.on_event(self.chat.notify)
        self.publishing = publishing

    def add_post(self, post_id: str = "p1") -> Post:
        photo = Photo("f1", make_image((900, 1200)), "mesa", local_now(), seen=True)
        post = Post(
            post_id,
            SENDER,
            [PostImage("/media/x.jpg", b"jpeg")],
            "Mesa de roble #muebles",
            source_photos=[photo],
        )
        self.store.add(post)
        return post

    async def say(self, text: str = "hacelo video") -> None:
        await self.chat.handle(message("text", text=text), self.channel)
        if self.maker:
            await self.maker.join()
        await self.chat.join()

    async def tap(self, button_id: str) -> None:
        tap = message("interactive").model_copy(
            update={"button": Button(id=button_id, title="x"), "kind": "button"}
        )
        await self.chat.handle(tap, self.channel)
        await self.publishing.join()
        await self.chat.join()

    def videos_of(self) -> list[Post]:
        return [post for post in self.store.all(SENDER) if post.video is not None]

    @property
    def said(self) -> list[str]:
        return [text for _, text in self.channel.sent]


def create_video(post_id: str = "p1") -> object:
    return call_reply("create_video", post_id=post_id)


async def test_flag_off_the_model_never_gets_the_tool_or_the_video_prompt() -> None:
    model = ScriptedModel(replies=[create_video(), text_reply("No puedo hacer videos.")])
    rig = Rig(model, None)
    rig.add_post()

    await rig.say()

    assert all(
        "create_video" not in [tool["name"] for tool in tools or []] for tools in model.tools_seen
    )
    assert "## Videos" not in model.systems[0]
    # It called the tool anyway: the answer is unknown_tool and nothing runs.
    assert "unknown_tool" in json.dumps(model.calls[1])
    assert rig.videos_of() == []
    assert rig.channel.video_headers == []


def test_flag_off_builds_no_video_maker_and_flag_on_builds_one() -> None:
    off = Settings(inbound_handler="chat", gemini_api_key="k", public_backend_url=BASE_URL)
    on = off.model_copy(update={"video_gen_enabled": True, "video_gen": "mock"})

    handler_off = build_conversation(off, PublicImages(), FakePublisher()).handler
    handler_on = build_conversation(on, PublicImages(), FakePublisher()).handler

    assert isinstance(handler_off, ChatHandler) and handler_off._videos is None
    assert isinstance(handler_on, ChatHandler) and handler_on._videos is not None
    assert "create_video" in [tool["name"] for tool in handler_on._tools]
    assert "create_video" not in [tool["name"] for tool in handler_off._tools]


async def test_request_sends_the_video_with_buttons_and_approval_publishes_a_reel() -> None:
    video_gen = CountingVideoGen()
    rig = Rig(ScriptedModel(replies=[create_video(), STARTED, READY, TOLD]), video_gen)
    source = rig.add_post()

    await rig.say()

    [video] = rig.videos_of()
    assert video.format == "reel"
    assert video.caption == source.caption
    assert source.status == "pending_approval"  # the image post is left as it was
    assert len(video_gen.calls) == 1
    assert video_gen.calls[0][1] == [source.source_photos[0].data]
    [(_, body, ids)] = rig.channel.buttons
    assert ids == [
        f"post_approve:{video.id}",
        f"post_change:{video.id}",
        f"post_discard:{video.id}",
    ]
    assert rig.channel.video_headers == [BASE_URL + video.video.path]  # type: ignore[union-attr]
    assert body == READY.text

    await rig.tap(f"post_approve:{video.id}")
    await rig.tap(f"post_publish:{video.id}")

    [call] = rig.publisher.calls
    assert call["media"].format == "reel"
    assert call["media"].url == BASE_URL + video.video.path  # type: ignore[union-attr]
    assert call["media"].ai_generated is True
    assert call["caption"] == source.caption
    assert rig.videos.get(video.video.path.removeprefix("/media/").removesuffix(".mp4"))  # type: ignore[union-attr]


async def test_nothing_publishes_a_video_the_owner_has_not_approved() -> None:
    rig = Rig(ScriptedModel(replies=[create_video(), STARTED, READY]), CountingVideoGen())
    rig.add_post()

    await rig.say()

    [video] = rig.videos_of()
    assert video.status == "pending_approval"
    assert rig.publisher.calls == []
    assert rig.publishing.publish_approved(SENDER, video.id, rig.channel) == {
        "error": "post_not_approved"
    }


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (VideoGenBlocked("safety"), "blocked"),
        (VideoGenRejected("bad request"), "rejected"),
        (VideoGenUnavailable("503"), "unavailable"),
        (VideoGenTimeout("slow"), "timeout"),
        (VideoGenNoVideo("empty"), "no_video"),
        (VideoGenError("other"), "failed"),
    ],
)
async def test_a_failed_generation_tells_the_owner_once_and_publishes_nothing(
    error: Exception, reason: str
) -> None:
    video_gen = CountingVideoGen(error)
    model = ScriptedModel(replies=[create_video(), STARTED, FAILED])
    rig = Rig(model, video_gen)
    rig.add_post()

    await rig.say()

    assert len(video_gen.calls) == 1  # never retried: a retry can bill a second clip
    assert rig.videos_of() == []
    assert rig.channel.buttons == []
    assert rig.publisher.calls == []
    assert rig.said == [STARTED.text, FAILED.text]
    assert f"({reason})" in model.calls[-1][-1]["content"][0]["text"]


async def test_the_event_falls_back_to_fixed_text_when_the_model_fails() -> None:
    rig = Rig(ScriptedModel(replies=[create_video(), STARTED]), CountingVideoGen())
    rig.add_post()
    await rig.say()
    rig.model.fail = True  # from here on, event turns fall back

    await rig.chat.notify(
        SENDER,
        VideoFailed("v1", "blocked", ("f1",)),
        rig.channel,
    )

    assert rig.said[-1] == messages_es.VIDEO_BLOCKED


async def test_blocked_is_refunded_but_other_failures_count_against_the_daily_limit() -> None:
    blocked = CountingVideoGen(VideoGenBlocked("safety"))
    rig = Rig(ScriptedModel(replies=[text_reply("ok")]), blocked, max_videos=1)
    rig.add_post()
    args = {"post_id": "p1"}

    for _ in range(2):  # each one is blocked, so each one is refunded and allowed
        assert rig.maker.create_video(SENDER, args, rig.channel)["status"] == "generating"  # type: ignore[union-attr]
        await rig.maker.join()  # type: ignore[union-attr]

    billed = CountingVideoGen(VideoGenUnavailable("503"))
    rig = Rig(ScriptedModel(replies=[text_reply("ok")]), billed, max_videos=1)
    rig.add_post()
    assert rig.maker.create_video(SENDER, args, rig.channel)["status"] == "generating"  # type: ignore[union-attr]
    await rig.maker.join()  # type: ignore[union-attr]
    assert rig.maker.create_video(SENDER, args, rig.channel) == {"error": "video_daily_limit"}  # type: ignore[union-attr]
    assert len(billed.calls) == 1


async def test_guards_run_in_code() -> None:
    rig = Rig(ScriptedModel(replies=[text_reply("ok")]), CountingVideoGen())
    assert rig.maker is not None
    rig.add_post()
    spent = rig.add_post("p2")
    rig.store.published(spent, None, None)
    bare = Post("p3", SENDER, [PostImage("/media/y.jpg", b"jpeg")], "caption")
    rig.store.add(bare)

    assert rig.maker.create_video(SENDER, {"post_id": "nope"}, rig.channel) == {
        "error": "unknown_post"
    }
    assert rig.maker.create_video(SENDER, {"post_id": "p2"}, rig.channel)["error"] == (
        "post_not_pending"
    )
    assert rig.maker.create_video(SENDER, {"post_id": "p3"}, rig.channel) == {"error": "no_photos"}
    assert rig.maker.create_video(SENDER, {"nope": 1}, rig.channel)["error"] == "invalid_arguments"
    assert rig.maker.create_video(SENDER, {"post_id": "p1"}, rig.channel)["status"] == "generating"
    assert rig.maker.create_video(SENDER, {"post_id": "p1"}, rig.channel) == {
        "error": "generation_in_progress"
    }
    await rig.maker.join()


async def test_an_event_turn_cannot_start_a_video() -> None:
    video_gen = CountingVideoGen()
    rig = Rig(ScriptedModel(replies=[create_video(), text_reply("No.")]), video_gen)
    rig.add_post()

    await rig.chat.notify(
        SENDER,
        StaleButton(),
        rig.channel,
    )

    assert video_gen.calls == []


async def test_revise_post_does_not_touch_a_video_post() -> None:
    rig = Rig(ScriptedModel(replies=[create_video(), STARTED, READY]), CountingVideoGen())
    rig.add_post()
    await rig.say()
    [video] = rig.videos_of()
    posts = rig.chat._posts

    result = posts.revise_post(
        SENDER, {"post_id": video.id, "change": "más corto", "part": "caption"}, rig.channel
    )

    assert result == {"error": "video_post"}


async def test_another_after_discarding_a_video_makes_a_new_video_and_leaves_the_source() -> None:
    video_gen = CountingVideoGen()
    rig = Rig(ScriptedModel(replies=[create_video(), STARTED, READY, TOLD]), video_gen)
    source = rig.add_post()
    await rig.say()
    [first] = rig.videos_of()

    await rig.tap(f"post_discard:{first.id}")
    await rig.tap(f"post_replace:{first.id}")
    await rig.maker.join()  # type: ignore[union-attr]
    await rig.chat.join()

    assert len(video_gen.calls) == 2
    assert len(rig.videos_of()) == 2
    assert first.status == "replaced"  # consumed by the tap
    assert source.status == "pending_approval"
    assert [post.status for post in rig.videos_of()] == ["replaced", "pending_approval"]


async def test_another_is_one_shot_for_a_discarded_video() -> None:
    video_gen = CountingVideoGen()
    rig = Rig(ScriptedModel(replies=[create_video(), STARTED, READY, TOLD]), video_gen)
    rig.add_post()
    await rig.say()
    [first] = rig.videos_of()
    await rig.tap(f"post_discard:{first.id}")

    await rig.tap(f"post_replace:{first.id}")
    await rig.tap(f"post_replace:{first.id}")  # a second tap on the same button
    await rig.maker.join()  # type: ignore[union-attr]

    assert len(video_gen.calls) == 2  # the request, and one remake
    assert first.status == "replaced"
    assert len(rig.videos_of()) == 2


async def test_another_on_a_video_post_is_stale_with_the_flag_off() -> None:
    rig = Rig(ScriptedModel(replies=[text_reply("ok")]), None)
    source = rig.add_post()
    video = Post(
        "v1",
        SENDER,
        [],
        source.caption,
        status="discarded",
        source_photos=source.source_photos,
        video=PostVideo("/media/v.mp4", b"mp4"),
    )
    rig.store.add(video)

    event = await rig.chat._buttons.handle(SENDER, "post_replace:v1", rig.channel)

    assert event == StaleButton()
    assert video.status == "discarded"


async def test_an_unwired_maker_refuses_before_any_generation() -> None:
    video_gen = CountingVideoGen()
    rig = Rig(ScriptedModel(replies=[text_reply("ok")]), video_gen)
    rig.add_post()
    unwired = VideoMaker(video_gen, rig.store, rig.videos, BASE_URL, 2)

    with pytest.raises(RuntimeError, match="on_event"):
        unwired.create_video(SENDER, {"post_id": "p1"}, rig.channel)

    assert video_gen.calls == []


async def test_a_sent_video_stays_served_after_the_cache_cap_of_later_clips() -> None:
    """The Owner's header link and Zernio's fetch must not 404 once other clips evict it."""
    rig = Rig(ScriptedModel(replies=[create_video(), STARTED, READY, TOLD]), CountingVideoGen())
    rig.videos = PublicVideos(max_videos=2)
    rig.videos.serve_from(rig.store.video)  # what the factory wires
    rig.maker._videos = rig.videos  # type: ignore[union-attr]
    rig.add_post()
    await rig.say()
    [video] = rig.videos_of()
    assert video.video is not None
    token = video.video.path.removeprefix("/media/").removesuffix(".mp4")

    for _ in range(5):  # clips of other senders
        rig.videos.add(b"other")

    assert rig.videos.get(token) == video.video.data


def test_the_factory_lets_the_clip_cache_fall_back_to_the_posts() -> None:
    videos = PublicVideos()
    settings = Settings(inbound_handler="chat", gemini_api_key="k", public_backend_url=BASE_URL)

    build_conversation(settings, PublicImages(), FakePublisher(), videos)

    assert videos._lookup is not None
