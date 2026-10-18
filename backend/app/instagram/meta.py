import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Self
from urllib.parse import urlencode

import httpx

from .base import InstagramError, InstagramImage, InstagramMedia, InstagramProfile, InstagramToken

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH_URL = "https://graph.instagram.com"
SCOPES = "instagram_business_basic"
REQUEST_TIMEOUT_S = 30.0
PAGE_SIZE = 50
ERROR_BODY_CHARS = 300
HTTP_BAD_REQUEST = 400

PROFILE_FIELDS = ("user_id", "username", "name", "followers_count", "media_count")
# Meta's IG User reference lists them, but its Instagram Login get-started page leaves them out
PROFILE_OPTIONAL_FIELDS = ("biography", "website")
CHILD_FIELDS = "children{id,media_type,media_url,thumbnail_url}"
MEDIA_FIELDS = (
    "id",
    "media_type",
    "media_url",
    "thumbnail_url",
    "permalink",
    "timestamp",
    "like_count",
    "comments_count",
    CHILD_FIELDS,
)
# Meta's IG Media reference labels `caption` "Facebook Login only"; Zernio reads it over
# Instagram Login, so it is asked for and dropped only if Meta refuses it
MEDIA_OPTIONAL_FIELDS = ("caption",)


class MetaInstagram:
    """InstagramPort over Meta's Instagram API with Instagram Login (ADR 0028)."""

    def __init__(
        self, client: httpx.AsyncClient, app_id: str, app_secret: str, graph_version: str
    ) -> None:
        self._client = client
        self._app_id = app_id
        self._app_secret = app_secret
        self._graph = f"{GRAPH_URL}/{graph_version}"

    @classmethod
    def from_settings(
        cls,
        app_id: str,
        app_secret: str,
        graph_version: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> Self:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, transport=transport)
        return cls(client, app_id, app_secret, graph_version)

    async def aclose(self) -> None:
        await self._client.aclose()

    def authorize_url(self, redirect_uri: str, state: str) -> str:
        query = {
            "client_id": self._app_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
        }
        return f"{AUTHORIZE_URL}?{urlencode(query)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> InstagramToken:
        """Authorization code → short-lived token → long-lived token (60 days)."""
        short = _json(
            await self._request(
                "POST",
                TOKEN_URL,
                data={
                    "client_id": self._app_id,
                    "client_secret": self._app_secret,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
        )
        # Meta has answered both {access_token, user_id} and {data: [{...}]}
        if isinstance(short.get("data"), list) and short["data"]:
            short = short["data"][0]
        short_token = _text(short, "access_token")
        user_id = str(short.get("user_id") or "")

        long = _json(
            await self._request(
                "GET",
                f"{GRAPH_URL}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": self._app_secret,
                    "access_token": short_token,
                },
            )
        )
        expires_in = long.get("expires_in")
        return InstagramToken(
            access_token=_text(long, "access_token"),
            user_id=user_id,
            expires_at=datetime.now(UTC) + timedelta(seconds=expires_in)
            if isinstance(expires_in, int)
            else None,
        )

    async def profile(self, access_token: str) -> InstagramProfile:
        body = await self._fields(
            f"{self._graph}/me", access_token, PROFILE_FIELDS, PROFILE_OPTIONAL_FIELDS
        )
        return InstagramProfile.model_validate(
            {**body, "user_id": str(body.get("user_id") or body.get("id") or "")}
        )

    async def recent_media(self, access_token: str, limit: int) -> list[InstagramMedia]:
        """The newest `limit` posts, Reels and carousels (never stories), newest first."""
        page = await self._fields(
            f"{self._graph}/me/media",
            access_token,
            MEDIA_FIELDS,
            MEDIA_OPTIONAL_FIELDS,
            {"limit": min(PAGE_SIZE, limit)},
        )
        media: list[InstagramMedia] = []
        while True:
            media.extend(_media(item) for item in page.get("data") or [] if isinstance(item, dict))
            next_url = (page.get("paging") or {}).get("next")
            if len(media) >= limit or not isinstance(next_url, str):
                return media[:limit]
            # The next link already carries the fields and the token
            page = _json(await self._request("GET", next_url))

    async def download(self, url: str) -> tuple[bytes, str]:
        response = await self._request("GET", url)
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        return response.content, content_type

    async def _fields(
        self,
        url: str,
        access_token: str,
        fields: tuple[str, ...],
        optional: tuple[str, ...],
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """GET with `fields` and `optional`; if Meta rejects that, again without `optional`."""
        base = {**(params or {}), "access_token": access_token}
        try:
            return _json(
                await self._request(
                    "GET", url, params={**base, "fields": ",".join(fields + optional)}
                )
            )
        except InstagramError as exc:
            if exc.status != HTTP_BAD_REQUEST:
                raise
            logger.warning("instagram refused %s, retrying without them: %s", optional, exc)
        return _json(await self._request("GET", url, params={**base, "fields": ",".join(fields)}))

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise InstagramError(f"instagram request failed: {exc!r}") from exc
        if response.is_error:
            raise InstagramError(
                f"instagram {response.status_code}: {response.text[:ERROR_BODY_CHARS]}",
                status=response.status_code,
            )
        return response


def _media(item: dict[str, Any]) -> InstagramMedia:
    media = InstagramMedia.model_validate({k: v for k, v in item.items() if k != "children"})
    children = (item.get("children") or {}).get("data") or [item]
    images = [image for child in children if (image := _image(child)) is not None]
    return media.model_copy(update={"images": images})


def _image(item: dict[str, Any]) -> InstagramImage | None:
    """The photo itself, or a video's cover; `media_url` is missing on copyrighted media."""
    url = item.get("thumbnail_url") if item.get("media_type") == "VIDEO" else item.get("media_url")
    if not isinstance(url, str) or not url or not item.get("id"):
        return None
    return InstagramImage(id=str(item["id"]), url=url)


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError as exc:
        raise InstagramError(f"instagram returned a non-JSON body: {response.text[:200]}") from exc
    if not isinstance(body, dict):
        raise InstagramError("instagram returned an unexpected body")
    return body


def _text(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value:
        raise InstagramError(f"instagram response has no {key}")
    return value
