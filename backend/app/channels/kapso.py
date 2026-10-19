from typing import Any, Self

import httpx
from pydantic import BaseModel, Field, ValidationError

from .base import Button, ChannelError
from .whatsapp_format import to_whatsapp

REQUEST_TIMEOUT_S = 30.0
MAX_BUTTONS = 3


# Kapso's answers, as far as we read them; unknown fields are ignored
class _MediaInfo(BaseModel):
    download_url: str | None = None
    mime_type: str | None = None


class _SentMessage(BaseModel):
    id: str


class _SendResponse(BaseModel):
    messages: list[_SentMessage] = Field(min_length=1)


class KapsoChannel:
    """ChannelPort over Kapso's Meta-compatible WhatsApp API.

    `client` talks to the API (base URL and X-API-Key set). `download_client` fetches the
    short-lived download URLs and carries no key: those URLs embed their own token.
    """

    def __init__(
        self,
        client: httpx.AsyncClient,
        download_client: httpx.AsyncClient,
        phone_number_id: str,
    ) -> None:
        self._client = client
        self._download_client = download_client
        self._phone_number_id = phone_number_id

    @classmethod
    def from_settings(
        cls,
        api_key: str,
        phone_number_id: str,
        base_url: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> Self:
        client = httpx.AsyncClient(
            base_url=base_url,
            headers={"X-API-Key": api_key},
            timeout=REQUEST_TIMEOUT_S,
            transport=transport,
        )
        download_client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S, transport=transport)
        return cls(client, download_client, phone_number_id)

    async def aclose(self) -> None:
        await self._client.aclose()
        await self._download_client.aclose()

    async def send_text(self, to: str, text: str) -> str:
        return await self._send(to, {"type": "text", "text": {"body": to_whatsapp(text)}})

    async def send_image(self, to: str, image_url: str, caption: str | None = None) -> str:
        image: dict[str, Any] = {"link": image_url}
        if caption:
            image["caption"] = to_whatsapp(caption)
        return await self._send(to, {"type": "image", "image": image})

    async def send_buttons(
        self,
        to: str,
        body: str,
        buttons: list[Button],
        header_image_url: str | None = None,
        header_video_url: str | None = None,
    ) -> str:
        if not 1 <= len(buttons) <= MAX_BUTTONS:
            raise ValueError(f"send_buttons takes 1 to {MAX_BUTTONS} buttons, got {len(buttons)}")
        if header_image_url and header_video_url:
            raise ValueError("send_buttons takes at most one header (image or video)")
        interactive: dict[str, Any] = {
            "type": "button",
            "body": {"text": to_whatsapp(body)},
            "action": {
                "buttons": [
                    {"type": "reply", "reply": {"id": b.id, "title": b.title}} for b in buttons
                ]
            },
        }
        if header_image_url:
            interactive["header"] = {"type": "image", "image": {"link": header_image_url}}
        elif header_video_url:
            interactive["header"] = {"type": "video", "video": {"link": header_video_url}}
        return await self._send(to, {"type": "interactive", "interactive": interactive})

    async def mark_read(self, message_id: str, typing: bool = False) -> None:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        if typing:
            payload["typing_indicator"] = {"type": "text"}
        await self._post_messages(payload)

    async def download_media(self, media_id: str) -> tuple[bytes, str]:
        return await self._fetch_media(media_id)

    async def _fetch_media(self, media_id: str) -> tuple[bytes, str]:
        """Kapso's documented two steps: resolve the media id, then fetch its download_url."""
        info_response = await self._request(
            self._client,
            "GET",
            f"/{media_id}",
            params={"phone_number_id": self._phone_number_id},
        )
        info = _parse(info_response, _MediaInfo, f"kapso media {media_id} has no download_url")
        if not info.download_url:
            raise ChannelError(f"kapso media {media_id} has no download_url")
        response = await self._request(self._download_client, "GET", info.download_url)
        return response.content, info.mime_type or response.headers.get("content-type", "")

    async def _send(self, to: str, message: dict[str, Any]) -> str:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            **message,
        }
        response = await self._post_messages(payload)
        sent = _parse(response, _SendResponse, "kapso send response has no message id")
        return sent.messages[0].id

    async def _post_messages(self, payload: dict[str, Any]) -> httpx.Response:
        return await self._request(
            self._client, "POST", f"/{self._phone_number_id}/messages", json=payload
        )

    @staticmethod
    async def _request(
        client: httpx.AsyncClient, method: str, url: str, **kwargs: Any
    ) -> httpx.Response:
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise ChannelError(f"kapso request failed: {exc!r}") from exc
        if response.is_error:
            raise ChannelError(f"kapso {response.status_code}: {response.text[:300]}")
        return response


def _parse[M: BaseModel](response: httpx.Response, model: type[M], error: str) -> M:
    try:
        return model.model_validate_json(response.content)
    except ValidationError as exc:
        raise ChannelError(error) from exc
