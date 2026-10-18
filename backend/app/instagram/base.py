from datetime import datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class InstagramError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class InstagramToken(BaseModel):
    access_token: str
    user_id: str
    expires_at: datetime | None


class InstagramProfile(BaseModel):
    user_id: str
    username: str
    name: str | None = None
    biography: str | None = None
    website: str | None = None
    followers_count: int | None = None
    media_count: int | None = None


class InstagramImage(BaseModel):
    """One image to import: a photo, a carousel slide, or the cover of a video."""

    id: str
    url: str


class InstagramMedia(BaseModel):
    id: str
    media_type: str  # IMAGE, VIDEO or CAROUSEL_ALBUM
    caption: str | None = None
    permalink: str | None = None
    timestamp: datetime | None = None
    like_count: int | None = None
    comments_count: int | None = None
    images: list[InstagramImage] = []


@runtime_checkable
class InstagramPort(Protocol):
    """Read access to the Owner's Instagram account through Instagram Login (ADR 0028)."""

    def authorize_url(self, redirect_uri: str, state: str) -> str: ...

    async def exchange_code(self, code: str, redirect_uri: str) -> InstagramToken: ...

    async def profile(self, access_token: str) -> InstagramProfile: ...

    async def recent_media(self, access_token: str, limit: int) -> list[InstagramMedia]: ...

    async def download(self, url: str) -> tuple[bytes, str]: ...
