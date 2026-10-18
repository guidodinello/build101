from datetime import datetime, timedelta

import pytest
from sqlalchemy.exc import OperationalError

from app.agents.schemas import BrandBrain
from app.conversation.events import Event, PostFailed, PostSent
from app.conversation.photos import LOCAL_TZ, InMemoryPhotos
from app.media.images import POST_SIZE, image_size
from app.media.public import PublicImages
from app.posts.drafts import SYSTEM_PROMPT, CarouselDraft, PostCopy, PostDrafter, SlideDraft
from app.posts.maker import WHATSAPP_CAPTION_MAX, PostMaker
from app.posts.store import InMemoryPosts, Post, PostImage
from tests.conftest import make_image
from tests.fakes import CountingImageGen, FakeChannel, ScriptedModel, brand_brain

SENDER = "59899000001"
NOON = datetime(2026, 10, 17, 12, 0, tzinfo=LOCAL_TZ)
POST_TEXT = "Mesa de roble a medida\n\n#muebles #roble"
PHOTO_SIZES = [(100, 100), (120, 100), (140, 100)]


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


def maker(
    model: ScriptedModel,
    image_gen: CountingImageGen,
    photos: InMemoryPhotos,
    images: PublicImages | None = None,
    max_posts_per_day: int = 5,
    store: InMemoryPosts | None = None,
    events: list[Event] | None = None,
    brand: BrandBrain | None = None,
    brand_fails: bool = False,
) -> PostMaker:
    """A maker whose events go to `events` (a throwaway list when the test doesn't look)."""
    recorded = events if events is not None else []

    async def record(sender: str, event: Event, channel: object) -> None:
        recorded.append(event)

    async def brand_of(sender: str) -> BrandBrain | None:
        if brand_fails:
            raise OperationalError("select", {}, ConnectionError("database down"))
        return brand if sender == SENDER else None

    posts = PostMaker(
        PostDrafter(model),
        image_gen,
        photos,
        images or PublicImages(),
        store or InMemoryPosts(),
        "https://backend.test/",
        max_posts_per_day=max_posts_per_day,
        brand_of=brand_of,
        now=lambda: NOON,
    )
    posts.on_event(record)
    return posts


@pytest.fixture
def photos() -> InMemoryPhotos:
    store = InMemoryPhotos(now=lambda: NOON)
    for size in PHOTO_SIZES:
        store.add(SENDER, make_image(size), None)
    return store


def captions(channel: FakeChannel) -> list[str | None]:
    return [caption for _, _, caption in channel.images]


async def test_photos_as_they_are_make_a_carousel_with_the_text_on_the_first(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(
        drafts={
            PostCopy: PostCopy(caption="Mesa de roble a medida", hashtags=["#muebles", "#roble"])
        }
    )
    image_gen, channel, images = CountingImageGen(), FakeChannel(), PublicImages()
    posts = maker(model, image_gen, photos, images)

    result = posts.create_post(
        SENDER, {"brief": "muebles", "asset_ids": ["f1", "f2", "f3"], "style": "photos"}, channel
    )
    await posts.join()

    assert result["status"] == "generating"
    assert captions(channel) == [f"1/3\n\n{POST_TEXT}", "2/3", "3/3"]
    assert channel.sent == []
    assert image_gen.calls == []
    token = channel.images[0][1].removeprefix("https://backend.test/media/").removesuffix(".jpg")
    assert image_size(images.get(token)) == POST_SIZE
    assert [part["type"] for part in model.structured_calls[0]] == [
        "text",
        "image",
        "image",
        "image",
    ]


@pytest.mark.parametrize("style", ["photos", "design"])
async def test_the_post_is_written_with_the_owners_brand_brain(
    photos: InMemoryPhotos, style: str
) -> None:
    brand = brand_brain(
        voice=brand_brain().voice.model_copy(update={"dont": ["No usar 'barato'"]}),
        constraints=["Sin mostrar caras"],
    )
    model = ScriptedModel(
        drafts={
            PostCopy: PostCopy(caption="Mesa de roble a medida", hashtags=["#muebles"]),
            CarouselDraft: carousel_draft(3),
        }
    )
    posts = maker(model, CountingImageGen(), photos, brand=brand)

    posts.create_post(
        SENDER, {"brief": "muebles", "asset_ids": ["f1", "f2", "f3"], "style": style}, FakeChannel()
    )
    await posts.join()

    [system] = model.structured_systems
    assert system.startswith(SYSTEM_PROMPT)
    brain = system.removeprefix(SYSTEM_PROMPT)
    assert "<brand_brain>" in brain
    assert "No usar 'barato'" in brain
    assert "Sin mostrar caras" in brain
    assert "#111111" in brain
    assert "luz natural" in brain
    assert brand.whatsapp_summary not in brain
    assert "preferred_time" not in brain


async def test_without_a_brand_brain_the_post_gets_the_plain_instructions(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(
        drafts={PostCopy: PostCopy(caption="Mesa de roble a medida", hashtags=["#muebles"])}
    )
    posts = maker(model, CountingImageGen(), photos)

    posts.create_post(
        SENDER, {"brief": "muebles", "asset_ids": ["f1"], "style": "photos"}, FakeChannel()
    )
    await posts.join()

    assert model.structured_systems == [SYSTEM_PROMPT]


async def test_a_post_goes_without_the_brand_brain_when_the_database_fails(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(
        drafts={PostCopy: PostCopy(caption="Mesa de roble a medida", hashtags=["#muebles"])}
    )
    events: list[Event] = []
    posts = maker(model, CountingImageGen(), photos, events=events, brand_fails=True)

    posts.create_post(
        SENDER, {"brief": "muebles", "asset_ids": ["f1"], "style": "photos"}, FakeChannel()
    )
    await posts.join()

    assert model.structured_systems == [SYSTEM_PROMPT]
    assert [type(event) for event in events] == [PostSent]


async def test_one_photo_is_a_single_image_post_without_numbering(photos: InMemoryPhotos) -> None:
    model = ScriptedModel(
        drafts={
            PostCopy: PostCopy(caption="Mesa de roble a medida", hashtags=["#muebles", "#roble"])
        }
    )
    channel = FakeChannel()
    posts = maker(model, CountingImageGen(), photos)

    posts.create_post(SENDER, {"brief": "mesa", "asset_ids": ["f2"], "style": "photos"}, channel)
    await posts.join()

    assert captions(channel) == [POST_TEXT]


async def test_a_design_of_several_photos_builds_each_slide_from_its_photo(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(3)})
    image_gen, channel = CountingImageGen(), FakeChannel()
    posts = maker(model, image_gen, photos)

    posts.create_post(
        SENDER, {"brief": "muebles", "asset_ids": ["f1", "f2", "f3"], "style": "design"}, channel
    )
    await posts.join()

    assert captions(channel) == [f"1/3\n\n{POST_TEXT}", "2/3", "3/3"]
    assert [[image_size(ref) for ref in refs] for refs in image_gen.references] == [
        [size] for size in PHOTO_SIZES
    ]
    assert "Each slide is built from its own photo" in model.structured_calls[0][0]["text"]


async def test_a_design_with_a_slide_count_uses_all_photos_on_every_slide(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(5)})
    image_gen, channel = CountingImageGen(), FakeChannel()
    posts = maker(model, image_gen, photos)

    posts.create_post(
        SENDER,
        {"brief": "mesa", "asset_ids": ["f1"], "style": "design", "slide_count": 3},
        channel,
    )
    await posts.join()

    assert len(channel.images) == 3
    assert "(cover slide)" in image_gen.calls[0]
    assert all(len(refs) == 1 for refs in image_gen.references)


async def test_a_sent_design_emits_an_event_with_its_headlines_and_text(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(2)})
    events: list[Event] = []
    posts = maker(model, CountingImageGen(), photos, events=events)

    result = posts.create_post(
        SENDER, {"brief": "m", "asset_ids": ["f1", "f2"], "style": "design"}, FakeChannel()
    )
    await posts.join()

    assert events == [
        PostSent(result["post_id"], 2, "design", ("f1", "f2"), ("Slide 1", "Slide 2"), POST_TEXT)
    ]
    text = events[0].note()
    assert text.startswith(f"[post {result['post_id']} sent to the Owner] 2 image(s), design")
    assert "from photos f1 f2" in text
    assert 'Slide headlines: 1 "Slide 1"; 2 "Slide 2"' in text
    assert f'Text: "{POST_TEXT}"' in text


async def test_the_event_is_sent_once_the_guard_is_free(photos: InMemoryPhotos) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(1)})
    channel = FakeChannel()
    posts = maker(model, CountingImageGen(), photos)
    seen: list[tuple[str, Event, bool]] = []

    async def notify(sender: str, event: Event, to: object) -> None:
        assert to is channel
        # The guard is free, so an Owner turn can ask for another post meanwhile.
        seen.append((sender, event, SENDER in posts._generating))

    posts.on_event(notify)
    result = posts.create_post(
        SENDER, {"brief": "m", "asset_ids": ["f1"], "style": "design"}, channel
    )
    await posts.join()

    [(sender, event, generating)] = seen
    assert (sender, generating) == (SENDER, False)
    assert isinstance(event, PostSent) and event.post_id == result["post_id"]


async def test_a_failing_notify_is_not_a_failed_post(photos: InMemoryPhotos) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(1)})
    channel = FakeChannel()
    posts = maker(model, CountingImageGen(), photos)

    async def notify(sender: str, event: Event, to: object) -> None:
        raise RuntimeError("boom")

    posts.on_event(notify)
    posts.create_post(SENDER, {"brief": "m", "asset_ids": ["f1"], "style": "design"}, channel)
    await posts.join()

    assert channel.sent == []  # no failure message: the post arrived
    assert len(channel.images) == 1


async def test_without_a_registered_callback_the_generation_fails_loudly(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(1)})
    posts = PostMaker(
        PostDrafter(model),
        CountingImageGen(),
        photos,
        PublicImages(),
        InMemoryPosts(),
        "https://backend.test/",
        max_posts_per_day=5,
        now=lambda: NOON,
    )

    posts.create_post(SENDER, {"brief": "m", "asset_ids": ["f1"], "style": "design"}, FakeChannel())

    with pytest.raises(RuntimeError, match="on_event"):
        await posts.join()


async def test_a_text_too_long_for_a_caption_follows_the_images(photos: InMemoryPhotos) -> None:
    long_caption = "a" * WHATSAPP_CAPTION_MAX
    model = ScriptedModel(drafts={PostCopy: PostCopy(caption=long_caption, hashtags=[])})
    channel = FakeChannel()
    posts = maker(model, CountingImageGen(), photos)

    posts.create_post(SENDER, {"brief": "m", "asset_ids": ["f1", "f2"], "style": "photos"}, channel)
    await posts.join()

    assert captions(channel) == ["1/2", "2/2"]
    assert channel.sent == [(SENDER, long_caption)]


async def test_a_failed_generation_emits_the_failure_and_frees_the_guard(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(1)})
    channel, image_gen, events = FakeChannel(), CountingImageGen(fail=True), []
    posts = maker(model, image_gen, photos, events=events)
    request = {"brief": "mesa", "asset_ids": ["f1"], "style": "design"}

    result = posts.create_post(SENDER, request, channel)
    await posts.join()

    assert channel.sent == []  # the orchestrator tells the Owner, not the maker
    assert events == [PostFailed(result["post_id"], "design", ("f1",), "mesa")]
    assert "Nothing reached the Owner" in events[0].note()
    assert posts.create_post(SENDER, request, channel)["status"] == "generating"
    await posts.join()


async def test_only_designs_count_toward_the_daily_limit(photos: InMemoryPhotos) -> None:
    model = ScriptedModel(
        drafts={
            PostCopy: PostCopy(caption="c", hashtags=[]),
            CarouselDraft: carousel_draft(1),
        }
    )
    posts = maker(model, CountingImageGen(), photos, max_posts_per_day=1)
    as_they_are = {"brief": "m", "asset_ids": ["f1"], "style": "photos"}
    design = {"brief": "m", "asset_ids": ["f1"], "style": "design"}

    results = []
    for arguments in (as_they_are, as_they_are, design, as_they_are, design):
        results.append(posts.create_post(SENDER, arguments, FakeChannel()))
        await posts.join()

    assert [result.get("error") for result in results] == [None, None, None, None, "daily_limit"]


@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        ({"brief": "mesa", "asset_ids": ["f9"], "style": "photos"}, "unknown_asset"),
        ({"brief": "mesa", "asset_ids": [], "style": "photos"}, "no_photos"),
        ({"brief": "mesa", "asset_ids": ["f1"]}, "invalid_arguments"),
        ({"brief": "mesa", "asset_ids": ["f1"], "style": "reel"}, "invalid_arguments"),
        (
            {"brief": "mesa", "asset_ids": ["f1"], "style": "design", "slide_count": 11},
            "invalid_arguments",
        ),
    ],
)
async def test_bad_requests_start_nothing(
    photos: InMemoryPhotos, arguments: dict[str, object], error: str
) -> None:
    image_gen = CountingImageGen()
    posts = maker(ScriptedModel(), image_gen, photos)

    result = posts.create_post(SENDER, arguments, FakeChannel())
    await posts.join()

    assert result["error"] == error
    assert image_gen.calls == []


def test_recent_photos_expire_and_skip_used_ones() -> None:
    now = NOON
    photos = InMemoryPhotos(now=lambda: now)
    first = photos.add(SENDER, b"1", "mesa")
    photos.add(SENDER, b"2", None)
    first.used = True

    assert [photo.id for photo in photos.recent(SENDER)] == ["f2"]
    assert photos.find(SENDER, ["f1", "f7"]) == ([first], ["f7"])

    now = NOON + timedelta(minutes=31)
    assert photos.recent(SENDER) == []
    assert photos.find(SENDER, ["f1"]) == ([], ["f1"])


def test_photo_ids_are_not_reused_after_the_cap() -> None:
    photos = InMemoryPhotos(max_photos=2, now=lambda: NOON)
    for n in range(3):
        photos.add(SENDER, bytes([n]), None)

    assert [photo.id for photo in photos.recent(SENDER)] == ["f2", "f3"]


def photos_model() -> ScriptedModel:
    copy = PostCopy(caption="Mesa de roble a medida", hashtags=["#muebles", "#roble"])
    return ScriptedModel(drafts={PostCopy: copy})


async def test_a_sent_post_waits_for_approval_with_its_images_in_order(
    photos: InMemoryPhotos,
) -> None:
    store, channel = InMemoryPosts(), FakeChannel()
    posts = maker(photos_model(), CountingImageGen(), photos, store=store)

    result = posts.create_post(
        SENDER, {"brief": "mesa", "asset_ids": ["f1", "f2", "f3"], "style": "photos"}, channel
    )
    await posts.join()

    [post] = store.pending(SENDER)
    assert post.id == result["post_id"]
    assert (post.format, post.caption) == ("carousel", POST_TEXT)
    assert [f"https://backend.test{image.path}" for image in post.images] == [
        url for _, url, _ in channel.images
    ]


async def test_a_single_photo_is_stored_as_an_image_post(photos: InMemoryPhotos) -> None:
    store = InMemoryPosts()
    posts = maker(photos_model(), CountingImageGen(), photos, store=store)

    posts.create_post(
        SENDER, {"brief": "mesa", "asset_ids": ["f2"], "style": "photos"}, FakeChannel()
    )
    await posts.join()

    assert [post.format for post in store.pending(SENDER)] == ["image"]


async def test_a_failed_generation_stores_nothing(photos: InMemoryPhotos) -> None:
    store = InMemoryPosts()
    posts = maker(photos_model(), CountingImageGen(fail=True), photos, store=store)

    posts.create_post(
        SENDER, {"brief": "mesa", "asset_ids": ["f1"], "style": "design"}, FakeChannel()
    )
    await posts.join()

    assert store.pending(SENDER) == []


async def test_the_remade_post_replaces_the_old_one_only_once_it_is_sent(
    photos: InMemoryPhotos,
) -> None:
    store = InMemoryPosts()
    old = Post("old", SENDER, [PostImage("/media/x.jpg", b"x")], "caption")
    store.add(old)
    posts = maker(photos_model(), CountingImageGen(), photos, store=store)

    posts.create_post(
        SENDER,
        {"brief": "otro título", "asset_ids": ["f1"], "style": "photos", "replaces": "old"},
        FakeChannel(),
    )
    assert old.status == "pending_approval"  # still generating
    await posts.join()

    assert old.status == "replaced"
    assert [post.id for post in store.pending(SENDER)] != ["old"]
    assert len(store.pending(SENDER)) == 1


async def test_replacing_something_unknown_or_not_pending_is_ignored(
    photos: InMemoryPhotos,
) -> None:
    store = InMemoryPosts()
    published = Post("done", SENDER, [PostImage("/media/x.jpg", b"x")], "caption", "published")
    store.add(published)
    posts = maker(photos_model(), CountingImageGen(), photos, store=store)

    for replaces in ("done", "nope"):
        posts.create_post(
            SENDER,
            {"brief": "mesa", "asset_ids": ["f1"], "style": "photos", "replaces": replaces},
            FakeChannel(),
        )
        await posts.join()

    assert published.status == "published"
    assert len(store.pending(SENDER)) == 2


def test_a_publishing_post_is_never_dropped_to_make_room() -> None:
    store = InMemoryPosts(max_per_sender=2)
    busy = Post("busy", SENDER, [], "c", "publishing")
    for post in (busy, Post("a", SENDER, [], "c"), Post("b", SENDER, [], "c")):
        store.add(post)

    assert store.get(SENDER, "busy") is busy
    assert store.get(SENDER, "a") is None
    assert store.get(SENDER, "b") is not None
