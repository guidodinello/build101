import asyncio

from app.agents.schemas import BrandBrain
from app.carousel.generator import GeneratedSlide
from app.carousel.schemas import CarouselBrief, CarouselCopy
from app.media.images import data_uri, logo_for_render

from .base import RendererPort, RenderLogo, SlideRender, render_brand


async def render_slides(
    renderer: RendererPort,
    copy: CarouselCopy,
    brief: CarouselBrief,
    scenes: list[GeneratedSlide],
    brand: BrandBrain | None,
    logo: bytes | None,
) -> list[bytes]:
    """Each slide's design over its scene, in order; the logo only when the Owner asked."""
    if [scene.index for scene in scenes] != list(range(1, len(copy.slides) + 1)):
        raise ValueError("render_slides needs one scene per slide, in order")
    family = "editorial" if brief.family == "panorama" and len(copy.slides) == 1 else brief.family
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
    return list(await asyncio.gather(*(renderer.render(request) for request in requests)))


def prepared_logo(data: bytes) -> RenderLogo:
    png, tone = logo_for_render(data)
    return RenderLogo(src=data_uri(png), tone=tone)
