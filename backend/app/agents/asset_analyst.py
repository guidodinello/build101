import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from app.llm.client import ChatModel, image_content, text_content
from app.prompts import load_prompt

from .schemas import AssetAnalysis

AGENT = "asset_analyst"
SYSTEM_PROMPT = load_prompt(Path(__file__).parent / "prompts" / "asset_analyst.md")
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True, slots=True)
class CatalogProduct:
    id: str
    name: str
    description: str


async def analyze_photo(
    model: ChatModel,
    image: bytes,
    catalog: list[CatalogProduct],
    owner_hint: str | None,
    linked_product_id: str | None,
) -> AssetAnalysis:
    """Describe one photo (a JPEG of at most 1536 px a side) for the other agents."""
    blocks = [
        f"<catalog>\n{json.dumps([asdict(p) for p in catalog], ensure_ascii=False)}\n</catalog>"
    ]
    if owner_hint:
        blocks.append(f"<owner_hint>{owner_hint}</owner_hint>")
    linked = next((p for p in catalog if p.id == linked_product_id), None)
    if linked:
        blocks.append(f"<linked_product>{linked.id}: {linked.name}</linked_product>")
    analysis = await model.structured(
        AGENT,
        SYSTEM_PROMPT,
        [text_content("\n".join(blocks)), image_content(image, "image/jpeg")],
        AssetAnalysis,
        "low",
    )
    known = {product.id for product in catalog}
    return analysis.model_copy(
        update={
            "product_ids": [pid for pid in dict.fromkeys(analysis.product_ids) if pid in known],
            "dominant_colors": [c.lower() for c in analysis.dominant_colors if HEX_COLOR.match(c)],
        }
    )
