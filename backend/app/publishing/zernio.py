import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any, Self

import httpx

from .base import PublisherError, PublishMedia, PublishResult

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 30.0
# publishNow is documented as synchronous, but Instagram answers 201 "publishing" while it
# processes the media (observed on the live test, 2026-10-18); this only bounds the POST itself
PUBLISH_TIMEOUT_S = 120.0
# After a non-final answer, poll GET /posts/{id} until the wall-clock cap. A pending result at
# the cap is not a failure. Each poll gets its own short timeout, so a hung GET overruns the cap
# by at most one poll (cap + interval + POLL_REQUEST_TIMEOUT_S), not by the 30 s default
POLL_INTERVAL_S = 2.0
POLL_TIMEOUT_S = 90.0
POLL_REQUEST_TIMEOUT_S = 10.0
MAX_CAROUSEL_ITEMS = 10
MIN_CAROUSEL_ITEMS = 2
INSTAGRAM = "instagram"
STATUS_PUBLISHED = "published"
# Post statuses from Zernio's OpenAPI spec: these are final and mean the post did not go out
STATUSES_FAILED = frozenset({"failed", "partial", "cancelled"})
# Not final: still publishing, or (207) a transient error that Zernio retries on its own
STATUSES_PENDING = frozenset({"publishing", "scheduled"})
HTTP_CONFLICT = 409
ERROR_BODY_CHARS = 300

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]


class ZernioPublisher:
    """PublisherPort over Zernio's unified publishing API (ADR 0008).

    `sleep` and `clock` are injectable so tests drive the poll loop without waiting.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        sleep: Sleep = asyncio.sleep,
        poll_interval_s: float = POLL_INTERVAL_S,
        poll_timeout_s: float = POLL_TIMEOUT_S,
        clock: Clock = time.monotonic,
    ) -> None:
        if poll_interval_s <= 0:
            raise ValueError(f"poll_interval_s must be positive, got {poll_interval_s}")
        self._client = client
        self._sleep = sleep
        self._poll_interval_s = poll_interval_s
        self._poll_timeout_s = poll_timeout_s
        self._clock = clock

    @classmethod
    def from_settings(
        cls,
        api_key: str,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Sleep = asyncio.sleep,
        poll_interval_s: float = POLL_INTERVAL_S,
        poll_timeout_s: float = POLL_TIMEOUT_S,
        clock: Clock = time.monotonic,
    ) -> Self:
        client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=REQUEST_TIMEOUT_S,
            transport=transport,
        )
        return cls(client, sleep, poll_interval_s, poll_timeout_s, clock)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def ensure_profile(self, name: str, external_id: str) -> str:
        response = await self._request("GET", "/profiles", params={"externalId": external_id})
        profiles = _json(response).get("profiles") or []
        if profiles:
            return _field(profiles[0], "_id")

        response = await self._request(
            "POST",
            "/profiles",
            json={"name": name, "externalId": external_id},
            accept={HTTP_CONFLICT},
        )
        body = _json(response)
        if response.status_code == HTTP_CONFLICT:
            # a concurrent create (or a taken name) already made it: reuse that profile
            return _field(body.get("details") or {}, "existingProfileId")
        return _field(body.get("profile") or {}, "_id")

    async def connect_url(self, profile_id: str, platform: str, redirect_url: str) -> str:
        if platform != INSTAGRAM:
            raise ValueError(f"connect_url only supports {INSTAGRAM}, got {platform!r}")
        response = await self._request(
            "GET",
            f"/connect/{platform}",
            params={"profileId": profile_id, "redirect_url": redirect_url},
        )
        return _field(_json(response), "authUrl")

    async def publish(
        self,
        account_id: str,
        caption: str,
        media: PublishMedia,
        when: datetime | None = None,
        idempotency_key: str | None = None,
    ) -> PublishResult:
        if when is not None:
            raise NotImplementedError("scheduling is T30's Should part")
        body = {
            "content": caption,
            "mediaItems": [{"type": "image", "url": url} for url in _image_urls(media)],
            "platforms": [{"platform": INSTAGRAM, "accountId": account_id}],
            "publishNow": True,
        }
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        response = await self._request(
            "POST", "/posts", json=body, headers=headers, timeout=PUBLISH_TIMEOUT_S
        )
        result = _post_result(_json(response))
        if result.status == "pending":
            if not result.external_post_id:
                # nothing to poll and nothing for the webhook (T29) to match: surface it
                # instead of returning a pending result that can never be resolved
                raise PublisherError(
                    "zernio accepted the post but returned no post id, so it cannot be tracked; "
                    "it may still go live, so check the account before retrying "
                    "(a retry with the same Idempotency-Key replays the original post)"
                )
            result = await self._wait_for_outcome(result.external_post_id, result)
        logger.info(
            "zernio publish: http=%d status=%s post=%s",
            response.status_code,
            result.status,
            result.external_post_id,
        )
        return result

    async def _wait_for_outcome(self, post_id: str, pending: PublishResult) -> PublishResult:
        """Poll the post until Zernio reports a final outcome. Never re-POSTs, never raises.

        The post already exists, so raising here would invite a retry and a duplicate: a poll
        that fails is logged and skipped, and reaching the wall-clock cap returns `pending`.
        """
        start = self._clock()
        deadline = start + self._poll_timeout_s
        result = pending
        attempt = 0
        while self._clock() < deadline:
            attempt += 1
            await self._sleep(self._poll_interval_s)
            try:
                response = await self._request(
                    "GET", f"/posts/{post_id}", timeout=POLL_REQUEST_TIMEOUT_S
                )
                result = _post_result(_json(response))
            except PublisherError as exc:
                logger.warning("zernio poll %d for post %s failed: %s", attempt, post_id, exc)
                continue
            if result.status != "pending":
                return result
        waited_s = self._clock() - start
        return result.model_copy(
            update={
                "external_post_id": post_id,
                "error": f"still publishing after {waited_s:.0f} s",
            }
        )

    async def _request(
        self,
        method: str,
        url: str,
        accept: set[int] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send a request; raise PublisherError unless it succeeded or its status is in `accept`."""
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise PublisherError(f"zernio request failed: {exc!r}") from exc
        if response.is_error and response.status_code not in (accept or set()):
            raise PublisherError(
                f"zernio {response.status_code}: {response.text[:ERROR_BODY_CHARS]}"
            )
        return response


def _image_urls(media: PublishMedia) -> list[str]:
    match media.format:
        case "image":
            if not media.url:
                raise ValueError("an image post needs media.url")
            return [media.url]
        case "carousel":
            if not MIN_CAROUSEL_ITEMS <= len(media.urls) <= MAX_CAROUSEL_ITEMS:
                raise ValueError(
                    f"a carousel takes {MIN_CAROUSEL_ITEMS} to {MAX_CAROUSEL_ITEMS} images, "
                    f"got {len(media.urls)}"
                )
            return media.urls
        case "reel":
            raise NotImplementedError("reels are a Could (not built yet)")


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise PublisherError(f"zernio returned a non-JSON body: {response.text[:200]}") from exc
    if not isinstance(body, dict):
        raise PublisherError("zernio returned an unexpected body")
    return body


def _field(obj: Any, key: str) -> str:
    value = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(value, str) or not value:
        raise PublisherError(f"zernio response has no {key}")
    return value


def _post_result(body: dict[str, Any]) -> PublishResult:
    """Map a create-post or get-post body to a result, by `post.status` alone.

    Only a final failure maps to `failed`: anything not final (including a post that is live
    but whose permalink is not there yet) is `pending`, so the caller never reports a failure
    for a post that may still go out.
    """
    post = body.get("post")
    if not isinstance(post, dict):
        raise PublisherError("zernio response has no post")
    post_id = post.get("_id") if isinstance(post.get("_id"), str) else None
    status = post.get("status")
    target = next(
        (
            p
            for p in post.get("platforms") or []
            if isinstance(p, dict) and p.get("platform") == INSTAGRAM
        ),
        {},
    )

    if status == STATUS_PUBLISHED:
        permalink = target.get("platformPostUrl")
        if isinstance(permalink, str) and permalink:
            return PublishResult(status="published", external_post_id=post_id, permalink=permalink)
        return PublishResult(
            status="pending",
            external_post_id=post_id,
            error="published, but Zernio has no permalink yet",
        )
    if status in STATUSES_FAILED:
        reason = target.get("errorMessage") or body.get("error") or f"post status {status!r}"
        return PublishResult(status="failed", external_post_id=post_id, error=str(reason))
    if status not in STATUSES_PENDING:
        logger.warning("zernio post %s has an unknown status %r", post_id, status)
    return PublishResult(
        status="pending", external_post_id=post_id, error=f"post status {status!r}"
    )
