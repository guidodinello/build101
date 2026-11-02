from typing import Literal

from pydantic import BaseModel, Field

MAX_SLIDES = 10
MAX_REFERENCES = 10
MAX_ITEMS = 5

SlideRole = Literal["cover", "content", "cta"]
# The renderer's template families and their layouts (ADR 0029, ADR 0035);
# frontend/lib/post-render/spec.ts lists the same
TemplateFamily = Literal["editorial", "numbers", "panorama", "minimal", "notes", "scrapbook"]
Layout = Literal[
    "auto",
    "overlay",
    "frame",
    "photo-top",
    "full-bleed",
    "quote",
    "poster",
    "band",
    "split",
    "window",
    "type",
    "side",
    "card",
    "checklist",
    "polaroid",
    "taped",
]
LAYOUTS: dict[TemplateFamily, tuple[Layout, ...]] = {
    "editorial": ("overlay", "frame", "photo-top", "full-bleed", "quote"),
    "numbers": ("poster", "band", "split"),
    "panorama": (),
    "minimal": ("window", "type", "side"),
    "notes": ("card", "checklist"),
    "scrapbook": ("polaroid", "taped"),
}
Emphasis = Literal["standard", "statement"]
Focus = Literal["center", "top", "bottom", "left", "right"]
Surface = Literal["auto", "paper", "brand", "dark"]


def family_layout(family: TemplateFamily, layout: Layout) -> Layout:
    """The layout if the family has it, else "auto" (the family picks per role)."""
    return layout if layout in LAYOUTS[family] else "auto"


class SlideCopy(BaseModel):
    role: SlideRole
    headline: str
    body: str | None = None
    kicker: str | None = None
    items: list[str] = Field(default_factory=list, max_length=MAX_ITEMS)


class CarouselCopy(BaseModel):
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    slides: list[SlideCopy] = Field(min_length=1, max_length=MAX_SLIDES)


class SlideScene(BaseModel):
    """One slide's photo brief and the design knobs its template takes."""

    index: int = Field(ge=1, le=MAX_SLIDES)
    scene_prompt: str
    layout: Layout = "auto"
    emphasis: Emphasis = "standard"
    focus: Focus = "center"
    surface: Surface = "auto"


class CarouselBrief(BaseModel):
    reference_asset_ids: list[str] = Field(min_length=1, max_length=MAX_REFERENCES)
    family: TemplateFamily = "editorial"
    style_prompt: str
    slides: list[SlideScene] = Field(min_length=1, max_length=MAX_SLIDES)
    style_notes: str
