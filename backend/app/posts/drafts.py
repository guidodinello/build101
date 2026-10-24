import logging
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from app.agents.schemas import BrandBrain
from app.carousel.schemas import (
    MAX_SLIDES,
    CarouselBrief,
    CarouselCopy,
    SlideCopy,
    SlideRole,
    SlideScene,
    TemplateFamily,
)
from app.knowledge.base import CatalogItem
from app.llm.client import ChatModel, Content, image_content, text_content
from app.prompts import tagged

logger = logging.getLogger(__name__)

AGENT = "post_drafter"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "draft.md").read_text()
BRAND_FIELDS_NOT_FOR_POSTS = {"whatsapp_summary", "posting"}
# The renderer rejects longer slots (frontend/lib/post-render/spec.ts); the prompt asks for less
SLOT_LIMITS = {"kicker": 40, "headline": 120, "body": 320}


class PostCopy(BaseModel):
    caption: str
    hashtags: list[str]


class SlideDraft(BaseModel):
    role: SlideRole
    kicker: str
    headline: str
    body: str
    scene_prompt: str


class CarouselDraft(BaseModel):
    caption: str
    hashtags: list[str]
    family: TemplateFamily
    style_prompt: str
    style_notes: str
    slides: list[SlideDraft]


@dataclass(frozen=True, slots=True)
class PreviousPost:
    """The version the Owner saw, for a remake that changes only what they asked."""

    brief: str
    text: str  # caption + hashtags
    headlines: list[str]
    style_prompt: str | None
    change: str | None  # the Owner's change, when it isn't already in the new brief


class PostDrafter:
    """Brief + photos + Brand Brain → the post's copy, and for a design the generator's input.

    One structured call, a stand-in for the Copywriter and the Art Director (T13, T14).
    `trend_notes` come from the latest Niche Report of the Business's niche (ADR 0025).
    """

    def __init__(self, model: ChatModel) -> None:
        self._model = model

    async def copy(
        self,
        brief: str,
        photos: list[bytes],
        brand: BrandBrain | None = None,
        notes: list[str] | None = None,
        previous: PreviousPost | None = None,
        trend_notes: str | None = None,
        products: list[CatalogItem] | None = None,
    ) -> PostCopy:
        request = (
            f"Write the caption for a post of {len(photos)} photo(s), posted as they are, "
            f"without a design.\n\nBrief: {brief}{revision_section(previous)}"
            f"{products_section(products)}{trend_section(trend_notes)}"
        )
        return await self._model.structured(
            AGENT,
            system_prompt(brand, notes),
            request_content(request, photos),
            PostCopy,
            "medium",
        )

    async def recaption(
        self,
        photos: list[bytes],
        previous: PreviousPost,
        brand: BrandBrain | None = None,
        notes: list[str] | None = None,
        products: list[CatalogItem] | None = None,
    ) -> PostCopy:
        """New caption and hashtags for a post whose images stay exactly as they are."""
        request = (
            "Rewrite only the caption and the hashtags of this post: its images stay exactly as "
            f"they are.\n\nBrief: {previous.brief}{revision_section(previous)}"
            f"{products_section(products)}"
        )
        return await self._model.structured(
            AGENT,
            system_prompt(brand, notes),
            request_content(request, photos),
            PostCopy,
            "medium",
        )

    async def design(
        self,
        brief: str,
        photos: list[bytes],
        photo_ids: list[str],
        slide_count: int,
        brand: BrandBrain | None = None,
        notes: list[str] | None = None,
        previous: PreviousPost | None = None,
        trend_notes: str | None = None,
        products: list[CatalogItem] | None = None,
    ) -> tuple[CarouselCopy, CarouselBrief]:
        one_per_photo = (
            " Each slide is built from its own photo, in order."
            if len(photos) == slide_count
            else ""
        )
        request = (
            f"A design of exactly {slide_count} slide(s) (4:5).{one_per_photo}\n\n"
            f"Brief: {brief}{revision_section(previous)}{products_section(products)}"
            f"{trend_section(trend_notes)}"
        )
        draft = await self._model.structured(
            AGENT,
            system_prompt(brand, notes),
            request_content(request, photos),
            CarouselDraft,
            "medium",
        )
        slides = fit_slides(draft.slides, slide_count)
        family = draft.family
        if family == "panorama" and (one_per_photo or len(slides) == 1):
            logger.info("panorama doesn't fit this design, using editorial")
            family = "editorial"
        copy = CarouselCopy(
            caption=draft.caption,
            hashtags=draft.hashtags,
            slides=[
                SlideCopy(
                    role=slide.role,
                    kicker=slide.kicker or None,
                    headline=slide.headline,
                    body=slide.body or None,
                )
                for slide in slides
            ],
        )
        carousel_brief = CarouselBrief(
            reference_asset_ids=photo_ids,
            family=family,
            style_prompt=draft.style_prompt,
            slides=[
                SlideScene(index=n, scene_prompt=slide.scene_prompt)
                for n, slide in enumerate(slides, start=1)
            ],
            style_notes=draft.style_notes,
        )
        return copy, carousel_brief


def system_prompt(brand: BrandBrain | None, notes: list[str] | None = None) -> str:
    """The instructions, then the Business's Brand Brain (agents.md § Brand Brain) and the
    Owner's notes (ADR 0030).

    They go in the system prompt, not the request, so the prefix stays the same for every post
    of a Business and caches.
    """
    prompt = SYSTEM_PROMPT
    if brand is not None:
        data = brand.model_dump_json(exclude=BRAND_FIELDS_NOT_FOR_POSTS)
        prompt += f"\n<brand_brain>\n{data}\n</brand_brain>\n"
    if notes:
        listed = "\n".join(f"- {note}" for note in notes)
        prompt += f"\n<owner_notes>\n{listed}\n</owner_notes>\n"
    return prompt


def products_section(products: list[CatalogItem] | None) -> str:
    """The Catalog Products in the post's photos, escaped: the Owner typed them in the wizard."""
    if not products:
        return ""
    items = [
        {"name": item.name, "description": item.description, "price": item.price}
        for item in products
    ]
    return f"\n\n{tagged('products', items)}"


def trend_section(trend_notes: str | None) -> str:
    """The niche's trend notes, one per line, escaped: they come from web pages (ADR 0025)."""
    if not trend_notes:
        return ""
    return f"\n\n{tagged('trend_notes', trend_notes.splitlines())}"


def revision_section(previous: PreviousPost | None) -> str:
    if previous is None:
        return ""
    lines = [f"Brief: {previous.brief}", f'Text: "{previous.text}"']
    if previous.headlines:
        lines.append(
            "Slide headlines: "
            + "; ".join(f'{n} "{h}"' for n, h in enumerate(previous.headlines, start=1))
        )
    if previous.style_prompt:
        lines.append(f"style_prompt: {previous.style_prompt}")
    change = (
        f'The Owner asked for this change: "{previous.change}".'
        if previous.change
        else "The brief above says what the Owner wants changed."
    )
    body = "\n".join(lines)
    return f"\n\n<previous_version>\n{body}\n</previous_version>\n{change}"


def request_content(request: str, photos: list[bytes]) -> list[Content]:
    return [text_content(request), *(image_content(photo, "image/jpeg") for photo in photos)]


def fit_slides(slides: list[SlideDraft], count: int) -> list[SlideDraft]:
    """Keep the requested number of slides (fewer if the model wrote fewer), cover first."""
    if not slides:
        raise ValueError("the design draft has no slides")
    if len(slides) != count:
        logger.warning("design draft has %d slides, %d requested", len(slides), count)
    fitted = [clip_slots(slide) for slide in slides[: min(count, MAX_SLIDES)]]
    fitted[0] = fitted[0].model_copy(update={"role": "cover"})
    return fitted


def clip_slots(slide: SlideDraft) -> SlideDraft:
    """Cut a slot the renderer would reject, rather than lose the whole post."""
    clipped = {
        field: getattr(slide, field)[:limit].rstrip()
        for field, limit in SLOT_LIMITS.items()
        if len(getattr(slide, field)) > limit
    }
    if clipped:
        logger.warning("design draft slot(s) over the renderer's limit, cut: %s", sorted(clipped))
    return slide.model_copy(update=clipped)
