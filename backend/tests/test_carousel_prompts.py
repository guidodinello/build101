import pytest

from app.carousel.prompts import (
    ANCHOR_INSTRUCTION,
    FIXED_RULES,
    FRAMING,
    PANORAMA_FRAMING,
    build_panorama_prompt,
    build_slide_prompt,
    panorama_ratio,
)
from app.carousel.schemas import CarouselBrief, CarouselCopy


def test_slide_prompt_has_style_scene_framing_and_rules_but_none_of_the_text(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec

    prompt = build_slide_prompt(brief, copy, 3, anchored=True)

    assert brief.style_prompt in prompt
    assert brief.slides[2].scene_prompt in prompt
    assert FRAMING[("editorial", "content")] in prompt
    assert "Photo 3 of 4" in prompt
    assert ANCHOR_INSTRUCTION in prompt
    assert prompt.endswith(FIXED_RULES)
    assert all(slide.headline not in prompt for slide in copy.slides)
    assert "Medimos tu ambiente" not in prompt


def test_cover_prompt_is_not_anchored_and_framed_for_its_family(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    brief = brief.model_copy(update={"family": "numbers"})

    prompt = build_slide_prompt(brief, copy, 1, anchored=False)

    assert FRAMING[("numbers", "cover")] in prompt
    assert ANCHOR_INSTRUCTION not in prompt


def test_slide_prompt_fails_when_the_brief_has_no_scene_for_the_slide(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    brief = brief.model_copy(update={"slides": brief.slides[:2]})

    with pytest.raises(ValueError, match="no scene for slide 3"):
        build_slide_prompt(brief, copy, 3, anchored=True)


def test_panorama_prompt_lists_the_panels_left_to_right_without_the_text(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec

    prompt = build_panorama_prompt(brief, copy)

    assert PANORAMA_FRAMING.format(count=4) in prompt
    panels = [prompt.index(f"- Panel {s.index}: {s.scene_prompt}") for s in brief.slides]
    assert panels == sorted(panels)
    assert prompt.endswith(FIXED_RULES)
    assert all(slide.headline not in prompt for slide in copy.slides)


@pytest.mark.parametrize(
    ("count", "ratio"), [(2, "16:9"), (3, "21:9"), (4, "4:1"), (5, "4:1"), (6, "8:1"), (10, "8:1")]
)
def test_panorama_ratio_is_the_closest_wide_ratio_to_the_slides(count: int, ratio: str) -> None:
    assert panorama_ratio(count) == ratio
