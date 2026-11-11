from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel


class PublishMedia(BaseModel):
    format: Literal["image", "reel", "carousel"]
    url: str | None = None  # image/reel: public or long-lived signed URL
    urls: list[str] = []  # carousel, in slide order, <= 10 JPEGs (ADR 0022)
    cover_offset_ms: int | None = None  # reel only
    alt_texts: list[str] = []  # image: one entry; carousel: one per slide, in order
    ai_generated: bool = False  # asks Instagram to label the post as AI-generated media


class PublishResult(BaseModel):
    """Outcome of a publish call.

    `pending`: the provider accepted the post and has not reached a final outcome (it is still
    publishing, or retries a transient error on its own). The post may well go live: do not
    report a failure and do not re-publish; the webhook (T29) or a later status check confirms
    it. `scheduled` is reserved for a post the caller asked to publish later (T30).
    """

    status: Literal["published", "scheduled", "pending", "failed"]
    external_post_id: str | None = None
    permalink: str | None = None
    error: str | None = None


@runtime_checkable
class PublisherPort(Protocol):
    async def ensure_profile(self, name: str, external_id: str) -> str: ...

    async def connect_url(self, profile_id: str, platform: str, redirect_url: str) -> str: ...

    async def publish(
        self,
        account_id: str,
        caption: str,
        media: PublishMedia,
        when: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> PublishResult: ...


class PublisherError(Exception):
    """The provider could not be reached, or answered something we cannot use."""


class PublishRetryable(PublisherError):
    """The outcome is unknown: a timeout, a dropped connection, a 5xx, or an accepted post with
    no id. The post may have been saved anyway, so retry with the same `idempotency_key` (the
    provider replays the original post) and never report a failure while it is unresolved."""


class PublishInProgress(PublisherError):
    """A request with the same `idempotency_key` is still being processed (HTTP 409).

    Wait `retry_after_s` (when the provider said how long) and resend with the same key.
    """

    def __init__(self, message: str, retry_after_s: float | None = None) -> None:
        super().__init__(message)
        self.retry_after_s = retry_after_s
