"""Live Zernio checks (`uv run pytest -m live tests/test_zernio_live.py`).

The publish test posts to the real demo Instagram account. Zernio cannot delete a
published Instagram post (DELETE refuses published posts, unpublish is not supported on
Instagram), so delete the post by hand in the Instagram app; the test prints its link.

ZERNIO_TEST_IMAGE_URL must be a public HTTPS URL that serves the raw JPEG with no redirect.
The committed fixture works from raw.githubusercontent:

    https://raw.githubusercontent.com/guidodinello/build101/main/backend/tests/fixtures/zernio-live-test.jpg

Before the PR is merged, put the branch name in place of `main` (the branch is deleted
after the squash merge, so `main` only works once the file has landed there).
"""

import asyncio
import os
import uuid
import warnings
from datetime import UTC, datetime

import pytest

from app.config import get_settings
from app.posts.publish import MAX_RETRY_AFTER_S
from app.publishing.base import (
    PublishInProgress,
    PublishMedia,
    PublishResult,
    PublishRetryable,
)
from app.publishing.zernio import ZernioPublisher

pytestmark = pytest.mark.live

# The first attempt plus retries with the same idempotency key
LIVE_PUBLISH_ATTEMPTS = 3


def live_publisher() -> ZernioPublisher:
    settings = get_settings()
    if not settings.zernio_api_key:
        pytest.skip("ZERNIO_API_KEY is not set")
    return ZernioPublisher.from_settings(
        api_key=settings.zernio_api_key, base_url=settings.zernio_base_url
    )


async def publish_live(
    publisher: ZernioPublisher, account_id: str, caption: str, media: PublishMedia
) -> PublishResult:
    """Publish and close the publisher, retrying with one idempotency key.

    Zernio's create call can time out even when the post goes live; the same key makes the
    retry replay that post instead of publishing a second one (integrations.md § Zernio)
    """
    idempotency_key = f"live-test-{uuid.uuid4()}"
    try:
        for attempt in range(1, LIVE_PUBLISH_ATTEMPTS + 1):
            try:
                return await publisher.publish(
                    account_id, caption, media, idempotency_key=idempotency_key
                )
            except PublishInProgress as exc:
                if attempt == LIVE_PUBLISH_ATTEMPTS:
                    raise
                await asyncio.sleep(min(exc.retry_after_s or 5.0, MAX_RETRY_AFTER_S))
            except PublishRetryable:
                if attempt == LIVE_PUBLISH_ATTEMPTS:
                    raise
        raise AssertionError("unreachable")
    finally:
        await publisher.aclose()


async def test_publish_one_image_to_the_demo_account() -> None:
    settings = get_settings()
    image_url = os.environ.get("ZERNIO_TEST_IMAGE_URL")
    if not settings.zernio_account_id or not image_url:
        pytest.skip("ZERNIO_ACCOUNT_ID and ZERNIO_TEST_IMAGE_URL are not set")
    # Zernio rejects identical content to the same account within 24 h, so stamp the caption
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    caption = f"[test] build101 Zernio live publish {stamp}. Delete me."
    media = PublishMedia(format="image", url=image_url)
    publisher = live_publisher()
    result = await publish_live(publisher, settings.zernio_account_id, caption, media)

    assert result.status == "published", result.error
    assert result.permalink is not None
    assert result.permalink.startswith("https://www.instagram.com/")
    warnings.warn(f"delete this test post by hand in Instagram: {result.permalink}", stacklevel=1)


async def test_publish_one_reel_to_the_demo_account() -> None:
    settings = get_settings()
    video_url = os.environ.get("ZERNIO_TEST_VIDEO_URL")
    if not settings.zernio_account_id or not video_url:
        pytest.skip("ZERNIO_ACCOUNT_ID and ZERNIO_TEST_VIDEO_URL are not set")
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    caption = f"[test] build101 Zernio live reel {stamp}. Delete me."
    media = PublishMedia(format="reel", url=video_url, cover_offset_ms=1000)
    result = await publish_live(live_publisher(), settings.zernio_account_id, caption, media)

    # A Reel can still be processing when the poll window ends: that is `pending`, not a failure
    assert result.status in {"published", "pending"}, result.error
    where = result.permalink or "its link is not known yet: look for the caption on the account"
    warnings.warn(f"delete this test reel by hand in Instagram: {where}", stacklevel=1)


async def test_connect_url_for_the_demo_profile() -> None:
    settings = get_settings()
    if not settings.zernio_profile_id:
        pytest.skip("ZERNIO_PROFILE_ID is not set")
    publisher = live_publisher()
    try:
        url = await publisher.connect_url(
            settings.zernio_profile_id, "instagram", "https://example.com/connected"
        )
    finally:
        await publisher.aclose()

    assert url.startswith("https://")
