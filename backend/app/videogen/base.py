from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class GeneratedVideo(BaseModel):
    data: bytes
    mime: str
    provider: str
    model: str | None
    duration_seconds: int  # Veo bills per second, so this is what a clip cost


@runtime_checkable
class VideoGenPort(Protocol):
    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        *,
        aspect_ratio: str = "9:16",
        duration_seconds: int = 8,
    ) -> GeneratedVideo:
        """One clip per call. The 9:16 default is the Reel format (ADR 0033)."""
        ...


class VideoGenError(Exception):
    pass


class VideoGenBlocked(VideoGenError):
    def __init__(self, reason: str) -> None:
        super().__init__(f"video generation blocked: {reason}")
        self.reason = reason


class VideoGenNoVideo(VideoGenError):
    pass


class VideoGenUnavailable(VideoGenError):
    pass


class VideoGenTimeout(VideoGenUnavailable):
    pass
