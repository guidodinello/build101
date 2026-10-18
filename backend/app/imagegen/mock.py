import asyncio
from io import BytesIO

from PIL import Image, ImageOps

from app.media.images import POST_SIZE

from .base import GeneratedImage

PROVIDER = "mock"
DELAY_S = 0.5
BLANK_COLOR = (230, 225, 215)
MOCK_HEIGHT = POST_SIZE[1]


class MockImageGen:
    def __init__(self, delay_s: float = DELAY_S) -> None:
        self._delay_s = delay_s

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        style_image: bytes | None = None,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> GeneratedImage:
        await asyncio.sleep(self._delay_s)
        source = reference_images[0] if reference_images else style_image
        size = ratio_size(aspect_ratio) if aspect_ratio else POST_SIZE
        data = await asyncio.to_thread(_fitted_image, source, size)
        return GeneratedImage(data=data, mime="image/jpeg", provider=PROVIDER, model=None, usage={})


def ratio_size(aspect_ratio: str) -> tuple[int, int]:
    width, height = (int(part) for part in aspect_ratio.split(":"))
    return round(MOCK_HEIGHT * width / height), MOCK_HEIGHT


def _fitted_image(source: bytes | None, size: tuple[int, int]) -> bytes:
    """The first reference cropped to `size`, or a blank image without one."""
    if source is None:
        image = Image.new("RGB", size, BLANK_COLOR)
    else:
        with Image.open(BytesIO(source)) as opened:
            image = ImageOps.fit(ImageOps.exif_transpose(opened).convert("RGB"), size)
    buffer = BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()
