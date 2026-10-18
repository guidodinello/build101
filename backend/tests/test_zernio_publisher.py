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


def publisher_with(
    handler: Handler,
    *,
    sleeps: list[float] | None = None,
    poll_interval_s: float = 2.0,
    poll_timeout_s: float = 90.0,
) -> tuple[ZernioPublisher, list[httpx.Request]]:
    """A publisher over a mocked transport. Its sleep only records, so no test waits."""
    requests: list[httpx.Request] = []
    slept = sleeps if sleeps is not None else []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    publisher = ZernioPublisher.from_settings(
        api_key="sk_test",
        base_url=BASE_URL,
        transport=httpx.MockTransport(record),
        sleep=fake_sleep,
        poll_interval_s=poll_interval_s,
        poll_timeout_s=poll_timeout_s,
    )
    return publisher, requests


def scripted(post: httpx.Response, *polls: httpx.Response | Exception) -> Handler:
    """Answer the POST with `post`, then each GET with the next of `polls` (the last repeats)."""
    queue = list(polls)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return post
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        return item

    return handler


def reply(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(status_code, json=body)


def posts(requests: list[httpx.Request], method: str) -> list[httpx.Request]:
    return [r for r in requests if r.method == method]


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


PUBLISHING = post_body("publishing", platform_status="processing")
PUBLISHED = post_body("published", platformPostUrl=PERMALINK)


async def test_201_publishing_then_published_polls_without_reposting() -> None:
    sleeps: list[float] = []
    publisher, requests = publisher_with(
        scripted(reply(201, PUBLISHING), reply(200, PUBLISHING), reply(200, PUBLISHED)),
        sleeps=sleeps,
    )

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "published"
    assert result.permalink == PERMALINK
    assert result.external_post_id == "post-1"
    assert len(posts(requests, "POST")) == 1
    polls = posts(requests, "GET")
    assert [str(p.url) for p in polls] == [f"{BASE_URL}/posts/post-1"] * 2
    assert all(p.headers["authorization"] == "Bearer sk_test" for p in polls)
    assert sleeps == [2.0, 2.0]


async def test_201_publishing_then_failed_returns_the_platform_error() -> None:
    failed = post_body("failed", platform_status="failed", errorMessage="media rejected")
    publisher, requests = publisher_with(scripted(reply(201, PUBLISHING), reply(200, failed)))

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "failed"
    assert result.error == "media rejected"
    assert len(posts(requests, "POST")) == 1


async def test_still_publishing_at_the_cap_is_pending_not_a_failure() -> None:
    sleeps: list[float] = []
    publisher, requests = publisher_with(
        scripted(reply(201, PUBLISHING), reply(200, PUBLISHING)),
        sleeps=sleeps,
        poll_interval_s=2.0,
        poll_timeout_s=6.0,
    )

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "pending"
    assert result.external_post_id == "post-1"
    assert "6 s" in (result.error or "")
    assert len(posts(requests, "POST")) == 1
    assert len(posts(requests, "GET")) == 3
    assert sleeps == [2.0, 2.0, 2.0]


def test_the_default_cap_is_90_seconds_in_2_second_polls() -> None:
    publisher = ZernioPublisher(httpx.AsyncClient())

    assert publisher._poll_attempts == 45


async def test_207_scheduled_is_zernio_retrying_then_it_lands() -> None:
    retrying = post_body("scheduled", platform_status="pending")
    publisher, requests = publisher_with(scripted(reply(207, retrying), reply(200, PUBLISHED)))

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "published"
    assert len(posts(requests, "POST")) == 1


async def test_207_scheduled_that_never_lands_is_pending() -> None:
    retrying = post_body("scheduled", platform_status="pending")
    publisher, _ = publisher_with(
        scripted(reply(207, retrying), reply(200, retrying)), poll_timeout_s=4.0
    )

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "pending"


async def test_an_unknown_status_is_pending_never_a_failure() -> None:
    publisher, _ = publisher_with(
        scripted(reply(201, post_body("brand-new-status")), reply(200, PUBLISHED))
    )

    assert (await publisher.publish(ACCOUNT_ID, "x", IMAGE)).status == "published"


async def test_published_without_a_permalink_waits_for_it() -> None:
    publisher, requests = publisher_with(
        scripted(reply(201, post_body("published")), reply(200, PUBLISHED))
    )

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "published"
    assert result.permalink == PERMALINK
    assert len(posts(requests, "POST")) == 1


async def test_published_that_never_gets_a_permalink_is_pending_without_raising() -> None:
    no_url = post_body("published")
    publisher, requests = publisher_with(
        scripted(reply(201, no_url), reply(200, no_url)), poll_timeout_s=4.0
    )

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "pending"
    assert result.permalink is None
    assert len(posts(requests, "POST")) == 1


async def test_a_published_post_with_a_permalink_is_not_polled() -> None:
    sleeps: list[float] = []
    publisher, requests = publisher_with(
        scripted(reply(201, PUBLISHED), reply(200, {})), sleeps=sleeps
    )

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "published"
    assert posts(requests, "GET") == []
    assert sleeps == []


async def test_failed_polls_are_skipped_and_the_post_is_not_resent() -> None:
    publisher, requests = publisher_with(
        scripted(
            reply(201, PUBLISHING),
            httpx.ConnectError("down"),
            reply(500, {"error": "boom"}),
            reply(200, {"message": "no post here"}),
            reply(200, PUBLISHED),
        )
    )

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "published"
    assert len(posts(requests, "POST")) == 1
    assert len(posts(requests, "GET")) == 4


async def test_every_poll_failing_is_pending_not_an_exception() -> None:
    publisher, _ = publisher_with(
        scripted(reply(201, PUBLISHING), httpx.ConnectError("down")), poll_timeout_s=4.0
    )

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    assert result.status == "pending"
    assert result.external_post_id == "post-1"


async def test_idempotency_key_goes_on_the_post_only() -> None:
    publisher, requests = publisher_with(scripted(reply(201, PUBLISHING), reply(200, PUBLISHED)))

    await publisher.publish(ACCOUNT_ID, "x", IMAGE, idempotency_key="post-7")

    [post] = posts(requests, "POST")
    assert post.headers["idempotency-key"] == "post-7"
    assert all("idempotency-key" not in g.headers for g in posts(requests, "GET"))


async def test_no_idempotency_header_when_no_key_is_given() -> None:
    publisher, requests = publisher_with(scripted(reply(201, PUBLISHED)))

    await publisher.publish(ACCOUNT_ID, "x", IMAGE)

    [post] = posts(requests, "POST")
    assert "idempotency-key" not in post.headers


async def test_a_200_replay_of_a_published_post_is_published() -> None:
    publisher, _ = publisher_with(scripted(reply(200, PUBLISHED)))

    result = await publisher.publish(ACCOUNT_ID, "x", IMAGE, idempotency_key="post-7")

    assert result.status == "published"
    assert result.permalink == PERMALINK


def test_the_poll_interval_must_be_positive() -> None:
    with pytest.raises(ValueError, match="poll_interval_s"):
        ZernioPublisher(httpx.AsyncClient(), poll_interval_s=0)


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
