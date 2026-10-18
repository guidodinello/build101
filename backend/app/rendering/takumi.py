from typing import Self

import httpx

from .base import RendererError, SlideRender

RENDER_PATH = "/api/render"
# A slide renders in tens of milliseconds; the margin covers a cold start of the Vercel function
REQUEST_TIMEOUT_S = 30.0
ERROR_BODY_CHARS = 300


class TakumiRenderer:
    """RendererPort over the frontend's Takumi route on Vercel (ADR 0028)."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    @classmethod
    def from_settings(
        cls, base_url: str, secret: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> Self:
        client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {secret}"},
            timeout=REQUEST_TIMEOUT_S,
            transport=transport,
        )
        return cls(client)

    async def render(self, slide: SlideRender) -> bytes:
        try:
            response = await self._client.post(RENDER_PATH, json=slide.model_dump(mode="json"))
        except httpx.HTTPError as exc:
            raise RendererError(f"renderer unreachable: {exc!r}") from exc
        if response.status_code != httpx.codes.OK:
            raise RendererError(
                f"renderer answered {response.status_code}: {response.text[:ERROR_BODY_CHARS]}"
            )
        if response.headers.get("content-type") != "image/jpeg":
            raise RendererError(f"renderer answered {response.headers.get('content-type')}")
        return response.content
