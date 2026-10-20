import json

import httpx
import pytest

from app.channels.base import Button, ChannelError
from app.channels.kapso import KapsoChannel

BASE_URL = "https://api.kapso.ai/meta/whatsapp/v24.0"
PHONE_NUMBER_ID = "pn-1"
MESSAGES_URL = f"{BASE_URL}/{PHONE_NUMBER_ID}/messages"


def channel_with(handler) -> tuple[KapsoChannel, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    channel = KapsoChannel.from_settings(
        api_key="key-123",
        phone_number_id=PHONE_NUMBER_ID,
        base_url=BASE_URL,
        transport=httpx.MockTransport(record),
    )
    return channel, requests


def sent_ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"messages": [{"id": "wamid.OUT1"}]})


async def test_send_text() -> None:
    channel, requests = channel_with(sent_ok)

    message_id = await channel.send_text("59899000001", "hola")

    assert message_id == "wamid.OUT1"
    [request] = requests
    assert request.method == "POST"
    assert str(request.url) == MESSAGES_URL
    assert request.headers["x-api-key"] == "key-123"
    assert json.loads(request.content) == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "59899000001",
        "type": "text",
        "text": {"body": "hola"},
    }


async def test_send_image_with_caption() -> None:
    channel, requests = channel_with(sent_ok)

    await channel.send_image("59899000001", "https://img.test/a.jpg", caption="1/5")

    assert json.loads(requests[0].content)["image"] == {
        "link": "https://img.test/a.jpg",
        "caption": "1/5",
    }
    assert json.loads(requests[0].content)["type"] == "image"


async def test_send_image_without_caption_omits_it() -> None:
    channel, requests = channel_with(sent_ok)

    await channel.send_image("59899000001", "https://img.test/a.jpg")

    assert json.loads(requests[0].content)["image"] == {"link": "https://img.test/a.jpg"}


async def test_send_buttons_with_image_header() -> None:
    channel, requests = channel_with(sent_ok)

    await channel.send_buttons(
        "59899000001",
        "¿Lo publico?",
        [Button(id="post_approve:1", title="Publicar"), Button(id="post_discard:1", title="Chau")],
        header_image_url="https://img.test/post.jpg",
    )

    assert json.loads(requests[0].content)["interactive"] == {
        "type": "button",
        "header": {"type": "image", "image": {"link": "https://img.test/post.jpg"}},
        "body": {"text": "¿Lo publico?"},
        "action": {
            "buttons": [
                {"type": "reply", "reply": {"id": "post_approve:1", "title": "Publicar"}},
                {"type": "reply", "reply": {"id": "post_discard:1", "title": "Chau"}},
            ]
        },
    }


async def test_send_buttons_with_video_header() -> None:
    channel, requests = channel_with(sent_ok)

    await channel.send_buttons(
        "59899000001",
        "Reel",
        [Button(id="a", title="Ok")],
        header_video_url="https://vid.test/r.mp4",
    )

    header = json.loads(requests[0].content)["interactive"]["header"]
    assert header == {"type": "video", "video": {"link": "https://vid.test/r.mp4"}}


async def test_send_buttons_validates_count_and_headers() -> None:
    channel, requests = channel_with(sent_ok)
    four = [Button(id=str(n), title="x") for n in range(4)]

    with pytest.raises(ValueError, match="1 to 3"):
        await channel.send_buttons("to", "body", four)
    with pytest.raises(ValueError, match="1 to 3"):
        await channel.send_buttons("to", "body", [])
    with pytest.raises(ValueError, match="at most one header"):
        await channel.send_buttons(
            "to", "body", four[:1], header_image_url="https://a", header_video_url="https://b"
        )
    assert requests == []


def test_button_title_is_limited_to_20_chars() -> None:
    with pytest.raises(ValueError):
        Button(id="a", title="x" * 21)


async def test_mark_read() -> None:
    channel, requests = channel_with(lambda request: httpx.Response(200, json={"success": True}))

    await channel.mark_read("wamid.IN1")

    assert str(requests[0].url) == MESSAGES_URL
    assert json.loads(requests[0].content) == {
        "messaging_product": "whatsapp",
        "status": "read",
        "message_id": "wamid.IN1",
    }


async def test_mark_read_with_typing_indicator() -> None:
    channel, requests = channel_with(lambda request: httpx.Response(200, json={"success": True}))

    await channel.mark_read("wamid.IN1", typing=True)

    assert json.loads(requests[0].content)["typing_indicator"] == {"type": "text"}


async def test_download_media_resolves_the_id_then_fetches_without_the_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.kapso.ai":
            return httpx.Response(
                200,
                json={
                    "download_url": "https://files.test/dl/abc?token=t",
                    "mime_type": "image/jpeg",
                    "file_size": "3",
                },
            )
        return httpx.Response(200, content=b"\xff\xd8\xff", headers={"content-type": "other"})

    channel, requests = channel_with(handler)

    data, mime = await channel.download_media("media-9")

    assert (data, mime) == (b"\xff\xd8\xff", "image/jpeg")
    resolve, download = requests
    assert str(resolve.url) == f"{BASE_URL}/media-9?phone_number_id={PHONE_NUMBER_ID}"
    assert resolve.headers["x-api-key"] == "key-123"
    assert str(download.url) == "https://files.test/dl/abc?token=t"
    assert "x-api-key" not in download.headers


async def test_download_media_without_download_url_fails() -> None:
    channel, _ = channel_with(lambda request: httpx.Response(200, json={"id": "media-9"}))

    with pytest.raises(ChannelError, match="no download_url"):
        await channel.download_media("media-9")


async def test_api_errors_raise_channel_error() -> None:
    channel, _ = channel_with(lambda request: httpx.Response(400, text="bad recipient"))

    with pytest.raises(ChannelError, match="kapso 400: bad recipient"):
        await channel.send_text("59899000001", "hola")


async def test_network_errors_raise_channel_error() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    channel, _ = channel_with(boom)

    with pytest.raises(ChannelError, match="request failed"):
        await channel.send_text("59899000001", "hola")


async def test_response_without_message_id_raises() -> None:
    channel, _ = channel_with(lambda request: httpx.Response(200, json={}))

    with pytest.raises(ChannelError, match="no message id"):
        await channel.send_text("59899000001", "hola")


async def test_send_text_converts_markdown_bold() -> None:
    channel, requests = channel_with(sent_ok)

    await channel.send_text("59899000001", "**Hola** https://www.instagram.com/p/AbC__d/")

    assert json.loads(requests[0].content)["text"]["body"] == (
        "*Hola* https://www.instagram.com/p/AbC__d/"
    )


async def test_send_image_converts_markdown_bold_in_the_caption() -> None:
    channel, requests = channel_with(sent_ok)

    await channel.send_image("59899000001", "https://img.test/a.jpg", caption="**1/5** __listo__")

    assert json.loads(requests[0].content)["image"]["caption"] == "*1/5* _listo_"


async def test_send_buttons_converts_markdown_bold_in_the_body() -> None:
    channel, requests = channel_with(sent_ok)

    await channel.send_buttons("59899000001", "**¿Lo subo?**", [Button(id="ok", title="Sí")])

    assert json.loads(requests[0].content)["interactive"]["body"] == {"text": "*¿Lo subo?*"}


async def test_download_media_ignores_a_non_string_mime_type() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "dl.test":
            return httpx.Response(200, content=b"x", headers={"content-type": "image/png"})
        return httpx.Response(200, json={"download_url": "https://dl.test/f", "mime_type": 5})

    channel, _ = channel_with(handler)

    assert await channel.download_media("media-9") == (b"x", "image/png")
