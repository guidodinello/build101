import json

import pytest

from app.carousel.schemas import CarouselBrief, CarouselCopy
from app.media.images import REVIEW_SIZE, UnreadableImage, image_size, review_copy
from app.posts.critic import (
    MAX_NEW_SCENES,
    DesignCritic,
    DesignReview,
    SlideReview,
    changed,
    revise,
)
from app.rendering.base import FitReport, RenderedSlide, RenderReport
from tests.conftest import make_image
from tests.fakes import SequenceModel

SLIDE = make_image((1080, 1350))


def review(index: int, **changes: object) -> SlideReview:
    fields = {
        "index": index,
        "verdict": "fix",
        "problems": ["text over the product"],
        "layout": "keep",
        "focus": "keep",
        "emphasis": "keep",
        "surface": "keep",
        "new_scene": False,
        "scene_note": "",
    }
    return SlideReview.model_validate(fields | changes)


def test_fixes_change_the_knobs_the_family_has_and_ignore_the_rest(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    _, brief = carousel_spec
    fixes = DesignReview(
        slides=[
            review(1, layout="frame", focus="top", emphasis="huge"),
            review(2, layout="checklist", surface="dark"),
            review(3, verdict="ok", layout="quote"),
        ]
    )

    revision = revise(brief, fixes)

    first, second, third = revision.brief.slides[:3]
    assert (first.layout, first.focus, first.emphasis) == ("frame", "top", "standard")
    assert (second.layout, second.surface) == ("auto", "dark")
    assert third == brief.slides[2]
    assert revision.new_scenes == []
    assert changed(brief, revision)


def test_new_scenes_are_capped_and_carry_the_critics_note(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    _, brief = carousel_spec
    fixes = DesignReview(
        slides=[review(n, new_scene=True, scene_note="no text on the wall") for n in (1, 2, 3)]
    )

    revision = revise(brief, fixes)

    assert revision.new_scenes == [1, 2][:MAX_NEW_SCENES]
    assert revision.brief.slides[0].scene_prompt.endswith("Fix: no text on the wall")
    assert revision.brief.slides[2].scene_prompt == brief.slides[2].scene_prompt


def test_a_panorama_is_never_regenerated_slide_by_slide(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    _, brief = carousel_spec
    panorama = brief.model_copy(update={"family": "panorama"})

    revision = revise(panorama, DesignReview(slides=[review(2, new_scene=True)]))

    assert revision.new_scenes == []
    assert not changed(panorama, revision)


async def test_the_critic_sees_each_slide_at_half_size_with_what_the_renderer_measured(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    report = RenderReport(
        family="editorial",
        role="cover",
        layout="overlay",
        fits=[FitReport(slot="headline", size=76, lines=3, clamped=True)],
    )
    slides = [RenderedSlide(image=SLIDE, report=report if n == 1 else None) for n in range(1, 5)]
    model = SequenceModel([DesignReview(slides=[])])

    await DesignCritic(model).review(copy, brief, slides)

    [content] = model.contents
    sheet = json.loads(content[0]["text"])
    assert [entry["index"] for entry in sheet] == [1, 2, 3, 4]
    assert sheet[0]["drawn_layout"] == "overlay"
    assert sheet[0]["fits"][0]["clamped"] is True
    assert sheet[0]["words"]["headline"] == copy.slides[0].headline
    assert "frame" in sheet[0]["layouts_in_family"]
    images = [block for block in content[1:] if block["type"] == "image"]
    assert len(images) == 4


def test_a_review_copy_is_half_the_slide() -> None:
    assert image_size(review_copy(SLIDE)) == REVIEW_SIZE


def test_a_slide_that_is_not_an_image_is_unreadable() -> None:
    with pytest.raises(UnreadableImage):
        review_copy(b"not a jpeg")


def test_a_second_fix_for_the_same_slide_is_ignored(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    _, brief = carousel_spec
    twice = [review(2, new_scene=True, scene_note="no text"), review(2, new_scene=True)]
    fixes = DesignReview(slides=[*twice, review(3, new_scene=True)])

    revision = revise(brief, fixes)

    assert revision.new_scenes == [2, 3]
    assert revision.brief.slides[1].scene_prompt.count("Fix:") == 1
