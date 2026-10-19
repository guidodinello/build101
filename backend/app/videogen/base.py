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
        """One clip per call. The 9:16 default is the Reel format (ADR 0033).

        Callers must not retry `generate` on their own: a timeout abandons an operation Google
        may still finish and bill, so a retry can bill a second clip. Only `VideoGenBlocked` is
        known not to bill (Veo docs); surface every other error instead of retrying.
        """
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
    """Transient (5xx, 408, 429, network, failed operation); still not safe to retry blindly."""


class VideoGenRejected(VideoGenError):
    """Google refused the request (4xx other than 408 and 429): retrying it cannot help."""


class VideoGenTimeout(VideoGenUnavailable):
    pass
