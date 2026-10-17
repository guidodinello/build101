from typing import Literal

from pydantic import BaseModel, Field

MAX_SLIDES = 10
MAX_REFERENCES = 10

SlideRole = Literal["cover", "content", "cta"]


class SlideCopy(BaseModel):
    role: SlideRole
    headline: str
    body: str | None = None


class CarouselCopy(BaseModel):
    caption: str
    hashtags: list[str] = Field(default_factory=list)
    slides: list[SlideCopy] = Field(min_length=1, max_length=MAX_SLIDES)


class SlideScene(BaseModel):
    index: int = Field(ge=1, le=MAX_SLIDES)
    scene_prompt: str


class CarouselBrief(BaseModel):
    reference_asset_ids: list[str] = Field(min_length=1, max_length=MAX_REFERENCES)
    style_prompt: str
    slides: list[SlideScene] = Field(min_length=1, max_length=MAX_SLIDES)
    style_notes: str


class TextCheck(BaseModel):
    matches: bool
    found: str
    issues: list[str] = Field(default_factory=list)
