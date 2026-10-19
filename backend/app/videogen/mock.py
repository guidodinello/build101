import asyncio
from pathlib import Path

from .base import GeneratedVideo

PROVIDER = "mock"
DELAY_S = 0.5
# A 1 s 360x640 (9:16) solid-color H.264 clip, made once with:
#   ffmpeg -f lavfi -i color=c=0xE6E1D7:s=360x640:d=1:r=24 -c:v libx264 -pix_fmt yuv420p \
#     -movflags +faststart mock.mp4
# It lives under app/ (not tests/) so the Docker image ships it: the mock is the demo fallback.
MOCK_VIDEO = Path(__file__).parent / "mock.mp4"


class MockVideoGen:
    def __init__(self, delay_s: float = DELAY_S) -> None:
        self._delay_s = delay_s

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        *,
        aspect_ratio: str = "9:16",
        duration_seconds: int = 8,
    ) -> GeneratedVideo:
        await asyncio.sleep(self._delay_s)
        data = await asyncio.to_thread(MOCK_VIDEO.read_bytes)
        return GeneratedVideo(
            data=data,
            mime="video/mp4",
            provider=PROVIDER,
            model=None,
            duration_seconds=duration_seconds,
        )
