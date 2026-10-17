import asyncio
import logging
from dataclasses import dataclass, field

import pytest

from app.carousel.generator import CarouselGenerator, GeneratedSlide
from app.carousel.prompts import ANCHOR_INSTRUCTION, BLOCKED_RETRY_NOTE
from app.carousel.schemas import CarouselBrief, CarouselCopy, SlideCopy, TextCheck
from app.imagegen.base import GeneratedImage, ImageGenBlocked, ImageGenUnavailable
from app.media.images import POST_SIZE, image_size
from tests.conftest import make_image

COLORS = ["red", "green", "blue", "yellow", "purple", "orange", "gray", "pink"]


@dataclass(slots=True)
class Call:
    prompt: str
    style_image: bytes | None


@dataclass(slots=True)
class FakeImageGen:
    failures: list[Exception] = field(default_factory=list)
    fail_calls: dict[int, Exception] = field(default_factory=dict)
    first_color: int = 0
    calls: list[Call] = field(default_factory=list)

    async def generate(
        self, prompt: str, reference_images: list[bytes], style_image: bytes | None = None
    ) -> GeneratedImage:
        self.calls.append(Call(prompt, style_image))
        if self.failures:
            raise self.failures.pop(0)
        if len(self.calls) in self.fail_calls:
            raise self.fail_calls[len(self.calls)]
        await asyncio.sleep(0)
        color = COLORS[(self.first_color + len(self.calls)) % len(COLORS)]
        return GeneratedImage(
            data=make_image((1856, 2304), color=color, format="PNG"),
            mime="image/png",
            provider="fake",
            model="fake-1",
            usage={"output_tokens": 1680},
        )


@dataclass(slots=True)
class FakeTextChecker:
    wrong_headlines: set[str] = field(default_factory=set)

    async def check(self, image: bytes, expected: SlideCopy) -> TextCheck:
        if expected.headline in self.wrong_headlines:
            self.wrong_headlines.discard(expected.headline)
            return TextCheck(matches=False, found="Robel", issues=["misspelled headline"])
        return TextCheck(matches=True, found=expected.headline)


REFERENCES = [make_image((2000, 1500))]


async def test_generate_makes_the_cover_first_then_anchors_every_other_slide_on_it(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    image_gen = FakeImageGen()

    slides = await CarouselGenerator(image_gen).generate(copy, brief, REFERENCES)

    assert [slide.index for slide in slides] == [1, 2, 3, 4]
    assert all(image_size(slide.image) == POST_SIZE for slide in slides)
    assert image_gen.calls[0].style_image is None
    assert ANCHOR_INSTRUCTION not in image_gen.calls[0].prompt
    assert all(call.style_image == slides[0].image for call in image_gen.calls[1:])
    assert all(ANCHOR_INSTRUCTION in call.prompt for call in image_gen.calls[1:])


async def test_generate_regenerates_a_slide_once_when_its_text_is_wrong(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    image_gen = FakeImageGen()
    checker = FakeTextChecker(wrong_headlines={"Roble macizo"})

    slides = await CarouselGenerator(image_gen, checker).generate(copy, brief, REFERENCES)

    assert len(image_gen.calls) == 5
    assert slides[1].attempts == 2
    assert slides[1].usage == {"output_tokens": 3360}
    assert "misspelled headline" in slides[1].prompt
    assert slides[1].text_check == TextCheck(matches=True, found="Roble macizo")


async def test_generate_retries_a_blocked_slide_with_a_simpler_scene(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    image_gen = FakeImageGen(failures=[ImageGenBlocked("IMAGE_SAFETY")])

    slides = await CarouselGenerator(image_gen).generate(copy, brief, REFERENCES)

    assert slides[0].attempts == 2
    assert BLOCKED_RETRY_NOTE in slides[0].prompt


async def test_generate_fails_when_a_slide_is_blocked_twice(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    failures: list[Exception] = [ImageGenBlocked("IMAGE_SAFETY"), ImageGenBlocked("IMAGE_SAFETY")]

    with pytest.raises(ImageGenBlocked):
        await CarouselGenerator(FakeImageGen(failures=failures)).generate(copy, brief, REFERENCES)


async def test_generate_does_not_retry_when_the_provider_is_unavailable(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    image_gen = FakeImageGen(failures=[ImageGenUnavailable("503")])

    with pytest.raises(ImageGenUnavailable):
        await CarouselGenerator(image_gen).generate(copy, brief, REFERENCES)
    assert len(image_gen.calls) == 1


async def test_generate_finishes_the_other_slides_and_logs_their_usage_when_one_fails(
    carousel_spec: tuple[CarouselCopy, CarouselBrief], caplog: pytest.LogCaptureFixture
) -> None:
    copy, brief = carousel_spec
    image_gen = FakeImageGen(fail_calls={3: ImageGenUnavailable("503")})

    with caplog.at_level(logging.INFO), pytest.raises(ImageGenUnavailable):
        await CarouselGenerator(image_gen).generate(copy, brief, REFERENCES)

    assert len(image_gen.calls) == 4
    finished = [r.getMessage() for r in caplog.records if "finished before" in r.getMessage()]
    assert len(finished) == 2
    assert all("{'output_tokens': 1680}" in message for message in finished)


async def test_generate_rejects_a_brief_whose_scenes_do_not_match_the_copy(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    brief = brief.model_copy(update={"slides": brief.slides[:3]})

    with pytest.raises(ValueError, match="don't match"):
        await CarouselGenerator(FakeImageGen()).generate(copy, brief, REFERENCES)


async def generated_carousel(
    copy: CarouselCopy, brief: CarouselBrief
) -> tuple[list[GeneratedSlide], FakeImageGen]:
    slides = await CarouselGenerator(FakeImageGen()).generate(copy, brief, REFERENCES)
    return slides, FakeImageGen(first_color=len(slides))


async def test_redo_regenerates_only_the_asked_slides_anchored_on_the_cover(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    current, image_gen = await generated_carousel(copy, brief)

    redone = await CarouselGenerator(image_gen).redo(copy, brief, REFERENCES, current, [3])

    assert len(image_gen.calls) == 1
    assert image_gen.calls[0].style_image == current[0].image
    assert [slide.image for slide in redone[:2]] == [slide.image for slide in current[:2]]
    assert redone[2].image != current[2].image
    assert redone[3] == current[3]


async def test_redo_of_the_cover_anchors_on_slide_2_and_others_on_the_new_cover(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    current, image_gen = await generated_carousel(copy, brief)

    redone = await CarouselGenerator(image_gen).redo(copy, brief, REFERENCES, current, [4, 1])

    assert image_gen.calls[0].style_image == current[1].image
    assert image_gen.calls[1].style_image == redone[0].image
    assert redone[0].image != current[0].image


@pytest.mark.parametrize("indexes", [[], [0], [5]])
async def test_redo_rejects_slides_outside_the_carousel(
    carousel_spec: tuple[CarouselCopy, CarouselBrief], indexes: list[int]
) -> None:
    copy, brief = carousel_spec
    current, image_gen = await generated_carousel(copy, brief)

    with pytest.raises(ValueError, match="invalid slides to redo"):
        await CarouselGenerator(image_gen).redo(copy, brief, REFERENCES, current, indexes)
