import logging
from pathlib import Path

from pydantic import BaseModel

from app.carousel.schemas import (
    MAX_SLIDES,
    CarouselBrief,
    CarouselCopy,
    SlideCopy,
    SlideRole,
    SlideScene,
)
from app.llm.client import ChatModel, Content, image_content, text_content

logger = logging.getLogger(__name__)

AGENT = "post_drafter"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "draft.md").read_text()


class PostCopy(BaseModel):
    caption: str
    hashtags: list[str]


class SlideDraft(BaseModel):
    role: SlideRole
    headline: str
    body: str
    scene_prompt: str


class CarouselDraft(BaseModel):
    caption: str
    hashtags: list[str]
    style_prompt: str
    style_notes: str
    slides: list[SlideDraft]


class PostDrafter:
    """Brief + photos → the post's copy, and for a design the generator's input too.

    One structured call, a stand-in for the Copywriter and the Art Director (T13, T14) until
    the Brand Brain exists. `trend_notes` come from the latest Niche Report (ADR 0025).
    """

    def __init__(self, model: ChatModel, trend_notes: str | None = None) -> None:
        self._model = model
        self._trend_notes = trend_notes

    async def copy(self, brief: str, photos: list[bytes]) -> PostCopy:
        request = (
            f"Write the caption for a post of {len(photos)} photo(s), posted as they are, "
            f"without a design.\n\nBrief: {brief}{self._trend_section()}"
        )
        return await self._model.structured(
            AGENT, SYSTEM_PROMPT, request_content(request, photos), PostCopy, "medium"
        )

    async def design(
        self, brief: str, photos: list[bytes], photo_ids: list[str], slide_count: int
    ) -> tuple[CarouselCopy, CarouselBrief]:
        one_per_photo = (
            " Each slide is built from its own photo, in order."
            if len(photos) == slide_count
            else ""
        )
        request = (
            f"A design of exactly {slide_count} slide(s) (4:5).{one_per_photo}\n\n"
            f"Brief: {brief}{self._trend_section()}"
        )
        draft = await self._model.structured(
            AGENT, SYSTEM_PROMPT, request_content(request, photos), CarouselDraft, "medium"
        )
        slides = fit_slides(draft.slides, slide_count)
        copy = CarouselCopy(
            caption=draft.caption,
            hashtags=draft.hashtags,
            slides=[
                SlideCopy(role=slide.role, headline=slide.headline, body=slide.body or None)
                for slide in slides
            ],
        )
        carousel_brief = CarouselBrief(
            reference_asset_ids=photo_ids,
            style_prompt=draft.style_prompt,
            slides=[
                SlideScene(index=n, scene_prompt=slide.scene_prompt)
                for n, slide in enumerate(slides, start=1)
            ],
            style_notes=draft.style_notes,
        )
        return copy, carousel_brief

    def _trend_section(self) -> str:
        if not self._trend_notes:
            return ""
        return f"\n\nTrend notes (what works in the niche this week):\n{self._trend_notes}"


def request_content(request: str, photos: list[bytes]) -> list[Content]:
    return [text_content(request), *(image_content(photo, "image/jpeg") for photo in photos)]


def fit_slides(slides: list[SlideDraft], count: int) -> list[SlideDraft]:
    """Keep the requested number of slides (fewer if the model wrote fewer), cover first."""
    if not slides:
        raise ValueError("the design draft has no slides")
    if len(slides) != count:
        logger.warning("design draft has %d slides, %d requested", len(slides), count)
    fitted = slides[: min(count, MAX_SLIDES)]
    fitted[0] = fitted[0].model_copy(update={"role": "cover"})
    return fitted
