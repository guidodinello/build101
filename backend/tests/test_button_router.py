import pytest

from app.conversation.button_router import ButtonRouter
from app.conversation.events import (
    PostApproved,
    PostChangeAsked,
    PostDiscarded,
    PostNotStarted,
    PostStarted,
    PublishStarted,
    StaleButton,
    buttons,
)
from app.conversation.photos import InMemoryPhotos
from app.media.public import PublicImages
from app.posts.drafts import PostCopy, PostDrafter
from app.posts.maker import PostMaker
from app.posts.publish import PostPublisher
from app.posts.store import InMemoryPosts, Post, PostImage, PostStatus
from app.publishing.base import PublishResult
from tests.conftest import make_image
from tests.fakes import CountingImageGen, FakeChannel, ScriptedModel

SENDER = "59899123456"
ACCOUNT = "acc_1"


class RecordingPublisher:
    def __init__(self) -> None:
        self.keys: list[str] = []

    async def publish(
        self, account_id: str, caption: str, media: object, idempotency_key: str, **_: object
    ) -> PublishResult:
        self.keys.append(idempotency_key)
        return PublishResult(status="published", permalink="https://instagram.com/p/x")


class Rig:
    def __init__(self) -> None:
        self.model = ScriptedModel(drafts={PostCopy: PostCopy(caption="Mesa", hashtags=[])})
        self.photos, self.store = InMemoryPhotos(), InMemoryPosts()
        images = PublicImages()
        self.maker = PostMaker(
            PostDrafter(self.model),
            CountingImageGen(),
            self.photos,
            images,
            self.store,
            "https://backend.test",
            max_posts_per_day=5,
        )
        self.publisher = RecordingPublisher()
        self.publishing = PostPublisher(
            self.publisher, self.store, images, "https://backend.test", ACCOUNT
        )
        self.events: list[object] = []

        async def notify(sender: str, event: object, channel: object) -> None:
            self.events.append(event)

        self.maker.on_event(notify)
        self.publishing.on_event(notify)
        self.channel = FakeChannel()
        self.router = ButtonRouter(self.store, self.maker, self.publishing, sessions=None)

    def add_post(self, post_id: str, status: PostStatus = "pending_approval") -> Post:
        photo = self.photos.add(SENDER, make_image((100, 100)), None)
        post = Post(
            post_id,
            SENDER,
            [PostImage(f"/media/{post_id}.jpg", make_image((1080, 1350)))],
            "Mesa",
            status=status,
            brief="la mesa",
            source_photos=[photo],
        )
        self.store.add(post)
        return post

    async def tap(self, button_id: str) -> object:
        return await self.router.handle(SENDER, button_id, self.channel)

    async def finish(self) -> None:
        await self.maker.join()
        await self.publishing.join()


@pytest.fixture
def rig() -> Rig:
    return Rig()


@pytest.mark.parametrize("button_id", ["nope", "variation_pick:p1:1", "post_schedule:p1", ""])
async def test_unknown_or_unbuilt_buttons_are_stale(rig: Rig, button_id: str) -> None:
    rig.add_post("p1", "approved")

    assert await rig.tap(button_id) == StaleButton()


async def test_noop_needs_no_answer(rig: Rig) -> None:
    assert await rig.tap("noop") is None


async def test_brand_buttons_are_stale_without_a_database(rig: Rig) -> None:
    assert await rig.tap("brand_ok") == StaleButton()
    assert await rig.tap("retry:abc") == StaleButton()


async def test_approve_works_once_and_offers_publish_now(rig: Rig) -> None:
    post = rig.add_post("p1")

    first = await rig.tap("post_approve:p1")
    second = await rig.tap("post_approve:p1")

    assert first == PostApproved("p1")
    assert post.status == "approved"
    assert [button.id for button in buttons(first)] == ["post_publish:p1"]
    assert second == StaleButton()


async def test_publish_needs_an_approved_post(rig: Rig) -> None:
    rig.add_post("p1")

    assert await rig.tap("post_publish:p1") == StaleButton()
    assert rig.publisher.keys == []


async def test_publish_now_publishes_the_approved_post(rig: Rig) -> None:
    post = rig.add_post("p1", "approved")

    event = await rig.tap("post_publish:p1")
    await rig.finish()

    assert event == PublishStarted("p1")
    assert post.status == "published"
    assert rig.publisher.keys == ["p1"]


async def test_retry_publishes_a_failed_post_under_a_new_key(rig: Rig) -> None:
    post = rig.add_post("p1", "failed")
    post.publish_attempts = 1

    event = await rig.tap("post_retry:p1")
    await rig.finish()

    assert event == PublishStarted("p1")
    assert rig.publisher.keys == ["p1-r2"]
    assert await rig.tap("post_retry:p1") == StaleButton()


async def test_discard_offers_another_and_replace_makes_it(rig: Rig) -> None:
    post = rig.add_post("p1")

    discarded = await rig.tap("post_discard:p1")
    replaced = await rig.tap("post_replace:p1")
    await rig.finish()

    assert discarded == PostDiscarded("p1")
    assert post.status == "discarded"
    assert [button.id for button in buttons(discarded)] == ["post_replace:p1", "noop"]
    assert isinstance(replaced, PostStarted) and replaced.origin == "Sí, otro"
    new = rig.store.get(SENDER, replaced.post_id)
    assert new is not None and new.brief == "la mesa"


async def test_change_tells_the_model_which_post_to_remake(rig: Rig) -> None:
    rig.add_post("p1")

    event = await rig.tap("post_change:p1")

    assert event == PostChangeAsked("p1")
    assert "revise_post with post_id=p1" in event.note()


async def test_photo_post_makes_a_post_from_the_photos_as_they_are(rig: Rig) -> None:
    photo = rig.photos.add(SENDER, make_image((100, 100)), None)

    event = await rig.tap(f"photo_post:{photo.id}")
    await rig.finish()

    assert isinstance(event, PostStarted)
    post = rig.store.get(SENDER, event.post_id)
    assert post is not None
    assert (post.style, [p.id for p in post.source_photos]) == ("photos", [photo.id])


async def test_photo_post_with_photos_that_expired(rig: Rig) -> None:
    assert await rig.tap("photo_post:f9") == PostNotStarted("unknown_asset")


async def test_subilo_can_still_publish_an_approved_post(rig: Rig) -> None:
    rig.add_post("p1", "approved")

    assert [post.id for post in rig.store.pending(SENDER)] == ["p1"]
