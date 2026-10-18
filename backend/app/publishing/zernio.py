import logging
from datetime import datetime
from typing import Any, Self

import httpx

from .base import PublisherError, PublishMedia, PublishResult

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_S = 30.0
# publishNow is synchronous: Zernio answers after Instagram has processed the media
PUBLISH_TIMEOUT_S = 120.0
MAX_CAROUSEL_ITEMS = 10
MIN_CAROUSEL_ITEMS = 2
INSTAGRAM = "instagram"
STATUS_PUBLISHED = "published"
# 207 with this post status: every platform hit a transient error and Zernio retries on its own
STATUS_RETRYING = "scheduled"
HTTP_CONFLICT = 409
HTTP_MULTI_STATUS = 207
ERROR_BODY_CHARS = 300


class ZernioPublisher:
    """PublisherPort over Zernio's unified publishing API (ADR 0008)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @classmethod
    def from_settings(
        cls,
        api_key: str,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> Self:
        client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=REQUEST_TIMEOUT_S,
            transport=transport,
        )
        return cls(client)

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
    ) -> PublishResult:
        if when is not None:
            raise NotImplementedError("scheduling is T30's Should part")
        body = {
            "content": caption,
            "mediaItems": [{"type": "image", "url": url} for url in _image_urls(media)],
            "platforms": [{"platform": INSTAGRAM, "accountId": account_id}],
            "publishNow": True,
        }
        response = await self._request(
            "POST", "/posts", json=body, timeout=PUBLISH_TIMEOUT_S, accept={HTTP_MULTI_STATUS}
        )
        result = _publish_result(response)
        logger.info(
            "zernio publish: http=%d status=%s post=%s",
            response.status_code,
            result.status,
            result.external_post_id,
        )
        return result

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


def _publish_result(response: httpx.Response) -> PublishResult:
    body = _json(response)
    post = body.get("post")
    if not isinstance(post, dict):
        raise PublisherError("zernio publish response has no post")
    post_id = post.get("_id") if isinstance(post.get("_id"), str) else None
    post_status = post.get("status")
    target = next(
        (
            p
            for p in post.get("platforms") or []
            if isinstance(p, dict) and p.get("platform") == INSTAGRAM
        ),
        {},
    )

    if post_status == STATUS_PUBLISHED and response.status_code != HTTP_MULTI_STATUS:
        return PublishResult(
            status="published",
            external_post_id=post_id,
            permalink=_field(target, "platformPostUrl"),
        )
    if post_status == STATUS_RETRYING and response.status_code == HTTP_MULTI_STATUS:
        return PublishResult(
            status="retrying", external_post_id=post_id, error="provider is retrying"
        )
    reason = (
        target.get("errorMessage")
        or body.get("error")
        or f"post status {post_status!r} (http {response.status_code})"
    )
    return PublishResult(status="failed", external_post_id=post_id, error=str(reason))
