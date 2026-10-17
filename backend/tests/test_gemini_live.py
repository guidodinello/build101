import pytest

from app.config import get_settings
from app.imagegen.gemini import GeminiImageGen
from app.media.images import image_size
from tests.conftest import make_image

pytestmark = pytest.mark.live


async def test_gemini_returns_a_4_5_2k_image_with_usage() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        pytest.skip("GEMINI_API_KEY is not set")
    image_gen = GeminiImageGen.from_api_key(
        api_key=settings.gemini_api_key,
        model=settings.gemini_image_model,
        thinking_level="minimal",
        max_concurrency=1,
    )

    generated = await image_gen.generate(
        "A product photo of this terracotta cube on a white table, soft daylight. No text.",
        [make_image((800, 800), color="sienna")],
    )

    width, height = image_size(generated.data)
    assert abs(width / height - 4 / 5) < 0.01
    assert height >= 2000
    assert generated.usage["output_tokens"] > 0
