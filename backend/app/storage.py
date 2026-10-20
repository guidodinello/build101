from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import cache
from typing import Any, Protocol, Self
from urllib.parse import parse_qs, urlparse

import httpx

from app.config import get_settings

ASSETS_BUCKET = "assets"
REQUEST_TIMEOUT_S = 30.0
HTTP_NOT_FOUND = 404
HTTP_BAD_REQUEST = 400
ERROR_BODY_CHARS = 300
MAX_REMOVE_PATHS = 1000
LIST_PAGE_SIZE = 100
# Supabase signed upload URLs last 2 h: an object older than this can no longer be PUT again.
SIGNED_UPLOAD_URL_TTL = timedelta(hours=2)


class StorageError(Exception):
    pass


class ObjectTooLarge(StorageError):
    """The object is bigger than the `max_bytes` the caller allowed."""


@dataclass(frozen=True, slots=True)
class SignedUpload:
    url: str
    token: str


@dataclass(frozen=True, slots=True)
class StoredObject:
    name: str  # relative to the listed prefix
    created_at: datetime


class StoragePort(Protocol):
    async def create_signed_upload_url(self, bucket: str, path: str) -> SignedUpload: ...

    async def download(
        self, bucket: str, path: str, *, max_bytes: int | None = None
    ) -> bytes | None:
        """The object's bytes, or None when it doesn't exist. Past `max_bytes` it stops reading
        and raises ObjectTooLarge, so an oversized object is never held whole in memory."""
        ...

    async def upload(self, bucket: str, path: str, data: bytes, content_type: str) -> None: ...

    async def create_signed_urls(
        self, bucket: str, paths: list[str], expires_in_s: int
    ) -> dict[str, str]:
        """Signed read URLs by path; paths that don't exist are left out."""
        ...

    async def remove(self, bucket: str, paths: list[str]) -> None:
        """Delete the objects; a path that doesn't exist is not an error."""
        ...

    async def list_objects(self, bucket: str, prefix: str) -> list[StoredObject]:
        """The objects directly under `prefix` (a folder, no trailing slash)."""
        ...


class SupabaseStorage:
    """StoragePort over Supabase Storage's REST API (ADR 0003), with the service role key.

    Same endpoints as the official `storage3` client; written on httpx like the other adapters.
    """

    def __init__(self, client: httpx.AsyncClient, storage_url: str) -> None:
        self._client = client
        self._storage_url = storage_url

    @classmethod
    def from_settings(
        cls,
        supabase_url: str,
        service_role_key: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> Self:
        storage_url = f"{supabase_url.rstrip('/')}/storage/v1"
        client = httpx.AsyncClient(
            base_url=storage_url,
            headers={"apikey": service_role_key, "Authorization": f"Bearer {service_role_key}"},
            timeout=REQUEST_TIMEOUT_S,
            transport=transport,
        )
        return cls(client, storage_url)

    async def create_signed_upload_url(self, bucket: str, path: str) -> SignedUpload:
        response = await self._request("POST", f"/object/upload/sign/{bucket}/{path}")
        signed = f"{self._storage_url}{response.json()['url']}"
        token = parse_qs(urlparse(signed).query).get("token")
        if not token:
            raise StorageError("supabase returned a signed upload url without a token")
        return SignedUpload(url=signed, token=token[0])

    async def download(
        self, bucket: str, path: str, *, max_bytes: int | None = None
    ) -> bytes | None:
        try:
            # Identity: the byte count must be the object's own, not what a compressed body
            # expands to; a response that is encoded anyway is refused in _read_capped.
            async with self._client.stream(
                "GET", f"/object/{bucket}/{path}", headers={"Accept-Encoding": "identity"}
            ) as response:
                # Storage answers a missing object with 400 or 404 depending on the version.
                if response.status_code in (HTTP_NOT_FOUND, HTTP_BAD_REQUEST):
                    return None
                if response.is_error:
                    await response.aread()
                    _raise_for_status(response)
                return await _read_capped(response, max_bytes)
        except httpx.HTTPError as exc:
            raise StorageError(f"supabase download failed: {exc!r}") from exc

    async def upload(self, bucket: str, path: str, data: bytes, content_type: str) -> None:
        await self._request(
            "POST",
            f"/object/{bucket}/{path}",
            content=data,
            headers={"Content-Type": content_type, "x-upsert": "true"},
        )

    async def create_signed_urls(
        self, bucket: str, paths: list[str], expires_in_s: int
    ) -> dict[str, str]:
        if not paths:
            return {}
        response = await self._request(
            "POST", f"/object/sign/{bucket}", json={"paths": paths, "expiresIn": expires_in_s}
        )
        return {
            item["path"]: f"{self._storage_url}{item['signedURL']}"
            for item in response.json()
            if item.get("signedURL") and not item.get("error")
        }

    async def remove(self, bucket: str, paths: list[str]) -> None:
        # DELETE /object/{bucket} with {"prefixes": [...]}, up to 1000 paths per call: what
        # storage-js's `remove` sends (src/packages/StorageFileApi.ts, src/lib/fetch.ts) and
        # https://supabase.com/docs/guides/storage/management/delete-objects documents.
        for start in range(0, len(paths), MAX_REMOVE_PATHS):
            await self._request(
                "DELETE",
                f"/object/{bucket}",
                json={"prefixes": paths[start : start + MAX_REMOVE_PATHS]},
            )

    async def list_objects(self, bucket: str, prefix: str) -> list[StoredObject]:
        # POST /object/list/{bucket} with {prefix, limit, offset, sortBy}: what storage-js's `list`
        # sends (src/packages/StorageFileApi.ts), items shaped like its `FileObject`
        # (src/lib/types.ts). Sub-folders come back without an `id`; they are skipped.
        objects: list[StoredObject] = []
        offset = 0
        while True:
            response = await self._request(
                "POST",
                f"/object/list/{bucket}",
                json={
                    "prefix": prefix,
                    "limit": LIST_PAGE_SIZE,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )
            page = response.json()
            objects.extend(
                StoredObject(item["name"], datetime.fromisoformat(item["created_at"]))
                for item in page
                if item.get("id") and item.get("created_at")
            )
            if len(page) < LIST_PAGE_SIZE:
                return objects
            offset += LIST_PAGE_SIZE

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        try:
            response = await self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise StorageError(f"supabase {method} {url} failed: {exc!r}") from exc
        _raise_for_status(response)
        return response


async def _read_capped(response: httpx.Response, max_bytes: int | None) -> bytes:
    """The body, read chunk by chunk; leaving early closes the connection with the rest unread."""
    encoding = response.headers.get("content-encoding", "identity").lower()
    if encoding != "identity":
        raise StorageError(f"supabase answered with content-encoding {encoding!r}")
    declared = response.headers.get("content-length", "")
    if max_bytes is not None and declared.isdigit() and int(declared) > max_bytes:
        raise ObjectTooLarge(f"object is {declared} bytes, over {max_bytes}")
    chunks: list[bytes] = []
    total = 0
    async for chunk in response.aiter_bytes():
        total += len(chunk)
        if max_bytes is not None and total > max_bytes:
            raise ObjectTooLarge(f"object is over {max_bytes} bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _raise_for_status(response: httpx.Response) -> None:
    if response.is_error:
        raise StorageError(
            f"supabase storage {response.status_code}: {response.text[:ERROR_BODY_CHARS]}"
        )


@cache
def get_storage() -> StoragePort:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are not set")
    return SupabaseStorage.from_settings(settings.supabase_url, settings.supabase_service_role_key)
