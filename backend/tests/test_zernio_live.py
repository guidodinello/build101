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

import os
import warnings
from datetime import UTC, datetime

import pytest

from app.config import get_settings
from app.publishing.base import PublishMedia
from app.publishing.zernio import ZernioPublisher

pytestmark = pytest.mark.live


def live_publisher() -> ZernioPublisher:
    settings = get_settings()
    if not settings.zernio_api_key:
        pytest.skip("ZERNIO_API_KEY is not set")
    return ZernioPublisher.from_settings(
        api_key=settings.zernio_api_key, base_url=settings.zernio_base_url
    )


async def test_publish_one_image_to_the_demo_account() -> None:
    settings = get_settings()
    image_url = os.environ.get("ZERNIO_TEST_IMAGE_URL")
    if not settings.zernio_account_id or not image_url:
        pytest.skip("ZERNIO_ACCOUNT_ID and ZERNIO_TEST_IMAGE_URL are not set")
    # Zernio rejects identical content to the same account within 24 h, so stamp the caption
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    caption = f"[test] build101 Zernio live publish {stamp}. Delete me."
    publisher = live_publisher()
    try:
        result = await publisher.publish(
            settings.zernio_account_id, caption, PublishMedia(format="image", url=image_url)
        )
    finally:
        await publisher.aclose()

    assert result.status == "published", result.error
    assert result.permalink is not None
    assert result.permalink.startswith("https://www.instagram.com/")
    warnings.warn(f"delete this test post by hand in Instagram: {result.permalink}", stacklevel=1)


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
