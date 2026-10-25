
import asyncio
from dataclasses import dataclass

from app.agents.schemas import BrandBrain
from app.carousel.generator import GeneratedSlide
from app.carousel.schemas import CarouselBrief, CarouselCopy
from app.media.images import data_uri, logo_for_render

from .base import RendererPort, RenderLogo, SlideRender, render_brand


@dataclass(frozen=True, slots=True)
class PartialSlideRenderError(RuntimeError):
    """Some slides rendered successfully, while others failed."""

    images: list[bytes]
    indices: list[int]
    errors: list[Exception]

    def __str__(self) -> str:
        return f"{len(self.images)} slide(s) rendered; {len(self.errors)} failed."


async def render_slides(
    renderer: RendererPort,
    copy: CarouselCopy,
    brief: CarouselBrief,
    scenes: list[GeneratedSlide],
    brand: BrandBrain | None,
    logo: bytes | None,
) -> list[bytes]:
    """Render slides in order, preserving successful results if one fails."""
    if [scene.index for scene in scenes] != list(range(1, len(copy.slides) + 1)):
        raise ValueError("render_slides needs one scene per slide, in order")

    family = (
        "editorial"
        if brief.family == "panorama" and len(copy.slides) == 1
        else brief.family
    )
    render_logo = await asyncio.to_thread(prepared_logo, logo) if logo else None
    tokens = render_brand(brand)
    requests = [
        SlideRender(
            family=family,
            index=scene.index,
            count=len(copy.slides),
            role=slide.role,
            kicker=slide.kicker,
            headline=slide.headline,
            body=slide.body,
            image=data_uri(scene.image),
            logo=render_logo,
            brand=tokens,
        )
        for slide, scene in zip(copy.slides, scenes, strict=True)
    ]

    results = await asyncio.gather(
        *(renderer.render(request) for request in requests),
        return_exceptions=True,
    )
    images: list[bytes] = []
    indices: list[int] = []
    errors: list[Exception] = []

    for index, result in enumerate(results, start=1):
        if isinstance(result, BaseException):
            if isinstance(result, Exception):
                errors.append(result)
                continue
            raise result
        images.append(result)
        indices.append(index)

    if errors:
        raise PartialSlideRenderError(images, indices, errors)

    return images


def prepared_logo(data: bytes) -> RenderLogo:
    png, tone = logo_for_render(data)
    return RenderLogo(src=data_uri(png), tone=tone)