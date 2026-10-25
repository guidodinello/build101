from dataclasses import dataclass
from datetime import datetime, timedelta
from io import BytesIO

import pytest
from PIL import Image

from app.agents.schemas import BrandBrain
from app.background import BackgroundWork
from app.conversation.events import Event, Notify, PostFailed, PostSent
from app.conversation.photos import LOCAL_TZ, InMemoryPhotos
from app.knowledge.base import BusinessKnowledge, Note
from app.media.images import POST_SIZE, image_size
from app.media.public import PublicImages
from app.posts.drafts import SYSTEM_PROMPT, CarouselDraft, PostCopy, PostDrafter, SlideDraft
from app.posts.lifecycle import PostLifecycle
from app.posts.maker import WHATSAPP_CAPTION_MAX, PostMaker
from app.posts.store import InMemoryPosts, Post, PostImage
from app.rendering.mock import MockRenderer
from tests.conftest import make_image
from tests.fakes import CountingImageGen, FakeChannel, ScriptedModel, brand_brain

SENDER = "59899000001"
NOON = datetime(2026, 10, 17, 12, 0, tzinfo=LOCAL_TZ)
POST_TEXT = "Mesa de roble a medida\n\n#muebles #roble"
PHOTO_SIZES = [(100, 100), (120, 100), (140, 100)]


@dataclass
class FakeKnowledge:
    """What the Agency knows about SENDER's Business; nothing for anyone else."""

    known: BusinessKnowledge
    asked: list[str]

    def __init__(self, known: BusinessKnowledge) -> None:
        self.known = known
        self.asked = []

    async def of(self, sender: str) -> BusinessKnowledge:
        self.asked.append(sender)
        return self.known if sender == SENDER else BusinessKnowledge()


def carousel_draft(slides: int, family: str = "editorial") -> CarouselDraft:
    return CarouselDraft(
        caption="Mesa de roble a medida",
        hashtags=["#muebles", "#roble"],
        family=family,
        style_prompt="warm",
        style_notes="cálido",
        slides=[
            SlideDraft(
                role="content",
                kicker=f"Tip {n}",
                headline=f"Slide {n}",
                body="",
                scene_prompt=f"scene {n}",
            )
            for n in range(1, slides + 1)
        ],
    )


async def drop(sender: str, event: Event, channel: object) -> None:
    """A notify for tests that don't look at the events."""


def recorder(events: list[Event]) -> Notify:
    async def record(sender: str, event: Event, channel: object) -> None:
        events.append(event)

    return record


def maker(
    model: ScriptedModel,
    image_gen: CountingImageGen,
    photos: InMemoryPhotos,
    images: PublicImages | None = None,
    max_posts_per_day: int = 5,
    store: PostLifecycle | None = None,
    brand: BrandBrain | None = None,
    renderer: MockRenderer | None = None,
    notes: list[str] | None = None,
    trend_notes: str | None = None,
    knowledge: FakeKnowledge | None = None,
) -> tuple[PostMaker, BackgroundWork]:
    """A maker and the background work to join."""
    background = BackgroundWork()
    posts = PostMaker(
        PostDrafter(model),
        image_gen,
        renderer or MockRenderer(),
        photos,
        images or PublicImages(),
        store or PostLifecycle(),
        "https://backend.test/",
        max_posts_per_day=max_posts_per_day,
        knowledge=knowledge
        or FakeKnowledge(
            BusinessKnowledge(
                brand=brand,
                notes=[Note(f"n{n}", text) for n, text in enumerate(notes or [], start=1)],
                trend_notes=trend_notes,
            )
        ),
        now=lambda: NOON,
        background=background,
    )
    return posts, background


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
    posts, background = maker(model, image_gen, photos, images)

    result = posts.create_post(
        SENDER,
        {"brief": "muebles", "asset_ids": ["f1", "f2", "f3"], "style": "photos"},
        channel,
        drop,
    )
    await background.join()

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
    posts, background = maker(model, CountingImageGen(), photos, brand=brand)

    posts.create_post(
        SENDER,
        {"brief": "muebles", "asset_ids": ["f1", "f2", "f3"], "style": style},
        FakeChannel(),
        drop,
    )
    await background.join()

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
    posts, background = maker(model, CountingImageGen(), photos)

    posts.create_post(
        SENDER, {"brief": "muebles", "asset_ids": ["f1"], "style": "photos"}, FakeChannel(), drop
    )
    await background.join()

    assert model.structured_systems == [SYSTEM_PROMPT]


async def test_a_post_goes_without_the_brand_brain_when_nothing_is_known(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(
        drafts={PostCopy: PostCopy(caption="Mesa de roble a medida", hashtags=["#muebles"])}
    )
    events: list[Event] = []
    posts, background = maker(
        model,
        CountingImageGen(),
        photos,
        knowledge=FakeKnowledge(BusinessKnowledge()),
    )

    posts.create_post(
        SENDER,
        {"brief": "muebles", "asset_ids": ["f1"], "style": "photos"},
        FakeChannel(),
        recorder(events),
    )
    await background.join()

    assert model.structured_systems == [SYSTEM_PROMPT]
    assert [type(event) for event in events] == [PostSent]


async def test_the_senders_trend_notes_reach_the_draft(photos: InMemoryPhotos) -> None:
    model = ScriptedModel(drafts={PostCopy: PostCopy(caption="Mesa", hashtags=[])})
    knowledge = FakeKnowledge(BusinessKnowledge(trend_notes="- [hook] Pieza heredable."))
    posts, background = maker(model, CountingImageGen(), photos, knowledge=knowledge)
    posts.create_post(
        SENDER, {"brief": "mesa", "asset_ids": ["f1"], "style": "photos"}, FakeChannel(), drop
    )
    await background.join()

    assert knowledge.asked == [SENDER]
    assert '"- [hook] Pieza heredable."' in model.structured_calls[0][0]["text"]


async def test_one_photo_is_a_single_image_post_without_numbering(photos: InMemoryPhotos) -> None:
    model = ScriptedModel(
        drafts={
            PostCopy: PostCopy(caption="Mesa de roble a medida", hashtags=["#muebles", "#roble"])
        }
    )
    channel = FakeChannel()
    posts, background = maker(model, CountingImageGen(), photos)

    posts.create_post(
        SENDER, {"brief": "mesa", "asset_ids": ["f2"], "style": "photos"}, channel, drop
    )
    await background.join()

    assert captions(channel) == [POST_TEXT]


async def test_a_design_of_several_photos_builds_each_slide_from_its_photo(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(3)})
    image_gen, channel = CountingImageGen(), FakeChannel()
    posts, background = maker(model, image_gen, photos)

    posts.create_post(
        SENDER,
        {"brief": "muebles", "asset_ids": ["f1", "f2", "f3"], "style": "design"},
        channel,
        drop,
    )
    await background.join()

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
    posts, background = maker(model, image_gen, photos)

    posts.create_post(
        SENDER,
        {"brief": "mesa", "asset_ids": ["f1"], "style": "design", "slide_count": 3},
        channel,
        drop,
    )
    await background.join()

    assert len(channel.images) == 3
    assert "(cover slide)" in image_gen.calls[0]
    assert all(len(refs) == 1 for refs in image_gen.references)


async def test_a_sent_design_emits_an_event_with_its_headlines_and_text(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(2)})
    events: list[Event] = []
    posts, background = maker(model, CountingImageGen(), photos)

    result = posts.create_post(
        SENDER,
        {"brief": "m", "asset_ids": ["f1", "f2"], "style": "design"},
        FakeChannel(),
        recorder(events),
    )
    await background.join()

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
    posts, background = maker(model, CountingImageGen(), photos)
    seen: list[tuple[str, Event, bool]] = []

    async def notify(sender: str, event: Event, to: object) -> None:
        assert to is channel
        # The guard is free, so an Owner turn can ask for another post meanwhile.
        seen.append((sender, event, SENDER in posts._generating))

    result = posts.create_post(
        SENDER, {"brief": "m", "asset_ids": ["f1"], "style": "design"}, channel, notify
    )
    await background.join()

    [(sender, event, generating)] = seen
    assert (sender, generating) == (SENDER, False)
    assert isinstance(event, PostSent) and event.post_id == result["post_id"]


async def test_a_failing_notify_is_not_a_failed_post(photos: InMemoryPhotos) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(1)})
    channel = FakeChannel()
    posts, background = maker(model, CountingImageGen(), photos)

    async def notify(sender: str, event: Event, to: object) -> None:
        raise RuntimeError("boom")

    posts.create_post(
        SENDER, {"brief": "m", "asset_ids": ["f1"], "style": "design"}, channel, notify
    )
    await background.join()

    assert channel.sent == []  # no failure message: the post arrived
    assert len(channel.images) == 1


async def test_a_text_too_long_for_a_caption_follows_the_images(photos: InMemoryPhotos) -> None:
    long_caption = "a" * WHATSAPP_CAPTION_MAX
    model = ScriptedModel(drafts={PostCopy: PostCopy(caption=long_caption, hashtags=[])})
    channel = FakeChannel()
    posts, background = maker(model, CountingImageGen(), photos)

    posts.create_post(
        SENDER, {"brief": "m", "asset_ids": ["f1", "f2"], "style": "photos"}, channel, drop
    )
    await background.join()

    assert captions(channel) == ["1/2", "2/2"]
    assert channel.sent == [(SENDER, long_caption)]


async def test_a_failed_generation_emits_the_failure_and_frees_the_guard(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(1)})
    channel, image_gen, events = FakeChannel(), CountingImageGen(fail=True), []
    posts, background = maker(model, image_gen, photos)
    request = {"brief": "mesa", "asset_ids": ["f1"], "style": "design"}

    result = posts.create_post(SENDER, request, channel, recorder(events))
    await background.join()

    assert channel.sent == []  # the orchestrator tells the Owner, not the maker
    assert events == [PostFailed(result["post_id"], "design", ("f1",), "mesa")]
    assert "Nothing reached the Owner" in events[0].note()
    assert posts.create_post(SENDER, request, channel, recorder(events))["status"] == "generating"
    await background.join()

async def test_a_partial_send_keeps_sent_images_and_reports_the_count(
    photos: InMemoryPhotos,
) -> None:
    class FailSecondImageChannel(FakeChannel):
        attempts: int = 0

        async def send_image(
            self, to: str, image_url: str, caption: str | None = None
        ) -> str:
            self.attempts += 1
            if self.attempts == 2:
                raise RuntimeError("second image failed")
            return await super().send_image(to, image_url, caption)

    store = PostLifecycle()
    channel = FailSecondImageChannel()
    events: list[Event] = []
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(2)})
    posts, background = maker(model, CountingImageGen(), photos, store=store)

    result = posts.create_post(
        SENDER,
        {"brief": "mesa", "asset_ids": ["f1", "f2"], "style": "design"},
        channel,
        recorder(events),
    )
    await background.join()

    assert len(channel.images) == 1
    assert len(store.pending(SENDER)) == 1
    saved = store.pending(SENDER)[0]
    assert len(saved.images) == 1
    assert saved.headlines == ["Slide 1"]
    assert events == [
        PostFailed(result["post_id"], "design", ("f1", "f2"), "mesa", sent_count=1)
    ]
    assert "1 slide(s) reached the Owner" in events[0].note()



async def test_only_designs_count_toward_the_daily_limit(photos: InMemoryPhotos) -> None:
    model = ScriptedModel(
        drafts={
            PostCopy: PostCopy(caption="c", hashtags=[]),
            CarouselDraft: carousel_draft(1),
        }
    )
    posts, background = maker(model, CountingImageGen(), photos, max_posts_per_day=1)
    as_they_are = {"brief": "m", "asset_ids": ["f1"], "style": "photos"}
    design = {"brief": "m", "asset_ids": ["f1"], "style": "design"}

    results = []
    for arguments in (as_they_are, as_they_are, design, as_they_are, design):
        results.append(posts.create_post(SENDER, arguments, FakeChannel(), drop))
        await background.join()

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
    posts, background = maker(ScriptedModel(), image_gen, photos)

    result = posts.create_post(SENDER, arguments, FakeChannel(), drop)
    await background.join()

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
    store, channel = PostLifecycle(), FakeChannel()
    posts, background = maker(photos_model(), CountingImageGen(), photos, store=store)

    result = posts.create_post(
        SENDER, {"brief": "mesa", "asset_ids": ["f1", "f2", "f3"], "style": "photos"}, channel, drop
    )
    await background.join()

    [post] = store.pending(SENDER)
    assert post.id == result["post_id"]
    assert (post.format, post.caption) == ("carousel", POST_TEXT)
    assert [f"https://backend.test{image.path}" for image in post.images] == [
        url for _, url, _ in channel.images
    ]


async def test_a_single_photo_is_stored_as_an_image_post(photos: InMemoryPhotos) -> None:
    store = PostLifecycle()
    posts, background = maker(photos_model(), CountingImageGen(), photos, store=store)

    posts.create_post(
        SENDER, {"brief": "mesa", "asset_ids": ["f2"], "style": "photos"}, FakeChannel(), drop
    )
    await background.join()

    assert [post.format for post in store.pending(SENDER)] == ["image"]


async def test_a_failed_generation_stores_nothing(photos: InMemoryPhotos) -> None:
    store = PostLifecycle()
    posts, background = maker(photos_model(), CountingImageGen(fail=True), photos, store=store)

    posts.create_post(
        SENDER, {"brief": "mesa", "asset_ids": ["f1"], "style": "design"}, FakeChannel(), drop
    )
    await background.join()

    assert store.pending(SENDER) == []


async def test_the_remade_post_replaces_the_old_one_only_once_it_is_sent(
    photos: InMemoryPhotos,
) -> None:
    store = PostLifecycle()
    old = Post("old", SENDER, [PostImage("/media/x.jpg", b"x")], "caption")
    store.add(old)
    posts, background = maker(photos_model(), CountingImageGen(), photos, store=store)

    posts.create_post(
        SENDER,
        {"brief": "otro título", "asset_ids": ["f1"], "style": "photos", "replaces": "old"},
        FakeChannel(),
        drop,
    )
    assert old.status == "pending_approval"  # still generating
    await background.join()

    assert old.status == "replaced"
    assert [post.id for post in store.pending(SENDER)] != ["old"]
    assert len(store.pending(SENDER)) == 1


async def test_replacing_something_unknown_or_not_pending_is_ignored(
    photos: InMemoryPhotos,
) -> None:
    store = PostLifecycle()
    published = Post("done", SENDER, [PostImage("/media/x.jpg", b"x")], "caption", "published")
    store.add(published)
    posts, background = maker(photos_model(), CountingImageGen(), photos, store=store)

    for replaces in ("done", "nope"):
        posts.create_post(
            SENDER,
            {"brief": "mesa", "asset_ids": ["f1"], "style": "photos", "replaces": replaces},
            FakeChannel(),
            drop,
        )
        await background.join()

    assert published.status == "published"
    assert len(store.pending(SENDER)) == 2


def test_a_publishing_post_is_never_dropped_to_make_room() -> None:
    store = PostLifecycle(InMemoryPosts(max_per_sender=2))
    busy = Post("busy", SENDER, [], "c", "publishing")
    for post in (busy, Post("a", SENDER, [], "c"), Post("b", SENDER, [], "c")):
        store.add(post)

    assert store.get(SENDER, "busy") is busy
    assert store.get(SENDER, "a") is None
    assert store.get(SENDER, "b") is not None


LOGO_RED = (220, 0, 0)


def bottom_right_pixel(data: bytes) -> tuple[int, int, int]:
    """A pixel inside the logo's corner: 4% margin, then into the logo."""
    with Image.open(BytesIO(data)) as image:
        return image.convert("RGB").getpixel((image.width - 60, image.height - 60))


async def test_a_post_with_the_logo_stamps_it_on_every_image(photos: InMemoryPhotos) -> None:
    photos.set_logo(SENDER, make_image((300, 120), color="#dc0000", format="PNG"))
    model = ScriptedModel(drafts={PostCopy: PostCopy(caption="Mesa", hashtags=["#muebles"])})
    store = PostLifecycle()
    posts, background = maker(model, CountingImageGen(), photos, store=store)

    result = posts.create_post(
        SENDER,
        {"brief": "mesa", "asset_ids": ["f1", "f2"], "style": "photos", "with_logo": True},
        FakeChannel(),
        drop,
    )
    await background.join()

    post = store.get(SENDER, result["post_id"])
    assert post is not None and post.with_logo
    for image in post.images:
        red, green, blue = bottom_right_pixel(image.data)
        assert red > 180 and green < 60 and blue < 60


async def test_a_design_hands_the_logo_to_the_template_instead_of_stamping_it(
    photos: InMemoryPhotos,
) -> None:
    photos.set_logo(SENDER, make_image((300, 120), color="#dc0000", format="PNG"))
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(2)})
    renderer, store = MockRenderer(), PostLifecycle()
    posts, background = maker(model, CountingImageGen(), photos, store=store, renderer=renderer)

    result = posts.create_post(
        SENDER,
        {"brief": "mesa", "asset_ids": ["f1", "f2"], "style": "design", "with_logo": True},
        FakeChannel(),
        drop,
    )
    await background.join()

    assert [slide.logo is not None for slide in renderer.slides] == [True, True]
    assert renderer.slides[0].logo is not None and renderer.slides[0].logo.tone == "dark"
    post = store.get(SENDER, result["post_id"])
    assert post is not None
    assert all(bottom_right_pixel(image.data)[0] < 180 for image in post.images)


async def test_every_designed_slide_is_rendered_from_its_copy_and_the_brand(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(3, family="numbers")})
    renderer = MockRenderer()
    posts, background = maker(
        model, CountingImageGen(), photos, brand=brand_brain(), renderer=renderer
    )

    posts.create_post(
        SENDER,
        {"brief": "mesa", "asset_ids": ["f1", "f2", "f3"], "style": "design"},
        FakeChannel(),
        drop,
    )
    await background.join()

    assert [(s.family, s.index, s.count, s.role) for s in renderer.slides] == [
        ("numbers", 1, 3, "cover"),
        ("numbers", 2, 3, "content"),
        ("numbers", 3, 3, "content"),
    ]
    second = renderer.slides[1]
    assert (second.kicker, second.headline, second.body) == ("Tip 2", "Slide 2", None)
    assert all(s.logo is None for s in renderer.slides)
    assert renderer.slides[0].brand.name == brand_brain().business_name


async def test_a_panorama_built_from_one_photo_per_slide_falls_back_to_editorial(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(3, family="panorama")})
    image_gen, renderer = CountingImageGen(), MockRenderer()
    posts, background = maker(model, image_gen, photos, renderer=renderer)

    posts.create_post(
        SENDER,
        {"brief": "mesa", "asset_ids": ["f1", "f2", "f3"], "style": "design"},
        FakeChannel(),
        drop,
    )
    await background.join()

    assert {slide.family for slide in renderer.slides} == {"editorial"}
    assert len(image_gen.calls) == 3


async def test_a_post_with_the_logo_without_one_is_refused(photos: InMemoryPhotos) -> None:
    model = ScriptedModel(drafts={PostCopy: PostCopy(caption="Mesa", hashtags=["#muebles"])})
    channel = FakeChannel()
    posts, background = maker(model, CountingImageGen(), photos)

    result = posts.create_post(
        SENDER,
        {"brief": "mesa", "asset_ids": ["f1"], "style": "photos", "with_logo": True},
        channel,
        drop,
    )

    assert result == {"error": "no_logo"}
    assert channel.images == []
    assert model.structured_calls == []


def sent_design(store: PostLifecycle, photos: InMemoryPhotos) -> Post:
    found, _ = photos.find(SENDER, ["f1", "f2"])
    post = Post(
        "old",
        SENDER,
        [PostImage("/media/a.jpg", make_image((1080, 1350))), PostImage("/media/b.jpg", b"")],
        "Mesa de roble\n\n#muebles",
        brief="mesa nueva",
        style="design",
        source_photos=found,
        headlines=["Roble macizo", "Hecha a mano"],
        style_prompt="warm, beige",
    )
    store.add(post)
    return post


async def test_a_caption_change_keeps_the_images_and_generates_nothing(
    photos: InMemoryPhotos,
) -> None:
    store, image_gen, channel = PostLifecycle(), CountingImageGen(), FakeChannel()
    events: list[Event] = []
    old = sent_design(store, photos)
    posts, background = maker(photos_model(), image_gen, photos, store=store, max_posts_per_day=0)

    result = posts.revise_post(
        SENDER,
        {"post_id": "old", "change": "más corto", "part": "caption"},
        channel,
        recorder(events),
    )
    await background.join()

    assert result["status"] == "generating"
    assert image_gen.calls == []  # not even the daily limit applies
    [new] = store.pending(SENDER)
    assert [image.data for image in new.images] == [image.data for image in old.images]
    assert (new.headlines, new.style_prompt) == (old.headlines, old.style_prompt)
    assert new.brief == "mesa nueva\nCambio: más corto"
    assert old.status == "replaced"
    assert isinstance(events[0], PostSent)


async def test_an_image_change_regenerates_the_design_from_the_previous_one(
    photos: InMemoryPhotos,
) -> None:
    store, image_gen = PostLifecycle(), CountingImageGen()
    sent_design(store, photos)
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(2)})
    posts, background = maker(model, image_gen, photos, store=store)

    posts.revise_post(
        SENDER, {"post_id": "old", "change": "fondo verde", "part": "images"}, FakeChannel(), drop
    )
    await background.join()

    request = model.structured_calls[0][0]["text"]
    assert "<previous_version>" in request
    assert "style_prompt: warm, beige" in request
    assert request.count('The Owner asked for this change: "fondo verde".') == 1
    assert len(image_gen.calls) == 2


@pytest.mark.parametrize(
    ("arguments", "error"),
    [
        ({"post_id": "nope", "change": "x", "part": "caption"}, "unknown_post"),
        ({"post_id": "mine", "change": "x", "part": "images"}, "photos_as_they_are"),
        ({"post_id": "done", "change": "x", "part": "caption"}, "post_not_pending"),
        ({"post_id": "mine", "change": "", "part": "caption"}, "invalid_arguments"),
    ],
)
async def test_bad_revisions_start_nothing(
    photos: InMemoryPhotos, arguments: dict[str, str], error: str
) -> None:
    store, image_gen = PostLifecycle(), CountingImageGen()
    store.add(Post("mine", SENDER, [PostImage("/media/x.jpg", b"x")], "caption"))
    store.add(Post("done", SENDER, [PostImage("/media/y.jpg", b"y")], "caption", "published"))
    posts, background = maker(photos_model(), image_gen, photos, store=store)

    assert posts.revise_post(SENDER, arguments, FakeChannel(), drop)["error"] == error


async def test_a_remake_by_create_post_shows_the_old_version(photos: InMemoryPhotos) -> None:
    store, model = PostLifecycle(), photos_model()
    store.add(Post("old", SENDER, [PostImage("/media/x.jpg", b"x")], "Texto viejo", brief="mesa"))
    posts, background = maker(model, CountingImageGen(), photos, store=store)

    posts.create_post(
        SENDER,
        {"brief": "con la otra foto", "asset_ids": ["f2"], "style": "photos", "replaces": "old"},
        FakeChannel(),
        drop,
    )
    await background.join()

    request = model.structured_calls[0][0]["text"]
    assert 'Text: "Texto viejo"' in request
    assert request.endswith("The brief above says what the Owner wants changed.")


async def test_the_owners_notes_reach_the_post_writer(photos: InMemoryPhotos) -> None:
    model = photos_model()

    posts, background = maker(
        model, CountingImageGen(), photos, notes=["Siempre mencionar el envío gratis"]
    )
    arguments = {"brief": "mesa", "asset_ids": ["f1"], "style": "photos"}
    posts.create_post(SENDER, arguments, FakeChannel(), drop)
    await background.join()

    assert "- Siempre mencionar el envío gratis" in model.structured_systems[0]
