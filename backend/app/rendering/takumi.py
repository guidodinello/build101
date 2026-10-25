import asyncio
import logging
import random
from typing import Any, Self

import httpx

from .base import RendererError, SlideRender

logger = logging.getLogger(__name__)

RENDER_PATH = "/api/render"
# A slide renders in tens of milliseconds; the margin covers a cold start of the Vercel function
REQUEST_TIMEOUT_S = 30.0
ERROR_BODY_CHARS = 300
# A cold start or a 5xx is retried once after a pause in this range, so it doesn't throw away
# scenes already generated and paid for
RETRY_PAUSE_S = (0.5, 2.0)


class RendererUnavailable(RendererError):
    """A 5xx or a timeout: worth one more try."""


class TakumiRenderer:
    """RendererPort over the frontend's Takumi route on Vercel (ADR 0029)."""

    def __init__(
        self, client: httpx.AsyncClient, retry_pause: tuple[float, float] = RETRY_PAUSE_S
    ) -> None:
        self._client = client
        self._retry_pause = retry_pause

    @classmethod
    def from_settings(
        cls,
        base_url: str,
        secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
        retry_pause: tuple[float, float] = RETRY_PAUSE_S,
    ) -> Self:
        client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {secret}"},
            timeout=REQUEST_TIMEOUT_S,
            transport=transport,
        )
        return cls(client, retry_pause)

    async def render(self, slide: SlideRender) -> bytes:
        body = slide.model_dump(mode="json")
        try:
            return await self._post(body)
        except RendererUnavailable as exc:
            logger.warning("slide %d: %s, retrying once", slide.index, exc)
            await asyncio.sleep(random.uniform(*self._retry_pause))
            return await self._post(body)

    async def _post(self, body: dict[str, Any]) -> bytes:
        try:
            response = await self._client.post(RENDER_PATH, json=body)
        except httpx.TimeoutException as exc:
            raise RendererUnavailable(f"renderer timed out: {exc!r}") from exc
        except httpx.HTTPError as exc:
            raise RendererError(f"renderer unreachable: {exc!r}") from exc
        if response.status_code != httpx.codes.OK:
            error = RendererUnavailable if response.is_server_error else RendererError
            raise error(
                f"renderer answered {response.status_code}: {response.text[:ERROR_BODY_CHARS]}"
            )
        if response.headers.get("content-type") != "image/jpeg":
            raise RendererError(f"renderer answered {response.headers.get('content-type')}")
        return response.content
