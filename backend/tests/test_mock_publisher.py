from urllib.parse import parse_qs, urlparse

from app.publishing.base import PublisherPort, PublishMedia
from app.publishing.mock import MockPublisher

IMAGE = PublishMedia(format="image", url="https://img.test/1.jpg")


async def test_publish_returns_a_fake_permalink() -> None:
    result = await MockPublisher(delay_s=0).publish("acc", "hola", IMAGE)

    assert result.status == "published"
    assert result.permalink is not None
    assert result.permalink.startswith("https://instagram.com/p/MOCK-")
    assert result.external_post_id is not None
    assert result.external_post_id.startswith("mock-")


async def test_publish_accepts_and_ignores_an_idempotency_key() -> None:
    result = await MockPublisher(delay_s=0).publish("acc", "hola", IMAGE, idempotency_key="post-7")

    assert result.status == "published"


async def test_publish_accepts_a_reel() -> None:
    reel = PublishMedia(format="reel", url="https://video.test/1.mp4", cover_offset_ms=1000)

    result = await MockPublisher(delay_s=0).publish("acc", "hola", reel)

    assert result.status == "published"
    assert result.permalink is not None


async def test_each_publish_gets_its_own_id() -> None:
    publisher = MockPublisher(delay_s=0)

    first = await publisher.publish("acc", "a", IMAGE)
    second = await publisher.publish("acc", "b", IMAGE)

    assert first.permalink != second.permalink


async def test_connect_url_marks_the_account_connected() -> None:
    url = await MockPublisher(delay_s=0).connect_url(
        "prof", "instagram", "https://app.test/o/t?step=ig"
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert query["step"] == ["ig"]
    assert query["connected"] == ["instagram"]
    assert query["accountId"] == ["mock-account"]


async def test_ensure_profile_is_deterministic() -> None:
    assert await MockPublisher(delay_s=0).ensure_profile("Name", "biz-1") == "mock-profile-biz-1"


def test_satisfies_the_port() -> None:
    assert isinstance(MockPublisher(), PublisherPort)
