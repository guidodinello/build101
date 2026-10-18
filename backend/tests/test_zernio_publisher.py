import json
from collections.abc import Callable
from datetime import UTC, datetime

import httpx
import pytest

from app.publishing.base import PublisherError, PublishMedia
from app.publishing.zernio import ZernioPublisher

BASE_URL = "https://zernio.test/api/v1"
ACCOUNT_ID = "acc-1"
PERMALINK = "https://www.instagram.com/p/ABC123/"
IMAGE = PublishMedia(format="image", url="https://img.test/1.jpg")

Handler = Callable[[httpx.Request], httpx.Response]


def publisher_with(handler: Handler) -> tuple[ZernioPublisher, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    publisher = ZernioPublisher.from_settings(
        api_key="sk_test", base_url=BASE_URL, transport=httpx.MockTransport(record)
    )
    return publisher, requests


def post_body(status: str, *, platform_status: str | None = None, **target: str) -> dict:
    return {
        "post": {
            "_id": "post-1",
            "status": status,
            "platforms": [
                {
                    "platform": "instagram",
                    "status": platform_status or status,
                    "platformPostId": "17890",
                    **target,
                }
            ],
        }
    }


def respond(status_code: int, body: dict) -> Handler:
    return lambda request: httpx.Response(status_code, json=body)


async def test_publish_image() -> None:
    publisher, requests = publisher_with(
        respond(201, post_body("published", platformPostUrl=PERMALINK))
    )

    result = await publisher.publish(ACCOUNT_ID, "hola", IMAGE)

    assert result.status == "published"
    assert result.external_post_id == "post-1"
    assert result.permalink == PERMALINK
    [request] = requests
    assert request.method == "POST"
    assert str(request.url) == f"{BASE_URL}/posts"
    assert request.headers["authorization"] == "Bearer sk_test"
    assert json.loads(request.content) == {
        "content": "hola",
        "mediaItems": [{"type": "image", "url": "https://img.test/1.jpg"}],
        "platforms": [{"platform": "instagram", "accountId": ACCOUNT_ID}],
        "publishNow": True,
    }


async def test_publish_carousel_keeps_slide_order() -> None:
    urls = [f"https://img.test/s{i}.jpg" for i in (3, 1, 2)]
    publisher, requests = publisher_with(
        respond(201, post_body("published", platformPostUrl=PERMALINK))
    )

    await publisher.publish(ACCOUNT_ID, "x", PublishMedia(format="carousel", urls=urls))

    [request] = requests
    sent = [item["url"] for item in json.loads(request.content)["mediaItems"]]
    assert sent == urls


@pytest.mark.parametrize("count", [0, 1, 11])
async def test_carousel_size_is_validated_before_any_request(count: int) -> None:
    publisher, requests = publisher_with(respond(201, {}))
    media = PublishMedia(
        format="carousel", urls=[f"https://img.test/{i}.jpg" for i in range(count)]
    )

    with pytest.raises(ValueError, match="2 to 10"):
        await publisher.publish(ACCOUNT_ID, "x", media)
    assert requests == []


async def test_image_needs_a_url() -> None:
    publisher, _ = publisher_with(respond(201, {}))

    with pytest.raises(ValueError, match="media.url"):
        await publisher.publish(ACCOUNT_ID, "x", PublishMedia(format="image"))


async def test_reel_and_scheduling_are_not_built() -> None:
    publisher, _ = publisher_with(respond(201, {}))

    with pytest.raises(NotImplementedError, match="reels"):
        await publisher.publish(ACCOUNT_ID, "x", PublishMedia(format="reel", url="u"))
    with pytest.raises(NotImplementedError, match="T30"):
        await publisher.publish(ACCOUNT_ID, "x", IMAGE, when=datetime.now(UTC))


@pytest.mark.parametrize("post_status", ["failed", "partial"])
async def test_207_terminal_status_is_a_failure(post_status: str) -> None:
    body = post_body(post_status, platform_status="failed", errorMessage="bad media url")
    publisher, _ = publisher_with(respond(207, body))

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "failed"
    assert result.error == "bad media url"
    assert result.permalink is None
    assert result.external_post_id == "post-1"


async def test_207_scheduled_means_zernio_is_retrying() -> None:
    publisher, _ = publisher_with(respond(207, post_body("scheduled", platform_status="pending")))

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "retrying"
    assert result.external_post_id == "post-1"


async def test_207_is_never_a_success_even_if_the_post_says_published() -> None:
    publisher, _ = publisher_with(respond(207, post_body("published", platformPostUrl=PERMALINK)))

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "failed"


async def test_201_with_a_non_published_status_is_a_failure() -> None:
    publisher, _ = publisher_with(respond(201, post_body("publishing")))

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "failed"
    assert "publishing" in (result.error or "")


async def test_published_without_a_permalink_is_an_error() -> None:
    publisher, _ = publisher_with(respond(201, post_body("published")))

    with pytest.raises(PublisherError, match="platformPostUrl"):
        await publisher.publish(ACCOUNT_ID, "x", IMAGE)


async def test_response_without_a_post_is_an_error() -> None:
    publisher, _ = publisher_with(respond(201, {"message": "ok"}))

    with pytest.raises(PublisherError, match="no post"):
        await publisher.publish(ACCOUNT_ID, "x", IMAGE)


@pytest.mark.parametrize("status_code", [400, 403, 409, 429, 500])
async def test_http_errors_raise_with_the_status(status_code: int) -> None:
    publisher, _ = publisher_with(respond(status_code, {"error": "nope"}))

    with pytest.raises(PublisherError, match=f"zernio {status_code}"):
        await publisher.publish(ACCOUNT_ID, "x", IMAGE)


async def test_network_errors_raise() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    publisher, _ = publisher_with(down)

    with pytest.raises(PublisherError, match="request failed"):
        await publisher.publish(ACCOUNT_ID, "x", IMAGE)


async def test_ensure_profile_returns_the_existing_one_without_creating() -> None:
    publisher, requests = publisher_with(respond(200, {"profiles": [{"_id": "prof-1"}]}))

    assert await publisher.ensure_profile("Muebles", "biz-1") == "prof-1"

    [request] = requests
    assert request.method == "GET"
    assert request.url.params["externalId"] == "biz-1"


async def test_ensure_profile_creates_when_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"profiles": []})
        return httpx.Response(201, json={"profile": {"_id": "prof-2"}})

    publisher, requests = publisher_with(handler)

    assert await publisher.ensure_profile("Muebles", "biz-1") == "prof-2"

    assert json.loads(requests[1].content) == {"name": "Muebles", "externalId": "biz-1"}


async def test_ensure_profile_recovers_from_a_409() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"profiles": []})
        return httpx.Response(409, json={"details": {"existingProfileId": "prof-3"}})

    publisher, _ = publisher_with(handler)

    assert await publisher.ensure_profile("Muebles", "biz-1") == "prof-3"


async def test_connect_url_returns_the_auth_url() -> None:
    publisher, requests = publisher_with(
        respond(200, {"authUrl": "https://auth.test/x", "state": "s"})
    )

    url = await publisher.connect_url("prof-1", "instagram", "https://app.test/back?a=1")

    assert url == "https://auth.test/x"
    [request] = requests
    assert request.url.path == "/api/v1/connect/instagram"
    assert request.url.params["profileId"] == "prof-1"
    assert request.url.params["redirect_url"] == "https://app.test/back?a=1"


async def test_connect_url_only_supports_instagram() -> None:
    publisher, _ = publisher_with(respond(200, {}))

    with pytest.raises(ValueError, match="instagram"):
        await publisher.connect_url("prof-1", "facebook", "https://app.test/back")
