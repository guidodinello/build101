import pytest

from app.carousel.prompts import (
    ANCHOR_INSTRUCTION,
    FIXED_RULES,
    build_slide_prompt,
    text_retry_note,
)
from app.carousel.schemas import CarouselBrief, CarouselCopy, TextCheck


def test_slide_prompt_has_exact_text_style_scene_and_rules(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec

    prompt = build_slide_prompt(brief, copy, 3, anchored=True)

    assert 'Headline: "Pensada para tu espacio"' in prompt
    assert 'Body: "Medimos tu ambiente y diseñamos la mesa justa."' in prompt
    assert brief.style_prompt in prompt
    assert brief.slides[2].scene_prompt in prompt
    assert "Slide 3 of 4" in prompt
    assert ANCHOR_INSTRUCTION in prompt
    assert prompt.endswith(FIXED_RULES)


def test_cover_prompt_is_not_anchored_and_omits_missing_body(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec

    prompt = build_slide_prompt(brief, copy, 1, anchored=False)

    assert 'Headline: "Tu comedor, a medida"' in prompt
    assert "Body:" not in prompt
    assert ANCHOR_INSTRUCTION not in prompt


def test_slide_prompt_fails_when_the_brief_has_no_scene_for_the_slide(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    brief = brief.model_copy(update={"slides": brief.slides[:2]})

    with pytest.raises(ValueError, match="no scene for slide 3"):
        build_slide_prompt(brief, copy, 3, anchored=True)


def test_text_retry_note_names_the_issues() -> None:
    check = TextCheck(matches=False, found="Robel macizo", issues=["'Roble' spelled 'Robel'"])

    assert "'Roble' spelled 'Robel'" in text_retry_note(check)


def test_text_retry_note_falls_back_to_the_text_found() -> None:
    assert '"Robel macizo"' in text_retry_note(TextCheck(matches=False, found="Robel macizo"))
