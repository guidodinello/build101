import json

import httpx
import pytest

from app.storage import StorageError, SupabaseStorage

SUPABASE_URL = "https://project.supabase.co"
KEY = "service-role-key"


def storage(handler: httpx.MockTransport) -> SupabaseStorage:
    return SupabaseStorage.from_settings(SUPABASE_URL, KEY, transport=handler)


async def test_signed_upload_url_is_absolute_and_carries_its_token() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json={"url": "/object/upload/sign/assets/b1/a1.jpg?token=abc.def"}
        )

    signed = await storage(httpx.MockTransport(handle)).create_signed_upload_url(
        "assets", "b1/a1.jpg"
    )

    assert (
        signed.url == f"{SUPABASE_URL}/storage/v1/object/upload/sign/assets/b1/a1.jpg?token=abc.def"
    )
    assert signed.token == "abc.def"
    assert seen[0].method == "POST"
    assert seen[0].url.path == "/storage/v1/object/upload/sign/assets/b1/a1.jpg"
    assert seen[0].headers["apikey"] == KEY
    assert seen[0].headers["authorization"] == f"Bearer {KEY}"


@pytest.mark.parametrize("status", [400, 404])
async def test_download_of_a_missing_object_is_none(status: int) -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(status, json={"error": "not_found"}))

    assert await storage(transport).download("assets", "b1/a1.jpg") is None


async def test_download_returns_the_bytes() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(200, content=b"jpeg"))

    assert await storage(transport).download("assets", "b1/a1.jpg") == b"jpeg"


async def test_upload_overwrites_with_the_content_type() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"Key": "assets/b1/a1-llm.jpg"})

    await storage(httpx.MockTransport(handle)).upload(
        "assets", "b1/a1-llm.jpg", b"jpeg", "image/jpeg"
    )

    assert seen[0].url.path == "/storage/v1/object/assets/b1/a1-llm.jpg"
    assert seen[0].headers["content-type"] == "image/jpeg"
    assert seen[0].headers["x-upsert"] == "true"
    assert seen[0].content == b"jpeg"


async def test_signed_urls_leave_out_paths_that_failed() -> None:
    seen: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json=[
                {
                    "path": "b1/a1.jpg",
                    "signedURL": "/object/sign/assets/b1/a1.jpg?token=t1",
                    "error": None,
                },
                {
                    "path": "b1/a2.jpg",
                    "signedURL": None,
                    "error": "Either the object does not exist",
                },
            ],
        )

    urls = await storage(httpx.MockTransport(handle)).create_signed_urls(
        "assets", ["b1/a1.jpg", "b1/a2.jpg"], 3600
    )

    assert urls == {"b1/a1.jpg": f"{SUPABASE_URL}/storage/v1/object/sign/assets/b1/a1.jpg?token=t1"}
    assert json.loads(seen[0].content) == {"paths": ["b1/a1.jpg", "b1/a2.jpg"], "expiresIn": 3600}


async def test_no_paths_makes_no_request() -> None:
    def handle(_: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    assert await storage(httpx.MockTransport(handle)).create_signed_urls("assets", [], 3600) == {}


async def test_an_error_status_raises_storage_error() -> None:
    transport = httpx.MockTransport(lambda _: httpx.Response(500, text="boom"))

    with pytest.raises(StorageError, match="500"):
        await storage(transport).create_signed_upload_url("assets", "b1/a1.jpg")


async def test_a_network_error_raises_storage_error() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(StorageError):
        await storage(httpx.MockTransport(handle)).download("assets", "b1/a1.jpg")
