import logging
from typing import Self

import httpx
from pydantic import ValidationError

from .base import RenderedSlide, RendererError, RenderReport, SlideRender

logger = logging.getLogger(__name__)

RENDER_PATH = "/api/render"
REPORT_HEADER = "x-render-report"
# A slide renders in tens of milliseconds; the margin covers a cold start of the Vercel function
REQUEST_TIMEOUT_S = 30.0
ERROR_BODY_CHARS = 300


class TakumiRenderer:
    """RendererPort over the frontend's Takumi route on Vercel (ADR 0029)."""

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

    async def render(self, slide: SlideRender) -> RenderedSlide:
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
        return RenderedSlide(image=response.content, report=report(response.headers))


def report(headers: httpx.Headers) -> RenderReport | None:
    """The renderer's measurements; a missing or unreadable report never fails the slide."""
    raw = headers.get(REPORT_HEADER)
    if raw is None:
        return None
    try:
        return RenderReport.model_validate_json(raw)
    except ValidationError:
        logger.warning("unreadable %s header, ignored", REPORT_HEADER)
        return None
