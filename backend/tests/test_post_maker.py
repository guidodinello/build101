from datetime import datetime, timedelta

import pytest

from app.conversation.history import InMemoryHistory
from app.conversation.photos import LOCAL_TZ, InMemoryPhotos
from app.copy import messages_es
from app.media.images import POST_SIZE, image_size
from app.media.public import PublicImages
from app.posts.drafts import CarouselDraft, PostCopy, PostDrafter, SlideDraft
from app.posts.maker import WHATSAPP_CAPTION_MAX, PostMaker
from tests.conftest import make_image
from tests.fakes import CountingImageGen, FakeChannel, ScriptedModel

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
    history: InMemoryHistory | None = None,
    max_posts_per_day: int = 5,
) -> PostMaker:
    return PostMaker(
        PostDrafter(model),
        image_gen,
        photos,
        history or InMemoryHistory(),
        images or PublicImages(),
        "https://backend.test/",
        max_posts_per_day=max_posts_per_day,
        now=lambda: NOON,
    )


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


async def test_a_sent_design_leaves_a_note_with_its_headlines_and_text(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(2)})
    history = InMemoryHistory()
    posts = maker(model, CountingImageGen(), photos, history=history)

    result = posts.create_post(
        SENDER, {"brief": "m", "asset_ids": ["f1", "f2"], "style": "design"}, FakeChannel()
    )
    await posts.join()

    [note] = history.get(SENDER)
    text = note["content"][0]["text"]
    assert text.startswith(f"[post {result['post_id']} sent to the Owner] 2 image(s), design")
    assert "from photos f1 f2" in text
    assert 'Slide headlines: 1 "Slide 1"; 2 "Slide 2"' in text
    assert f'Text: "{POST_TEXT}"' in text


async def test_a_text_too_long_for_a_caption_follows_the_images(photos: InMemoryPhotos) -> None:
    long_caption = "a" * WHATSAPP_CAPTION_MAX
    model = ScriptedModel(drafts={PostCopy: PostCopy(caption=long_caption, hashtags=[])})
    channel = FakeChannel()
    posts = maker(model, CountingImageGen(), photos)

    posts.create_post(SENDER, {"brief": "m", "asset_ids": ["f1", "f2"], "style": "photos"}, channel)
    await posts.join()

    assert captions(channel) == ["1/2", "2/2"]
    assert channel.sent == [(SENDER, long_caption)]


async def test_a_failed_generation_tells_the_owner_and_frees_the_guard(
    photos: InMemoryPhotos,
) -> None:
    model = ScriptedModel(drafts={CarouselDraft: carousel_draft(1)})
    channel, image_gen, history = FakeChannel(), CountingImageGen(fail=True), InMemoryHistory()
    posts = maker(model, image_gen, photos, history=history)
    request = {"brief": "mesa", "asset_ids": ["f1"], "style": "design"}

    posts.create_post(SENDER, request, channel)
    await posts.join()

    assert channel.sent == [(SENDER, messages_es.JOB_FAILED)]
    [note] = history.get(SENDER)
    assert note["content"][0]["text"].endswith("asked whether to try again.")
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
