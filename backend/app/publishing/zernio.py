import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Annotated, Any, Self

import httpx
from pydantic import BaseModel, BeforeValidator, Field, ValidationError

from .base import PublisherError, PublishInProgress, PublishMedia, PublishResult, PublishRetryable

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
HTTP_SERVER_ERROR = 500
IDEMPOTENCY_CONFLICT = "idempotency_conflict"
ERROR_BODY_CHARS = 300

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]


# Models for the parts of Zernio's answers we read; unknown fields are ignored. Only what the code
# needs is strict. Everything else degrades as it always has: `_post_result` runs on the answer to
# POST /posts, after the post may already exist, so an odd-shaped optional field must never turn
# into a final PublisherError.
def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _objects(value: object) -> list[object]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


class _Profile(BaseModel):
    id: str = Field(validation_alias="_id", min_length=1)


class _Profiles(BaseModel):
    profiles: Annotated[list[object] | None, BeforeValidator(lambda value: value or None)] = None


class _CreatedProfile(BaseModel):
    profile: _Profile


class _ConflictDetails(BaseModel):
    existing_profile_id: str = Field(validation_alias="existingProfileId", min_length=1)


class _ProfileConflict(BaseModel):
    details: _ConflictDetails


class _ConnectUrl(BaseModel):
    auth_url: str = Field(validation_alias="authUrl", min_length=1)


class _Target(BaseModel):
    platform: object = None
    platform_post_url: Annotated[str | None, BeforeValidator(_str_or_none)] = Field(
        default=None, validation_alias="platformPostUrl"
    )
    error_message: object = Field(default=None, validation_alias="errorMessage")


class _Post(BaseModel):
    id: Annotated[str | None, BeforeValidator(_str_or_none)] = Field(
        default=None, validation_alias="_id"
    )
    status: object = None
    platforms: Annotated[list[_Target], BeforeValidator(_objects)] = Field(default_factory=list)


class _PostBody(BaseModel):
    post: _Post
    error: object = None


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
        profiles = _parse(response, _Profiles, "profiles").profiles
        if profiles:
            return _validate(profiles[0], _Profile, "_id").id

        response = await self._request(
            "POST",
            "/profiles",
            json={"name": name, "externalId": external_id},
            accept={HTTP_CONFLICT},
        )
        if response.status_code == HTTP_CONFLICT:
            # a concurrent create (or a taken name) already made it: reuse that profile
            conflict = _parse(response, _ProfileConflict, "existingProfileId")
            return conflict.details.existing_profile_id
        return _parse(response, _CreatedProfile, "_id").profile.id

    async def connect_url(self, profile_id: str, platform: str, redirect_url: str) -> str:
        if platform != INSTAGRAM:
            raise ValueError(f"connect_url only supports {INSTAGRAM}, got {platform!r}")
        response = await self._request(
            "GET",
            f"/connect/{platform}",
            params={"profileId": profile_id, "redirect_url": redirect_url},
        )
        return _parse(response, _ConnectUrl, "authUrl").auth_url

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
        target: dict[str, Any] = {"platform": INSTAGRAM, "accountId": account_id}
        if instagram_data := _instagram_data(media):
            target["platformSpecificData"] = instagram_data
        body = {
            "content": caption,
            "mediaItems": _media_items(media),
            "platforms": [target],
            "publishNow": True,
        }
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        response = await self._request(
            "POST", "/posts", json=body, headers=headers, timeout=PUBLISH_TIMEOUT_S
        )
        result = _post_result(_parse(response, _PostBody, "post"))
        if result.status == "pending":
            if not result.external_post_id:
                # nothing to poll and nothing for the webhook (T29) to match: surface it
                # instead of returning a pending result that can never be resolved
                raise PublishRetryable(
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
                result = _post_result(_parse(response, _PostBody, "post"))
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
        except httpx.TransportError as exc:  # timeouts and dropped connections: outcome unknown
            raise PublishRetryable(f"zernio request failed: {exc!r}") from exc
        except httpx.HTTPError as exc:
            raise PublisherError(f"zernio request failed: {exc!r}") from exc
        if response.is_error and response.status_code not in (accept or set()):
            raise _status_error(response)
        return response


def _status_error(response: httpx.Response) -> PublisherError:
    """Classify an error response: unknown outcome (5xx), same key in flight (409), or final."""
    message = f"zernio {response.status_code}: {response.text[:ERROR_BODY_CHARS]}"
    if response.status_code >= HTTP_SERVER_ERROR:
        return PublishRetryable(message)
    if response.status_code == HTTP_CONFLICT:
        # The in-flight 409 has no documented body, so Retry-After is the signal; a duplicate-
        # content 409 has none and is final.
        retry_after = response.headers.get("Retry-After", "")
        if retry_after or IDEMPOTENCY_CONFLICT in response.text:
            seconds = float(retry_after) if retry_after.replace(".", "", 1).isdigit() else None
            return PublishInProgress(message, seconds)
    return PublisherError(message)


def _media_items(media: PublishMedia) -> list[dict[str, str]]:
    match media.format:
        case "image":
            if not media.url:
                raise ValueError("an image post needs media.url")
            return [{"type": "image", "url": media.url}]
        case "carousel":
            if not MIN_CAROUSEL_ITEMS <= len(media.urls) <= MAX_CAROUSEL_ITEMS:
                raise ValueError(
                    f"a carousel takes {MIN_CAROUSEL_ITEMS} to {MAX_CAROUSEL_ITEMS} images, "
                    f"got {len(media.urls)}"
                )
            return [{"type": "image", "url": url} for url in media.urls]
        case "reel":
            # A single video item with no contentType publishes as a Reel (Zernio Instagram
            # posts: https://docs.zernio.com/platforms/instagram/posts). Video limits (MP4/MOV,
            # H.264, 9:16, 3-90 s, <= 300 MB): https://docs.zernio.com/platforms/instagram/media
            if not media.url:
                raise ValueError("a reel needs media.url")
            if media.cover_offset_ms is not None and media.cover_offset_ms < 0:
                raise ValueError(f"cover_offset_ms must be >= 0, got {media.cover_offset_ms}")
            return [{"type": "video", "url": media.url}]


def _instagram_data(media: PublishMedia) -> dict[str, Any]:
    """Instagram `platformSpecificData`, only the fields that differ from Zernio's defaults.

    `thumbOffset` (ms into the video) picks the Reel cover; `isAiGenerated` adds Instagram's
    AI label (https://docs.zernio.com/platforms/instagram/fields, OpenAPI v1.297.1).
    """
    data: dict[str, Any] = {}
    if media.format == "reel" and media.cover_offset_ms is not None:
        data["thumbOffset"] = media.cover_offset_ms
    if media.ai_generated:
        data["isAiGenerated"] = True
    return data


def _parse[M: BaseModel](response: httpx.Response, model: type[M], label: str) -> M:
    try:
        body = response.json()
    except ValueError as exc:
        raise PublisherError(f"zernio returned a non-JSON body: {response.text[:200]}") from exc
    return _validate(body, model, label)


def _validate[M: BaseModel](data: object, model: type[M], label: str) -> M:
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise PublisherError(f"zernio response has no {label}") from exc


def _post_result(body: _PostBody) -> PublishResult:
    """Map a create-post or get-post body to a result, by `post.status` alone.

    Only a final failure maps to `failed`: anything not final (including a post that is live
    but whose permalink is not there yet) is `pending`, so the caller never reports a failure
    for a post that may still go out.
    """
    post = body.post
    post_id = post.id
    status = post.status
    target = next((p for p in post.platforms if p.platform == INSTAGRAM), _Target())

    if status == STATUS_PUBLISHED:
        if target.platform_post_url:
            return PublishResult(
                status="published", external_post_id=post_id, permalink=target.platform_post_url
            )
        return PublishResult(
            status="pending",
            external_post_id=post_id,
            error="published, but Zernio has no permalink yet",
        )
    if status in STATUSES_FAILED:
        reason = target.error_message or body.error or f"post status {status!r}"
        return PublishResult(status="failed", external_post_id=post_id, error=str(reason))
    if status not in STATUSES_PENDING:
        logger.warning("zernio post %s has an unknown status %r", post_id, status)
    return PublishResult(
        status="pending", external_post_id=post_id, error=f"post status {status!r}"
    )
