import asyncio
from datetime import datetime

import pytest

from app.conversation.button_router import ButtonRouter
from app.conversation.chat import ChatHandler
from app.conversation.history import InMemoryHistory
from app.conversation.photos import InMemoryPhotos
from app.copy import messages_es
from app.media.public import PublicImages
from app.posts.drafts import PostDrafter
from app.posts.maker import PostMaker
from app.posts.publish import MAX_RETRY_AFTER_S, PostPublisher
from app.posts.store import InMemoryPosts, Post, PostImage
from app.publishing.base import (
    PublisherError,
    PublishInProgress,
    PublishResult,
    PublishRetryable,
)
from app.publishing.mock import MOCK_ACCOUNT_ID, PERMALINK_PREFIX, MockPublisher
from tests.conftest import make_image
from tests.fakes import (
    PERMALINK,
    CountingImageGen,
    FakeChannel,
    FakePublisher,
    ScriptedModel,
    call_reply,
    text_reply,
)
from tests.test_chat_handler import SENDER, message

ACCOUNT_ID = "acc-1"
BASE_URL = "https://backend.test"
STARTED = text_reply("¡Dale, lo subo! ⏳")
ASK = text_reply("¿Lo subo?")


def approve(post_id: str) -> object:
    return call_reply("approve_post", post_id=post_id, next="publish_now")


class Rig:
    def __init__(
        self,
        model: ScriptedModel,
        publisher: FakePublisher | MockPublisher | None = None,
        account_id: str | None = ACCOUNT_ID,
        max_images: int = 200,
    ) -> None:
        self.model = model
        self.publisher = publisher or FakePublisher()
        self.sleeps: list[float] = []
        self.channel = FakeChannel()
        self.photos, self.history = InMemoryPhotos(), InMemoryHistory()
        self.store, self.images = InMemoryPosts(), PublicImages(max_images)

        async def sleep(seconds: float) -> None:
            self.sleeps.append(seconds)

        self.publishing = PostPublisher(
            self.publisher, self.store, self.history, self.images, BASE_URL, account_id, sleep
        )
        maker = PostMaker(
            PostDrafter(model),
            CountingImageGen(),
            self.photos,
            self.history,
            self.images,
            self.store,
            BASE_URL,
            max_posts_per_day=5,
        )
        self.chat = ChatHandler(
            model,
            self.history,
            self.photos,
            maker,
            self.publishing,
            self.store,
            ButtonRouter(self.store, maker, self.publishing, self.history, sessions=None),
            assistant_name="Mora",
            max_photo_mb=1,
            keep_alive_s=60.0,
        )

    def add_post(self, post_id: str, slides: int = 1) -> Post:
        images = [PostImage(self.images.add(make_image((80, 100))), b"jpeg") for _ in range(slides)]
        post = Post(post_id, SENDER, images, f"Caption {post_id} #muebles")
        self.store.add(post)
        return post

    async def say(self, text: str) -> None:
        await self.chat.handle(message("text", text=text), self.channel)

    async def finish(self) -> None:
        await self.publishing.join()

    @property
    def said(self) -> list[str]:
        return [text for _, text in self.channel.sent]


def status(rig: Rig, post_id: str) -> str:
    post = rig.store.get(SENDER, post_id)
    assert post is not None
    return post.status


async def test_subilo_publishes_the_one_pending_post_once_and_sends_the_link() -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED]))
    post = rig.add_post("p1")

    await rig.say("subilo")
    await rig.finish()

    [call] = rig.publisher.calls
    assert call["key"] == "p1"
    assert call["account_id"] == ACCOUNT_ID
    assert call["caption"] == "Caption p1 #muebles"
    assert call["media"].format == "image"
    assert call["media"].url == BASE_URL + post.images[0].path
    assert rig.said == [STARTED.text, messages_es.published(PERMALINK)]
    assert (post.status, post.permalink, post.external_post_id) == ("published", PERMALINK, "ext-1")


async def test_a_carousel_goes_out_with_its_slides_in_order() -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED]))
    post = rig.add_post("p1", slides=3)

    await rig.say("publicalo")
    await rig.finish()

    [call] = rig.publisher.calls
    assert call["media"].format == "carousel"
    assert call["media"].urls == [BASE_URL + image.path for image in post.images]


async def test_the_outcome_message_waits_for_the_turn_that_started_the_publish() -> None:
    # The publisher answers at once; the model's second call is slow.
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED], delay_s=0.1))
    rig.add_post("p1")

    await rig.say("subilo")
    await rig.finish()

    assert rig.said == [STARTED.text, messages_es.published(PERMALINK)]
    history = rig.history.get(SENDER)
    assert history[-1]["content"][0]["text"].startswith("[post p1 published]")  # after the turn


async def test_praise_does_not_publish_even_if_the_model_calls_the_tool() -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), ASK]))
    rig.add_post("p1")

    await rig.say("me encanta")
    await rig.finish()

    assert rig.publisher.calls == []
    assert status(rig, "p1") == "pending_approval"
    assert rig.said == [ASK.text]


async def test_subilo_with_two_pending_posts_asks_which_and_does_not_publish() -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), text_reply("¿Cuál subo? 1) … 2) …")]))
    rig.add_post("p1")
    rig.add_post("p2")

    await rig.say("subilo")
    await rig.finish()

    assert rig.publisher.calls == []
    assert [status(rig, "p1"), status(rig, "p2")] == ["pending_approval"] * 2


async def test_a_number_after_the_question_publishes_that_post() -> None:
    which = text_reply("¿Cuál subo? 1) … 2) …")
    rig = Rig(ScriptedModel(replies=[approve("p1"), which, approve("p2"), STARTED]))
    rig.add_post("p1")
    rig.add_post("p2")

    await rig.say("subilo")
    await rig.say("la segunda")
    await rig.finish()

    assert [call["key"] for call in rig.publisher.calls] == ["p2"]
    assert [status(rig, "p1"), status(rig, "p2")] == ["pending_approval", "published"]


async def test_the_model_cannot_pick_a_post_the_owner_did_not_choose() -> None:
    which = text_reply("¿Cuál subo?")
    rig = Rig(ScriptedModel(replies=[approve("p1"), which, approve("p1"), ASK]))
    rig.add_post("p1")
    rig.add_post("p2")

    await rig.say("subilo")
    await rig.say("la segunda")  # names p2, but the model calls the tool for p1
    await rig.finish()

    assert rig.publisher.calls == []


async def test_a_number_after_another_turn_does_not_publish() -> None:
    rig = Rig(
        ScriptedModel(
            replies=[approve("p1"), text_reply("¿Cuál?"), text_reply("Hola"), approve("p2"), ASK]
        )
    )
    rig.add_post("p1")
    rig.add_post("p2")

    await rig.say("subilo")
    await rig.say("hola")
    await rig.say("2")
    await rig.finish()

    assert rig.publisher.calls == []


async def test_subilo_with_nothing_pending_publishes_nothing() -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), text_reply("No tengo nada para subir")]))

    await rig.say("subilo")
    await rig.finish()

    assert rig.publisher.calls == []


async def test_a_second_subilo_while_publishing_does_not_publish_again() -> None:
    gate = asyncio.Event()
    rig = Rig(
        ScriptedModel(
            replies=[approve("p1"), STARTED, approve("p1"), text_reply("Ya se está subiendo")]
        ),
        FakePublisher(gate=gate),
    )
    rig.add_post("p1")

    await rig.say("subilo")
    await rig.say("subilo")
    gate.set()
    await rig.finish()

    assert len(rig.publisher.calls) == 1
    assert status(rig, "p1") == "published"


async def test_a_scheduled_approval_publishes_nothing() -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), text_reply("Programar no puedo todavía")]))
    rig.add_post("p1")

    await rig.say("subilo mañana a la tarde")
    await rig.finish()

    assert rig.publisher.calls == []


async def test_photos_in_the_turn_make_it_a_post_request_not_an_approval() -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), ASK]))
    rig.add_post("p1")
    rig.photos.add(SENDER, make_image((80, 100)), None)  # sent earlier, not used by a post yet

    await rig.say("subilas así")
    await rig.finish()

    assert rig.publisher.calls == []


async def test_a_voice_note_transcript_counts_as_the_owners_words() -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED]))
    rig.add_post("p1")
    audio = message("audio")
    assert audio.audio
    audio.audio.provider_transcript = "subilo"

    await rig.chat.handle(audio, rig.channel)
    await rig.finish()

    assert [call["key"] for call in rig.publisher.calls] == ["p1"]


async def test_without_an_instagram_account_nothing_is_published() -> None:
    rig = Rig(
        ScriptedModel(replies=[approve("p1"), text_reply("Falta conectar Instagram")]),
        account_id=None,
    )
    rig.add_post("p1")

    await rig.say("subilo")
    await rig.finish()

    assert rig.publisher.calls == []
    assert status(rig, "p1") == "pending_approval"


async def test_pending_is_not_reported_as_a_failure_and_is_not_published_again() -> None:
    pending = PublishResult(status="pending", external_post_id="ext-1", error="still publishing")
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED]), FakePublisher(results=[pending]))
    rig.add_post("p1")

    await rig.say("subilo")
    await rig.finish()

    assert rig.said == [STARTED.text, messages_es.PUBLISH_PENDING]
    assert status(rig, "p1") == "publish_pending"
    assert len(rig.publisher.calls) == 1


@pytest.mark.parametrize(
    "outcome",
    [PublishResult(status="failed", error="rejected"), PublisherError("zernio 400: bad")],
)
async def test_a_definite_failure_tells_the_owner_and_offers_a_retry(
    outcome: PublishResult | Exception,
) -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED]), FakePublisher(results=[outcome]))
    rig.add_post("p1")

    await rig.say("subilo")
    await rig.finish()

    assert rig.said == [STARTED.text]
    assert rig.channel.buttons == [(SENDER, messages_es.PUBLISH_FAILED, ["post_retry:p1"])]
    assert status(rig, "p1") == "failed"
    assert len(rig.publisher.calls) == 1


async def test_a_timeout_is_retried_once_with_the_same_key() -> None:
    results = [PublishRetryable("timeout"), PublishResult(status="published", permalink=PERMALINK)]
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED]), FakePublisher(results=results))
    rig.add_post("p1")

    await rig.say("subilo")
    await rig.finish()

    assert [call["key"] for call in rig.publisher.calls] == ["p1", "p1"]
    assert rig.said[-1] == messages_es.published(PERMALINK)


async def test_a_timeout_that_repeats_is_unknown_not_failed() -> None:
    rig = Rig(
        ScriptedModel(replies=[approve("p1"), STARTED]),
        FakePublisher(results=[PublishRetryable("timeout")]),
    )
    rig.add_post("p1")

    await rig.say("subilo")
    await rig.finish()

    assert len(rig.publisher.calls) == 2
    assert rig.said[-1] == messages_es.PUBLISH_PENDING
    assert status(rig, "p1") == "publish_pending"


@pytest.mark.parametrize(
    ("retry_after", "waited"),
    [(7.0, 7.0), (None, 5.0), (600.0, MAX_RETRY_AFTER_S)],
)
async def test_a_request_in_flight_waits_and_resends_with_the_same_key(
    retry_after: float | None, waited: float
) -> None:
    results = [
        PublishInProgress("in flight", retry_after),
        PublishResult(status="published", permalink=PERMALINK),
    ]
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED]), FakePublisher(results=results))
    rig.add_post("p1")

    await rig.say("subilo")
    await rig.finish()

    assert rig.sleeps == [waited]
    assert [call["key"] for call in rig.publisher.calls] == ["p1", "p1"]
    assert status(rig, "p1") == "published"


async def test_a_pending_post_keeps_its_images_served_after_others_push_it_out() -> None:
    rig = Rig(ScriptedModel(replies=[approve("p1"), STARTED]), max_images=3)
    post = rig.add_post("p1", slides=2)
    for _ in range(5):
        rig.images.add(b"newer")
    token = post.images[0].path.removeprefix("/media/").removesuffix(".jpg")
    assert rig.images.get(token) is None

    await rig.say("subilo")
    await rig.finish()

    assert all(
        rig.images.get(image.path.removeprefix("/media/").removesuffix(".jpg")) == b"jpeg"
        for image in post.images
    )


async def test_the_whole_flow_runs_offline_with_the_mock_publisher() -> None:
    rig = Rig(
        ScriptedModel(replies=[approve("p1"), STARTED]), MockPublisher(delay_s=0), MOCK_ACCOUNT_ID
    )
    rig.add_post("p1")

    await rig.say("subilo")
    await rig.finish()

    assert rig.said[-1].startswith(f"¡Publicado! 🎉 {PERMALINK_PREFIX}")
    assert status(rig, "p1") == "published"


def test_the_clock_is_only_used_for_created_at() -> None:
    assert isinstance(Post("p", SENDER, [], "c").created_at, datetime)


async def test_a_number_picks_the_post_that_was_listed_even_if_the_list_changed() -> None:
    which = text_reply("¿Cuál subo? 1) … 2) … 3) …")
    rig = Rig(ScriptedModel(replies=[approve("p1"), which, approve("p2"), STARTED]))
    first = rig.add_post("p1")
    rig.add_post("p2")
    rig.add_post("p3")

    await rig.say("subilo")
    first.status = "replaced"  # a remake retired p1 after the Owner saw the numbered list
    await rig.say("la segunda")  # "2" was p2 in that list
    await rig.finish()

    assert [call["key"] for call in rig.publisher.calls] == ["p2"]


async def test_a_listed_post_that_is_no_longer_pending_is_not_approved_by_its_number() -> None:
    which = text_reply("¿Cuál subo? 1) … 2) … 3) …")
    rig = Rig(ScriptedModel(replies=[approve("p1"), which, approve("p3"), ASK]))
    rig.add_post("p1")
    chosen = rig.add_post("p2")
    rig.add_post("p3")

    await rig.say("subilo")
    chosen.status = "replaced"
    await rig.say("la segunda")  # p2 is gone; the model must not slide to another post
    await rig.finish()

    assert rig.publisher.calls == []
