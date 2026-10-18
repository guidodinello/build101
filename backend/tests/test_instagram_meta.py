from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from app.instagram.base import InstagramError
from app.instagram.meta import MetaInstagram

REDIRECT_URI = "https://api.test/oauth/instagram/callback"
Handler = Callable[[httpx.Request], httpx.Response]


def instagram(handler: Handler) -> tuple[MetaInstagram, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    transport = httpx.MockTransport(record)
    return MetaInstagram.from_settings("app-id", "app-secret", "v24.0", transport), requests


def fields(request: httpx.Request) -> list[str]:
    return request.url.params.get("fields", "").split(",")


def test_authorize_url_asks_only_for_read_access() -> None:
    client, _ = instagram(lambda request: httpx.Response(500))

    url = urlsplit(client.authorize_url(REDIRECT_URI, "the-state"))

    query = parse_qs(url.query)
    assert f"{url.netloc}{url.path}" == "www.instagram.com/oauth/authorize"
    assert query == {
        "client_id": ["app-id"],
        "redirect_uri": [REDIRECT_URI],
        "response_type": ["code"],
        "scope": ["instagram_business_basic"],
        "state": ["the-state"],
    }


@pytest.mark.parametrize(
    "short_body",
    [
        {"access_token": "short", "user_id": 17841},
        {"data": [{"access_token": "short", "user_id": "17841", "permissions": "x"}]},
    ],
)
async def test_code_is_exchanged_for_a_long_lived_token(short_body: dict[str, Any]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.instagram.com":
            return httpx.Response(200, json=short_body)
        return httpx.Response(200, json={"access_token": "long", "expires_in": 5184000})

    client, requests = instagram(handler)

    token = await client.exchange_code("the-code", REDIRECT_URI)

    assert (token.access_token, token.user_id) == ("long", "17841")
    assert token.expires_at is not None
    form = parse_qs(requests[0].content.decode())
    assert form["code"] == ["the-code"]
    assert form["redirect_uri"] == [REDIRECT_URI]
    assert requests[1].url.params["grant_type"] == "ig_exchange_token"
    assert requests[1].url.params["access_token"] == "short"


async def test_profile_is_read_again_without_bio_when_meta_refuses_it() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "biography" in fields(request):
            return httpx.Response(400, json={"error": {"code": 100}})
        return httpx.Response(200, json={"user_id": "1", "username": "katei", "media_count": 9})

    client, requests = instagram(handler)

    profile = await client.profile("token")

    assert (profile.username, profile.media_count, profile.biography) == ("katei", 9, None)
    assert len(requests) == 2


async def test_other_errors_are_raised() -> None:
    client, _ = instagram(lambda request: httpx.Response(500, text="down"))

    with pytest.raises(InstagramError) as raised:
        await client.profile("token")

    assert raised.value.status == 500


async def test_media_follows_pages_up_to_the_limit_with_every_image() -> None:
    first = {
        "data": [
            {"id": "1", "media_type": "IMAGE", "media_url": "https://cdn/1.jpg", "caption": "a"},
            {
                "id": "2",
                "media_type": "CAROUSEL_ALBUM",
                "media_url": "https://cdn/2a.jpg",
                "children": {
                    "data": [
                        {"id": "2a", "media_type": "IMAGE", "media_url": "https://cdn/2a.jpg"},
                        {"id": "2b", "media_type": "VIDEO", "thumbnail_url": "https://cdn/2b.jpg"},
                    ]
                },
            },
        ],
        "paging": {"next": "https://graph.instagram.com/v24.0/me/media?after=x"},
    }
    second = {
        "data": [
            {"id": "3", "media_type": "VIDEO", "thumbnail_url": "https://cdn/3.jpg"},
            {"id": "4", "media_type": "VIDEO"},  # copyrighted audio: no media_url, no cover
        ],
        "paging": {"next": "https://graph.instagram.com/v24.0/me/media?after=y"},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=second if "after" in request.url.params else first)

    client, requests = instagram(handler)

    media = await client.recent_media("token", limit=4)

    assert [post.id for post in media] == ["1", "2", "3", "4"]
    assert [[image.id for image in post.images] for post in media] == [
        ["1"],
        ["2a", "2b"],
        ["3"],
        [],
    ]
    assert media[1].images[1].url == "https://cdn/2b.jpg"
    assert "caption" in fields(requests[0])
    assert len(requests) == 2


async def test_download_returns_the_bytes_and_their_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"jpeg", headers={"content-type": "image/jpeg; q=1"})

    client, _ = instagram(handler)

    assert await client.download("https://cdn/1.jpg") == (b"jpeg", "image/jpeg")


async def test_a_body_that_is_not_json_is_an_error() -> None:
    client, _ = instagram(lambda request: httpx.Response(200, text="<html>"))

    with pytest.raises(InstagramError):
        await client.profile("token")
