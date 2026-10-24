from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from app.config import get_settings
from app.knowledge.base import CatalogItem
from app.llm.client import GeminiChat
from app.posts.drafts import PostDrafter
from tests.conftest import make_image

pytestmark = pytest.mark.live


def live_drafter() -> PostDrafter:
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not set")
    return PostDrafter(GeminiChat.from_api_key(settings.gemini_api_key, settings.gemini_chat_model))


async def test_design_draft_matches_the_generator_input() -> None:
    copy, brief = await live_drafter().design(
        "Mesa ratona de roble nueva, destacar la veta", [make_image((400, 500))], ["f1"], 3
    )

    assert len(copy.slides) == 3
    assert copy.slides[0].role == "cover"
    assert [scene.index for scene in brief.slides] == [1, 2, 3]
    assert brief.reference_asset_ids == ["f1"]


def wooden_table() -> bytes:
    """A plain drawing of a wooden table: brown, with grain lines and no claim to back."""
    image = Image.new("RGB", (800, 1000), "#efe9df")
    draw = ImageDraw.Draw(image)
    draw.rectangle((120, 420, 680, 470), fill="#9a6a3c")
    for y in range(426, 466, 8):
        draw.line((130, y, 670, y + 3), fill="#7d5230", width=2)
    for x in (150, 630):
        draw.rectangle((x, 470, x + 30, 800), fill="#8a5d34")
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


UNBACKED_CLAIMS = ("macizo", "maciza", "hecho a mano", "hecha a mano", "hechoamano", "artesanal")
WOODS = ("roble", "nogal", "pino", "eucalipto", "lapacho", "cedro", "paraíso", "kiri")


async def test_a_table_photo_without_a_product_claims_no_wood_and_no_handmade() -> None:
    copy = await live_drafter().copy("Mesa de comedor nueva en el showroom", [wooden_table()])

    text = f"{copy.caption} {' '.join(copy.hashtags)}".lower()
    assert not any(claim in text for claim in (*UNBACKED_CLAIMS, *WOODS)), text


async def test_a_veneered_product_is_never_called_solid() -> None:
    product = CatalogItem("Mesa Ñandubay", None, "Mesa de comedor enchapada en roble, 1,80 m")

    copy = await live_drafter().copy(
        "Mesa de comedor nueva en el showroom", [wooden_table()], products=[product]
    )

    text = f"{copy.caption} {' '.join(copy.hashtags)}".lower()
    assert "macizo" not in text and "maciza" not in text, text
