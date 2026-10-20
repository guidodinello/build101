import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Self
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, BeforeValidator, Field, ValidationError, model_validator

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


# Models for the parts of Meta's answers we read; unknown fields are ignored. Only what the code
# needs is strict (the access token, a media item's id and type). Everything else degrades the
# way it always has: null, a wrong type or a non-object list entry is treated as absent.
def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _id_or_none(value: object) -> str | None:
    return str(value) if value else None


def _object_or_none(value: object) -> object:
    return value if isinstance(value, dict) else None


def _objects(value: object) -> list[object]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


class _ShortToken(BaseModel):
    access_token: str = Field(min_length=1)
    user_id: Annotated[str, BeforeValidator(lambda value: str(value or ""))] = ""

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, data: object) -> object:
        # Meta has answered both {access_token, user_id} and {data: [{...}]}
        match data:
            case {"data": [first, *_]}:
                return first
            case _:
                return data


class _LongToken(BaseModel):
    access_token: str = Field(min_length=1)
    expires_in: Annotated[int | None, BeforeValidator(_int_or_none)] = None


class _ProfileResponse(InstagramProfile):
    """An InstagramProfile as Meta answers it: the id may come as `id`, and as a number."""

    @model_validator(mode="before")
    @classmethod
    def _user_id(cls, data: object) -> object:
        if isinstance(data, dict):
            return {**data, "user_id": str(data.get("user_id") or data.get("id") or "")}
        return data


class _MediaChild(BaseModel):
    id: Annotated[str | None, BeforeValidator(_id_or_none)] = None
    media_type: object = None
    media_url: Annotated[str | None, BeforeValidator(_str_or_none)] = None
    thumbnail_url: Annotated[str | None, BeforeValidator(_str_or_none)] = None


class _Children(BaseModel):
    data: Annotated[list[_MediaChild], BeforeValidator(_objects)] = Field(default_factory=list)


class _MediaItem(InstagramMedia):
    """A post as /me/media lists it: the fields InstagramMedia keeps, plus its image sources."""

    media_url: Annotated[str | None, BeforeValidator(_str_or_none)] = None
    thumbnail_url: Annotated[str | None, BeforeValidator(_str_or_none)] = None
    children: Annotated[_Children | None, BeforeValidator(_object_or_none)] = None


class _Paging(BaseModel):
    next: Annotated[str | None, BeforeValidator(_str_or_none)] = None


class _MediaPage(BaseModel):
    data: Annotated[list[_MediaItem], BeforeValidator(_objects)] = Field(default_factory=list)
    paging: Annotated[_Paging | None, BeforeValidator(_object_or_none)] = None


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
        short = _parse(
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
            ),
            _ShortToken,
        )
        long = _parse(
            await self._request(
                "GET",
                f"{GRAPH_URL}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": self._app_secret,
                    "access_token": short.access_token,
                },
            ),
            _LongToken,
        )
        return InstagramToken(
            access_token=long.access_token,
            user_id=short.user_id,
            expires_at=datetime.now(UTC) + timedelta(seconds=long.expires_in)
            if long.expires_in is not None
            else None,
        )

    async def profile(self, access_token: str) -> InstagramProfile:
        profile = await self._fields(
            f"{self._graph}/me",
            access_token,
            PROFILE_FIELDS,
            PROFILE_OPTIONAL_FIELDS,
            _ProfileResponse,
        )
        return InstagramProfile.model_validate(profile.model_dump())

    async def recent_media(self, access_token: str, limit: int) -> list[InstagramMedia]:
        """The newest `limit` posts, Reels and carousels (never stories), newest first."""
        page = await self._fields(
            f"{self._graph}/me/media",
            access_token,
            MEDIA_FIELDS,
            MEDIA_OPTIONAL_FIELDS,
            _MediaPage,
            {"limit": min(PAGE_SIZE, limit)},
        )
        media: list[InstagramMedia] = []
        while True:
            media.extend(_media(item) for item in page.data)
            next_url = page.paging.next if page.paging else None
            if len(media) >= limit or next_url is None:
                return media[:limit]
            # The next link already carries the fields and the token
            page = _parse(await self._request("GET", next_url), _MediaPage)

    async def download(self, url: str) -> tuple[bytes, str]:
        response = await self._request("GET", url)
        content_type = response.headers.get("content-type", "").split(";")[0].strip()
        return response.content, content_type

    async def _fields[M: BaseModel](
        self,
        url: str,
        access_token: str,
        fields: tuple[str, ...],
        optional: tuple[str, ...],
        model: type[M],
        params: dict[str, int] | None = None,
    ) -> M:
        """GET with `fields` and `optional`; if Meta rejects that, again without `optional`."""
        base = {**(params or {}), "access_token": access_token}
        try:
            return _parse(
                await self._request(
                    "GET", url, params={**base, "fields": ",".join(fields + optional)}
                ),
                model,
            )
        except InstagramError as exc:
            if exc.status != HTTP_BAD_REQUEST:
                raise
            logger.warning("instagram refused %s, retrying without them: %s", optional, exc)
        return _parse(
            await self._request("GET", url, params={**base, "fields": ",".join(fields)}), model
        )

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


def _media(item: _MediaItem) -> InstagramMedia:
    media = InstagramMedia.model_validate(
        item.model_dump(include=InstagramMedia.model_fields.keys() - {"images"})
    )
    children = (item.children.data if item.children else None) or [item]
    images = [image for child in children if (image := _image(child)) is not None]
    return media.model_copy(update={"images": images})


def _image(item: _MediaChild | _MediaItem) -> InstagramImage | None:
    """The photo itself, or a video's cover; `media_url` is missing on copyrighted media."""
    url = item.thumbnail_url if item.media_type == "VIDEO" else item.media_url
    if not url or not item.id:
        return None
    return InstagramImage(id=item.id, url=url)


def _parse[M: BaseModel](response: httpx.Response, model: type[M]) -> M:
    try:
        body = response.json()
    except ValueError as exc:
        raise InstagramError(f"instagram returned a non-JSON body: {response.text[:200]}") from exc
    try:
        return model.model_validate(body)
    except ValidationError as exc:
        first = exc.errors()[0]
        if not first["loc"]:
            raise InstagramError("instagram returned an unexpected body") from exc
        field = ".".join(str(part) for part in first["loc"])
        raise InstagramError(f"instagram response has no {field}") from exc
