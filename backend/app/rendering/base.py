import re
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

from app.agents.schemas import BrandBrain, FontPair
from app.carousel.schemas import Emphasis, Focus, Layout, SlideRole, Surface, TemplateFamily
from app.media.images import Tone

HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
# The renderer rejects a longer brand name (frontend/lib/post-render/spec.ts)
MAX_BRAND_NAME = 80


class BrandColors(BaseModel):
    primary: str = "#3B2A20"
    secondary: str = "#8C7B6B"
    accent: str = "#C8833B"
    background: str = "#F5F0E8"
    text: str = "#1C1814"


class RenderBrand(BaseModel):
    name: str | None = None
    colors: BrandColors = BrandColors()
    fonts: FontPair = "serif-classic"


class RenderLogo(BaseModel):
    src: str  # data URI
    tone: Tone


class SlideRender(BaseModel):
    """One slide for POST /api/render (frontend/lib/post-render/spec.ts, ADR 0029)."""

    family: TemplateFamily
    index: int
    count: int
    role: SlideRole
    layout: Layout = "auto"
    emphasis: Emphasis = "standard"
    focus: Focus = "center"
    surface: Surface = "auto"
    kicker: str | None
    headline: str
    body: str | None
    items: list[str] = Field(default_factory=list)
    image: str  # data URI of the scene
    logo: RenderLogo | None
    brand: RenderBrand


class FitReport(BaseModel):
    slot: str
    size: int
    lines: int
    clamped: bool  # the text needed more room than the layout gives, set at the smallest size


class InkReport(BaseModel):
    slot: str
    ink: str
    contrast: float
    scrim: float
    busy: bool


class RenderReport(BaseModel):
    """What the renderer measured on a slide (x-render-report): the Design Critic reads it."""

    family: str
    role: str
    layout: str
    fits: list[FitReport] = Field(default_factory=list)
    ink: list[InkReport] = Field(default_factory=list)


class RenderedSlide(BaseModel):
    image: bytes
    report: RenderReport | None = None


@runtime_checkable
class RendererPort(Protocol):
    async def render(self, slide: SlideRender) -> RenderedSlide:
        """The designed slide as a 1080×1350 JPEG, with what the renderer measured."""
        ...


class RendererError(Exception):
    pass


def render_brand(brand: BrandBrain | None) -> RenderBrand:
    """The Brand Brain's name and colors; a color that isn't #RRGGBB keeps the default."""
    if brand is None:
        return RenderBrand()
    identity = brand.visual_identity
    given = {
        "primary": identity.primary_color,
        "secondary": identity.secondary_color,
        "accent": identity.accent_color,
        "background": identity.background_color,
        "text": identity.text_color,
    }
    colors = BrandColors(
        **{key: value for key, value in given.items() if HEX_COLOR.fullmatch(value)}
    )
    name = brand.business_name.strip()[:MAX_BRAND_NAME].rstrip()
    return RenderBrand(name=name or None, colors=colors, fonts=identity.font_pair)
