import asyncio
import logging
from collections.abc import Coroutine, Iterable
from typing import Any

from pydantic import BaseModel

from app.imagegen.base import GeneratedImage, ImageGenBlocked, ImageGenNoImage, ImageGenPort
from app.media.images import decode, prepare_reference, slice_panorama, to_post_image

from .prompts import BLOCKED_RETRY_NOTE, build_panorama_prompt, build_slide_prompt, panorama_ratio
from .schemas import CarouselBrief, CarouselCopy

logger = logging.getLogger(__name__)

COVER = 1
# A panorama spans several slides, so it is generated at 4K to keep each slice sharp (ADR 0029)
PANORAMA_IMAGE_SIZE = "4K"


class GeneratedSlide(BaseModel):
    """One slide's text-free scene; the renderer sets the design over it (ADR 0029)."""

    index: int
    image: bytes
    prompt: str
    provider: str
    model: str | None
    usage: dict[str, int]
    attempts: int


class CarouselGenerator:
    def __init__(self, image_gen: ImageGenPort) -> None:
        self._image_gen = image_gen

    async def generate(
        self,
        copy: CarouselCopy,
        brief: CarouselBrief,
        references: list[bytes],
        slide_references: dict[int, list[bytes]] | None = None,
    ) -> list[GeneratedSlide]:
        """`slide_references` overrides `references` for the slides it lists (1-based).

        A panorama is one wide scene from all the references, so it ignores `slide_references`.
        """
        check_slides_match(copy, brief)
        prepared = await prepare_references(references)
        if is_panorama(copy, brief):
            return await self._panorama(copy, brief, prepared)
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
        """A panorama is regenerated whole: one slice alone would break the seams."""
        check_slides_match(copy, brief)
        check_redo_request(len(copy.slides), current, indexes)
        if is_panorama(copy, brief):
            return await self.generate(copy, brief, references)
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
        prompt = build_slide_prompt(brief, copy, index, anchored=style_image is not None)
        generated, prompt, attempts = await self._generate(prompt, references, style_image)
        return GeneratedSlide(
            index=index,
            image=await asyncio.to_thread(to_post_image, generated.data),
            prompt=prompt,
            provider=generated.provider,
            model=generated.model,
            usage=generated.usage,
            attempts=attempts,
        )

    async def _panorama(
        self, copy: CarouselCopy, brief: CarouselBrief, references: list[bytes]
    ) -> list[GeneratedSlide]:
        count = len(copy.slides)
        generated, prompt, attempts = await self._generate(
            build_panorama_prompt(brief, copy),
            references,
            None,
            aspect_ratio=panorama_ratio(count),
            image_size=PANORAMA_IMAGE_SIZE,
        )
        images = await asyncio.to_thread(slice_panorama, generated.data, count)
        return [
            GeneratedSlide(
                index=index,
                image=image,
                prompt=prompt,
                provider=generated.provider,
                model=generated.model,
                usage=generated.usage if index == COVER else {},
                attempts=attempts,
            )
            for index, image in enumerate(images, start=1)
        ]

    async def _generate(
        self,
        prompt: str,
        references: list[bytes],
        style_image: bytes | None,
        **size: str,
    ) -> tuple[GeneratedImage, str, int]:
        try:
            generated = await self._image_gen.generate(prompt, references, style_image, **size)
            return generated, prompt, 1
        except (ImageGenBlocked, ImageGenNoImage) as exc:
            logger.warning("image generation failed (%s), retrying with a simpler scene", exc)
            prompt = f"{prompt}\n\n{BLOCKED_RETRY_NOTE}"
            generated = await self._image_gen.generate(prompt, references, style_image, **size)
            return generated, prompt, 2


def is_panorama(copy: CarouselCopy, brief: CarouselBrief) -> bool:
    return brief.family == "panorama" and len(copy.slides) > 1


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
    return list(await asyncio.gather(*(decode(prepare_reference, data) for data in references)))


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
