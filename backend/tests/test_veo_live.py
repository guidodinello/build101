import pytest

from app.config import get_settings
from app.videogen.gemini import GeminiVideoGen
from tests.conftest import make_image

pytestmark = pytest.mark.live


async def test_veo_animates_a_product_image_into_a_9_16_mp4() -> None:
    """Billed (Lite, 4 s, about US$0.20): run on purpose with -m live, never in CI."""
    settings = get_settings()
    if not settings.gemini_video_api_key:
        pytest.skip("GEMINI_VIDEO_API_KEY is not set")
    video_gen = GeminiVideoGen.from_api_key(
        api_key=settings.gemini_video_api_key,
        model=settings.gemini_video_model,
        max_concurrency=1,
        timeout_s=settings.video_gen_timeout_s,
    )

    video = await video_gen.generate(
        "Slow push-in on this terracotta cube on a white table, soft daylight. No text.",
        [make_image((1080, 1350), color="sienna")],
        aspect_ratio="9:16",
        duration_seconds=4,
    )

    assert video.data[4:8] == b"ftyp"
    assert video.mime == "video/mp4"
