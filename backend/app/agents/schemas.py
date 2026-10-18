"""Output models of the specialist agents (docs/architecture/agents.md).

Kept to objects, strings, ints, enums and lists: Gemini rejects large or deeply constrained
schemas, so limits (lengths, counts, hex colors) are checked in code after the call.
"""

from typing import Literal

from pydantic import BaseModel

Goal = Literal["sales", "awareness", "launch", "loyalty"]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class AssetAnalysis(BaseModel):
    description: str
    subjects: list[str]
    product_ids: list[str]
    quality: Literal["high", "ok", "low"]
    orientation: Literal["portrait", "landscape", "square"]
    has_people: bool
    has_text: bool
    dominant_colors: list[str]
    best_for: list[Literal["hero", "background", "detail", "behind_the_scenes"]]
    safe_crop_focus: Literal["center", "top", "bottom", "left", "right"]


class Voice(BaseModel):
    descriptors: list[str]
    formality: int
    humor: int
    emoji_policy: Literal["many", "few", "none"]
    do: list[str]
    dont: list[str]
    sample_phrases: list[str]


class Audience(BaseModel):
    name: str
    description: str
    pains: list[str]
    motivations: list[str]


class ContentPillar(BaseModel):
    id: str
    name: str
    description: str
    example_ideas: list[str]


class FeaturedProduct(BaseModel):
    product_id: str
    name: str
    why: str


class VisualIdentity(BaseModel):
    primary_color: str
    secondary_color: str
    accent_color: str
    background_color: str
    text_color: str
    logo_asset_id: str | None
    photo_style: str


class PostingPrefs(BaseModel):
    posts_per_week: int
    preferred_days: list[Weekday]
    preferred_time: str


class BrandBrain(BaseModel):
    business_name: str
    one_liner: str
    description: str
    category: str
    location: str
    goal: Goal
    audiences: list[Audience]
    value_props: list[str]
    voice: Voice
    pillars: list[ContentPillar]
    featured_products: list[FeaturedProduct]
    ctas: list[str]
    hashtags: list[str]
    posting: PostingPrefs
    constraints: list[str]
    visual_identity: VisualIdentity
    whatsapp_summary: str
