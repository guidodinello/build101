import os

import pytest

from app.channels.kapso import KapsoChannel
from app.config import get_settings

pytestmark = pytest.mark.live


def live_channel() -> KapsoChannel:
    settings = get_settings()
    if not settings.kapso_api_key or not settings.kapso_phone_number_id:
        pytest.skip("KAPSO_API_KEY and KAPSO_PHONE_NUMBER_ID are not set")
    return KapsoChannel.from_settings(
        api_key=settings.kapso_api_key,
        phone_number_id=settings.kapso_phone_number_id,
        base_url=settings.kapso_base_url,
    )


async def test_send_text_to_the_test_recipient() -> None:
    recipient = os.environ.get("KAPSO_TEST_RECIPIENT")
    if not recipient:
        pytest.skip("KAPSO_TEST_RECIPIENT is not set")
    channel = live_channel()
    try:
        message_id = await channel.send_text(recipient, "build101 live smoke test")
    finally:
        await channel.aclose()

    assert message_id.startswith("wamid.")


async def test_download_media_two_step() -> None:
    media_id = os.environ.get("KAPSO_TEST_MEDIA_ID")
    if not media_id:
        pytest.skip("KAPSO_TEST_MEDIA_ID is not set")
    channel = live_channel()
    try:
        data, mime = await channel.download_media(media_id)
    finally:
        await channel.aclose()

    assert data
    assert "/" in mime
