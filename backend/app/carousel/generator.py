import asyncio
import logging
from collections.abc import Coroutine, Iterable
from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from app.imagegen.base import GeneratedImage, ImageGenBlocked, ImageGenNoImage, ImageGenPort
from app.media.images import prepare_reference, to_post_image

from .prompts import BLOCKED_RETRY_NOTE, build_slide_prompt, text_retry_note
from .schemas import CarouselBrief, CarouselCopy, SlideCopy, TextCheck

logger = logging.getLogger(__name__)

COVER = 1


@runtime_checkable
class TextCheckerPort(Protocol):
    async def check(self, image: bytes, expected: SlideCopy) -> TextCheck: ...


class GeneratedSlide(BaseModel):
    index: int
    image: bytes
    prompt: str
    provider: str
    model: str | None
    usage: dict[str, int]
    attempts: int
    text_check: TextCheck | None = None


class CarouselGenerator:
    def __init__(
        self, image_gen: ImageGenPort, text_checker: TextCheckerPort | None = None
    ) -> None:
        self._image_gen = image_gen
        self._text_checker = text_checker

    async def generate(
        self,
        copy: CarouselCopy,
        brief: CarouselBrief,
        references: list[bytes],
        slide_references: dict[int, list[bytes]] | None = None,
    ) -> list[GeneratedSlide]:
        """`slide_references` overrides `references` for the slides it lists (1-based)."""
        check_slides_match(copy, brief)
        prepared = await prepare_references(references)
        per_slide = {
            index: await prepare_references(slide_refs)
            for index, slide_refs in (slide_references or {}).items()
        }
        cover = await self._slide(
            copy, brief, COVER, per_slide.get(COVER, prepared), style_image=None
        )
        rest = await gather_slides(
            self._slide(copy, brief, index, per_slide.get(index, prepared), style_image=cover.image)
            for index in range(COVER + 1, len(copy.slides) + 1)
        )
        return [cover, *rest]

    async def redo(
        self,
        copy: CarouselCopy,
        brief: CarouselBrief,
        references: list[bytes],
        current: list[GeneratedSlide],
        indexes: list[int],
    ) -> list[GeneratedSlide]:
        check_slides_match(copy, brief)
        check_redo_request(len(copy.slides), current, indexes)
        prepared = await prepare_references(references)
        slides = {slide.index: slide for slide in current}

        if COVER in indexes:
            anchor = slides[COVER + 1].image if COVER + 1 in slides else None
            slides[COVER] = await self._slide(copy, brief, COVER, prepared, style_image=anchor)

        redone = await gather_slides(
            self._slide(copy, brief, index, prepared, style_image=slides[COVER].image)
            for index in sorted(set(indexes) - {COVER})
        )
        slides.update((slide.index, slide) for slide in redone)
        return [slides[index] for index in sorted(slides)]

    async def _slide(
        self,
        copy: CarouselCopy,
        brief: CarouselBrief,
        index: int,
        references: list[bytes],
        style_image: bytes | None,
    ) -> GeneratedSlide:
        expected = copy.slides[index - 1]
        prompt = build_slide_prompt(brief, copy, index, anchored=style_image is not None)
        generated, image, prompt, attempts = await self._render(prompt, references, style_image)
        usage = generated.usage
        check = await self._check(image, expected)

        if check is not None and not check.matches:
            logger.info("slide %d text mismatch, regenerating: %s", index, check.issues)
            retry_prompt = f"{prompt}\n\n{text_retry_note(check)}"
            generated, image, prompt, retries = await self._render(
                retry_prompt, references, style_image
            )
            usage = add_usage(usage, generated.usage)
            attempts += retries
            check = await self._check(image, expected)
            if check is not None and not check.matches:
                logger.warning("slide %d text still wrong after retry: %s", index, check.issues)

        return GeneratedSlide(
            index=index,
            image=image,
            prompt=prompt,
            provider=generated.provider,
            model=generated.model,
            usage=usage,
            attempts=attempts,
            text_check=check,
        )

    async def _render(
        self, prompt: str, references: list[bytes], style_image: bytes | None
    ) -> tuple[GeneratedImage, bytes, str, int]:
        attempts = 1
        try:
            generated = await self._image_gen.generate(prompt, references, style_image)
        except (ImageGenBlocked, ImageGenNoImage) as exc:
            logger.warning("image generation failed (%s), retrying with a simpler scene", exc)
            prompt = f"{prompt}\n\n{BLOCKED_RETRY_NOTE}"
            generated = await self._image_gen.generate(prompt, references, style_image)
            attempts += 1
        image = await asyncio.to_thread(to_post_image, generated.data)
        return generated, image, prompt, attempts

    async def _check(self, image: bytes, expected: SlideCopy) -> TextCheck | None:
        if self._text_checker is None:
            return None
        return await self._text_checker.check(image, expected)


def check_slides_match(copy: CarouselCopy, brief: CarouselBrief) -> None:
    expected = list(range(1, len(copy.slides) + 1))
    found = sorted(scene.index for scene in brief.slides)
    if found != expected:
        raise ValueError(f"carousel brief scenes {found} don't match the copy's slides {expected}")


def check_redo_request(slide_count: int, current: list[GeneratedSlide], indexes: list[int]) -> None:
    if sorted(slide.index for slide in current) != list(range(1, slide_count + 1)):
        raise ValueError(f"current slides don't cover slides 1..{slide_count}")
    if not indexes or any(not 1 <= index <= slide_count for index in indexes):
        raise ValueError(f"invalid slides to redo: {indexes} (carousel has {slide_count})")


async def prepare_references(references: list[bytes]) -> list[bytes]:
    return list(
        await asyncio.gather(*(asyncio.to_thread(prepare_reference, data) for data in references))
    )


async def gather_slides(
    coroutines: Iterable[Coroutine[Any, Any, GeneratedSlide]],
) -> list[GeneratedSlide]:
    results = await asyncio.gather(*coroutines, return_exceptions=True)
    slides = [result for result in results if isinstance(result, GeneratedSlide)]
    failures = [result for result in results if isinstance(result, BaseException)]
    if not failures:
        return slides
    for slide in slides:
        logger.info(
            "slide %d finished before the carousel failed: %d attempts, usage %s",
            slide.index,
            slide.attempts,
            slide.usage,
        )
    for failure in failures[1:]:
        logger.warning("another slide failed too: %r", failure)
    raise failures[0]


def add_usage(first: dict[str, int], second: dict[str, int]) -> dict[str, int]:
    return {key: first.get(key, 0) + second.get(key, 0) for key in first.keys() | second.keys()}
