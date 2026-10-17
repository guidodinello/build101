from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class GeneratedImage(BaseModel):
    data: bytes
    mime: str
    provider: str
    model: str | None
    usage: dict[str, int]
    finish_reason: str | None = None


@runtime_checkable
class ImageGenPort(Protocol):
    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        style_image: bytes | None = None,
    ) -> GeneratedImage: ...


class ImageGenError(Exception):
    pass


class ImageGenBlocked(ImageGenError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"image generation blocked: {reason}")
        self.reason = reason


class ImageGenNoImage(ImageGenError):
    pass


class ImageGenUnavailable(ImageGenError):
    pass
