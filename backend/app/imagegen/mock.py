import asyncio
from io import BytesIO

from PIL import Image

from app.media.images import POST_SIZE, to_post_image

from .base import GeneratedImage

PROVIDER = "mock"
DELAY_S = 0.5
BLANK_COLOR = (230, 225, 215)


class MockImageGen:
    def __init__(self, delay_s: float = DELAY_S) -> None:
        self._delay_s = delay_s

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        style_image: bytes | None = None,
    ) -> GeneratedImage:
        await asyncio.sleep(self._delay_s)
        source = reference_images[0] if reference_images else style_image
        data = await asyncio.to_thread(to_post_image, source) if source else _blank_image()
        return GeneratedImage(data=data, mime="image/jpeg", provider=PROVIDER, model=None, usage={})


def _blank_image() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", POST_SIZE, BLANK_COLOR).save(buffer, format="JPEG")
    return buffer.getvalue()
