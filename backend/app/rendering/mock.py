import base64

from .base import SlideRender


class MockRenderer:
    """Returns the scene unchanged: for tests and local runs without the frontend."""

    def __init__(self) -> None:
        self.slides: list[SlideRender] = []

    async def render(self, slide: SlideRender) -> bytes:
        self.slides.append(slide)
        return base64.b64decode(slide.image.split(",", 1)[1])
