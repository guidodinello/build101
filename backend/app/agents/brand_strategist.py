import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.llm.client import ChatModel, text_content
from app.prompts import load_prompt

from .asset_analyst import HEX_COLOR
from .schemas import BrandBrain, FeaturedProduct, VisualIdentity

logger = logging.getLogger(__name__)

AGENT = "brand_strategist"
# Owners who ticked "Todavía no tengo logo ni colores" start with this until they pick colors.
NEUTRAL_PALETTE = ("#3d3d3d", "#8a8a8a", "#c9a227", "#f5f2ec", "#1f1f1f")
SYSTEM_PROMPT = load_prompt(Path(__file__).parent / "prompts" / "brand_strategist.md").format(
    neutral_palette=", ".join(NEUTRAL_PALETTE)
)
MAX_SUMMARY_CHARS = 600
MAX_FEATURED = 5
DEFAULT_POSTS_PER_WEEK = 3
# The Owner's Instagram (ADR 0028): the captions that did best and the newest ones
MAX_TOP_CAPTIONS = 10
MAX_RECENT_CAPTIONS = 20
MAX_PROMPT_CAPTION_CHARS = 500
MAX_HASHTAGS = 20
HASHTAG = re.compile(r"#(\w+)")


@dataclass(frozen=True, slots=True)
class BrandInputs:
    business: dict[str, Any]
    catalog: list[dict[str, Any]]  # id, name, description, price
    questionnaire: dict[str, Any]
    brand_words: list[str]
    colors: list[str]  # the Owner's; empty when they have none yet
    logo_palette: list[str] = field(default_factory=list)
    logo_asset_id: str | None = None
    photo_descriptions: list[str] = field(default_factory=list)
    instagram: dict[str, Any] | None = None  # onboarding_data["instagram"], when connected
    previous: BrandBrain | None = None
    correction: str | None = None


async def write_brand_brain(model: ChatModel, inputs: BrandInputs) -> BrandBrain:
    """The Brand Brain from the onboarding answers, or a revision of `previous` (revise mode).

    The rules the model may bend are enforced afterwards in code; a summary over the limit gets
    one more try with the problem stated, then is kept as is.
    """
    content = [text_content(_prompt_input(inputs))]
    brain = _enforce(
        await model.structured(AGENT, SYSTEM_PROMPT, content, BrandBrain, "high"), inputs
    )
    if len(brain.whatsapp_summary) <= MAX_SUMMARY_CHARS:
        return brain
    retry = (
        f"Your whatsapp_summary had {len(brain.whatsapp_summary)} characters; the limit is "
        f"{MAX_SUMMARY_CHARS}. Write it again, shorter, keeping the format."
    )
    content.append(text_content(retry))
    brain = _enforce(
        await model.structured(AGENT, SYSTEM_PROMPT, content, BrandBrain, "high"), inputs
    )
    if len(brain.whatsapp_summary) > MAX_SUMMARY_CHARS:
        logger.warning("brand summary still %d chars after a retry", len(brain.whatsapp_summary))
    return brain


def _prompt_input(inputs: BrandInputs) -> str:
    def block(tag: str, value: Any) -> str:
        return f"<{tag}>\n{json.dumps(value, ensure_ascii=False, indent=1)}\n</{tag}>"

    colors = (
        {"owner_colors": inputs.colors, "logo_palette": inputs.logo_palette}
        if inputs.colors
        else {"owner_colors": "none yet", "logo_palette": inputs.logo_palette}
    )
    blocks = [
        block("business", inputs.business),
        block("catalog", inputs.catalog),
        block("questionnaire", inputs.questionnaire),
        block("brand_words", inputs.brand_words),
        block("colors", colors),
        block("photos", inputs.photo_descriptions),
    ]
    if inputs.instagram:
        blocks.append(block("instagram", _instagram_input(inputs.instagram)))
    if inputs.previous is not None and inputs.correction:
        blocks.append(block("previous_brand_brain", inputs.previous.model_dump()))
        blocks.append(f"<correction>{inputs.correction}</correction>")
    return "\n".join(blocks)


def _instagram_input(instagram: dict[str, Any]) -> dict[str, Any]:
    """The profile, a sample of captions (most engaged first, then the newest) and the hashtags
    the Owner uses most, out of everything the import read."""
    posts = [post for post in instagram.get("posts") or [] if post.get("caption")]
    by_engagement = sorted(
        range(len(posts)),
        key=lambda i: (posts[i].get("likes") or 0) + (posts[i].get("comments") or 0),
        reverse=True,
    )
    sample = dict.fromkeys(
        [*by_engagement[:MAX_TOP_CAPTIONS], *range(min(len(posts), MAX_RECENT_CAPTIONS))]
    )
    hashtags = Counter(tag.lower() for post in posts for tag in HASHTAG.findall(post["caption"]))
    return {
        "username": instagram.get("username"),
        "name": instagram.get("name"),
        "biography": instagram.get("biography"),
        "website": instagram.get("website"),
        "followers_count": instagram.get("followers_count"),
        "posts_read": len(instagram.get("posts") or []),
        "captions": [
            {
                "caption": posts[i]["caption"][:MAX_PROMPT_CAPTION_CHARS],
                "type": posts[i].get("type"),
                "likes": posts[i].get("likes"),
                "comments": posts[i].get("comments"),
            }
            for i in sample
        ],
        "top_hashtags": [f"#{tag}" for tag, _ in hashtags.most_common(MAX_HASHTAGS)],
    }


def _enforce(brain: BrandBrain, inputs: BrandInputs) -> BrandBrain:
    """Hold the model to the facts it was given (agents.md § Brand Strategist)."""
    catalog = {product["id"]: product for product in inputs.catalog}
    featured = [
        FeaturedProduct(
            product_id=item.product_id, name=catalog[item.product_id]["name"], why=item.why
        )
        for item in brain.featured_products
        if item.product_id in catalog
    ][:MAX_FEATURED]
    constraints = list(brain.constraints)
    avoid = (inputs.questionnaire.get("avoid") or "").strip()
    if avoid and avoid not in constraints:
        constraints.insert(0, avoid)
    goal = inputs.questionnaire.get("goal") or brain.goal
    posting = brain.posting.model_copy(
        update={
            "posts_per_week": inputs.questionnaire.get("posts_per_week") or DEFAULT_POSTS_PER_WEEK
        }
    )
    return brain.model_copy(
        update={
            "featured_products": featured,
            "constraints": constraints,
            "goal": goal,
            "posting": posting,
            "visual_identity": _visual_identity(brain.visual_identity, inputs),
        }
    )


def _visual_identity(identity: VisualIdentity, inputs: BrandInputs) -> VisualIdentity:
    if not inputs.colors:
        primary, secondary, accent, background, text = NEUTRAL_PALETTE
        return identity.model_copy(
            update={
                "primary_color": primary,
                "secondary_color": secondary,
                "accent_color": accent,
                "background_color": background,
                "text_color": text,
                "logo_asset_id": inputs.logo_asset_id,
            }
        )
    fixed: dict[str, Any] = {"logo_asset_id": inputs.logo_asset_id}
    # The Owner's own colors win over the model's guesses.
    if identity.primary_color.lower() not in inputs.colors:
        fixed["primary_color"] = inputs.colors[0]
    fallbacks = iter([*inputs.colors[1:], *inputs.logo_palette, *NEUTRAL_PALETTE[1:]])
    for name in (
        "primary_color",
        "secondary_color",
        "accent_color",
        "background_color",
        "text_color",
    ):
        color = fixed.get(name, getattr(identity, name))
        if not HEX_COLOR.match(color):
            fixed[name] = next(fallbacks)
    return identity.model_copy(update=fixed)
