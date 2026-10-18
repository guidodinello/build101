from typing import Literal

from pydantic import BaseModel, Field

MAX_SLIDES = 10
MAX_REFERENCES = 10

SlideRole = Literal["cover", "content", "cta"]
# The renderer's template families (ADR 0028); frontend/lib/post-render/spec.ts lists the same
TemplateFamily = Literal["editorial", "numbers", "panorama"]


class SlideCopy(BaseModel):
    role: SlideRole
    headline: str
    body: str | None = None
    kicker: str | None = None


class CarouselCopy(BaseModel):
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    slides: list[SlideCopy] = Field(min_length=1, max_length=MAX_SLIDES)


class SlideScene(BaseModel):
    index: int = Field(ge=1, le=MAX_SLIDES)
    scene_prompt: str


class CarouselBrief(BaseModel):
    reference_asset_ids: list[str] = Field(min_length=1, max_length=MAX_REFERENCES)
    family: TemplateFamily = "editorial"
    style_prompt: str
    slides: list[SlideScene] = Field(min_length=1, max_length=MAX_SLIDES)
    style_notes: str
