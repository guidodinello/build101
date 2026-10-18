from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel


class PublishMedia(BaseModel):
    format: Literal["image", "reel", "carousel"]
    url: str | None = None  # image/reel: public or long-lived signed URL
    urls: list[str] = []  # carousel, in slide order, <= 10 JPEGs (ADR 0022)
    cover_offset_ms: int | None = None  # reel only


class PublishResult(BaseModel):
    """Outcome of a publish call.

    `retrying`: the provider accepted the post and retries on its own. Do not re-publish;
    the webhook (T29) or a later status check confirms it. `scheduled` is reserved for a
    post the caller asked to publish later (T30).
    """

    status: Literal["published", "scheduled", "retrying", "failed"]
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
    ) -> PublishResult: ...


class PublisherError(Exception):
    """The provider could not be reached, or answered something we cannot use."""
