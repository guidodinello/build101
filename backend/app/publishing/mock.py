import asyncio
from datetime import datetime
from urllib.parse import urlencode
from uuid import uuid4

from .base import PublishMedia, PublishResult

DELAY_S = 2.0
PERMALINK_PREFIX = "https://instagram.com/p/MOCK-"
MOCK_ACCOUNT_ID = "mock-account"
ID_CHARS = 8


class MockPublisher:
    """Offline PublisherPort: local dev, the simulator and the stage fallback."""

    def __init__(self, delay_s: float = DELAY_S) -> None:
        self._delay_s = delay_s

    async def ensure_profile(self, name: str, external_id: str) -> str:
        return f"mock-profile-{external_id}"

    async def connect_url(self, profile_id: str, platform: str, redirect_url: str) -> str:
        query = urlencode({"connected": platform, "accountId": MOCK_ACCOUNT_ID})
        separator = "&" if "?" in redirect_url else "?"
        return f"{redirect_url}{separator}{query}"

    async def publish(
        self,
        account_id: str,
        caption: str,
        media: PublishMedia,
        when: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> PublishResult:
        await asyncio.sleep(self._delay_s)
        post_id = uuid4().hex[:ID_CHARS]
        return PublishResult(
            status="published",
            external_post_id=f"mock-{post_id}",
            permalink=f"{PERMALINK_PREFIX}{post_id}",
        )
