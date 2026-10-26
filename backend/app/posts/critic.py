import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel

from app.carousel.schemas import (
    LAYOUTS,
    CarouselBrief,
    CarouselCopy,
    Emphasis,
    Focus,
    Surface,
)
from app.llm.client import Content, StructuredModel, image_content, text_content
from app.media.images import decode, review_copy
from app.rendering.base import RenderedSlide

logger = logging.getLogger(__name__)

AGENT = "design_critic"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "critic.md").read_text()
# A new scene is a paid image generation and adds a minute to the post (ADR 0035)
MAX_NEW_SCENES = 2


class SlideReview(BaseModel):
    """The knobs are plain strings ("keep" or a value): checked against the family in code."""

    index: int
    verdict: Literal["ok", "fix"]
    problems: list[str]
    layout: str
    focus: str
    emphasis: str
    surface: str
    new_scene: bool
    scene_note: str


class DesignReview(BaseModel):
    slides: list[SlideReview]

    @property
    def fixes(self) -> list[SlideReview]:
        return [slide for slide in self.slides if slide.verdict == "fix"]


@dataclass(frozen=True, slots=True)
class Revision:
    brief: CarouselBrief
    new_scenes: list[int]  # slides whose photo is generated again, 1-based


class DesignCritic:
    """Looks at a rendered carousel and asks for layout fixes before the Owner sees it."""

    def __init__(self, model: StructuredModel) -> None:
        self._model = model

    async def review(
        self, copy: CarouselCopy, brief: CarouselBrief, slides: list[RenderedSlide]
    ) -> DesignReview:
        previews = await asyncio.gather(*(decode(review_copy, slide.image) for slide in slides))
        content: list[Content] = [
            text_content(slide_sheet(copy, brief, slides)),
            *(image_content(preview, "image/jpeg") for preview in previews),
        ]
        return await self._model.structured(AGENT, SYSTEM_PROMPT, content, DesignReview, "medium")


def slide_sheet(copy: CarouselCopy, brief: CarouselBrief, slides: list[RenderedSlide]) -> str:
    """What each slide should show and what the renderer measured, for the critic."""
    sheet = []
    for words, design, rendered in zip(copy.slides, brief.slides, slides, strict=True):
        report = rendered.report
        sheet.append(
            {
                "index": design.index,
                "family": brief.family,
                "role": words.role,
                "drawn_layout": report.layout if report else design.layout,
                "knobs": design.model_dump(include={"layout", "emphasis", "focus", "surface"}),
                "layouts_in_family": list(LAYOUTS[brief.family]),
                "words": words.model_dump(exclude={"role"}, exclude_none=True),
                "fits": [fit.model_dump() for fit in report.fits] if report else [],
                "ink": [ink.model_dump() for ink in report.ink] if report else [],
            }
        )
    return json.dumps(sheet, ensure_ascii=False)


def revise(brief: CarouselBrief, review: DesignReview) -> Revision:
    """The brief with the critic's fixes; values the family doesn't have are ignored."""
    scenes = {scene.index: scene for scene in brief.slides}
    new_scenes: list[int] = []
    seen: set[int] = set()
    for fix in review.fixes:
        scene = scenes.get(fix.index)
        if scene is None or fix.index in seen:
            continue
        seen.add(fix.index)
        changes = knob_changes(brief, fix)
        if fix.new_scene and brief.family != "panorama" and len(new_scenes) < MAX_NEW_SCENES:
            new_scenes.append(fix.index)
            if fix.scene_note.strip():
                changes["scene_prompt"] = f"{scene.scene_prompt} Fix: {fix.scene_note.strip()}"
        scenes[fix.index] = scene.model_copy(update=changes)
    revised = brief.model_copy(update={"slides": [scenes[index] for index in sorted(scenes)]})
    return Revision(revised, new_scenes)


def knob_changes(brief: CarouselBrief, fix: SlideReview) -> dict[str, object]:
    allowed: dict[str, tuple[str, ...]] = {
        "layout": LAYOUTS[brief.family],
        "focus": get_args(Focus),
        "emphasis": get_args(Emphasis),
        "surface": get_args(Surface),
    }
    return {
        name: getattr(fix, name) for name, values in allowed.items() if getattr(fix, name) in values
    }


def changed(brief: CarouselBrief, revision: Revision) -> bool:
    return bool(revision.new_scenes) or revision.brief != brief
