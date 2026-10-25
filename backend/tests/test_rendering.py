import base64
import json

import httpx
import pytest

from app.carousel.generator import GeneratedSlide
from app.carousel.schemas import CarouselBrief, CarouselCopy
from app.config import Settings
from app.media.images import image_mime
from app.rendering.base import (
    MAX_BRAND_NAME,
    BrandColors,
    RendererError,
    SlideRender,
    render_brand,
)
from app.rendering.factory import build_renderer
from app.rendering.mock import MockRenderer
from app.rendering.slides import render_slides
from app.rendering.takumi import TakumiRenderer
from tests.conftest import make_image
from tests.fakes import brand_brain

SECRET = "render-secret"
JPEG = make_image((1080, 1350))


def slide_render(**changes: object) -> SlideRender:
    fields = {
        "family": "editorial",
        "index": 1,
        "count": 3,
        "role": "cover",
        "kicker": "Guía",
        "headline": "Tu comedor, a medida",
        "body": None,
        "image": "data:image/jpeg;base64,AAAA",
        "logo": None,
        "brand": render_brand(None),
    }
    return SlideRender.model_validate(fields | changes)


def renderer(handler: httpx.MockTransport) -> TakumiRenderer:
    return TakumiRenderer.from_settings(
        "https://front.test/", SECRET, transport=handler, retry_pause=(0, 0)
    )


async def test_takumi_posts_the_slide_with_the_secret_and_returns_the_jpeg() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})

    image = await renderer(httpx.MockTransport(handle)).render(slide_render())

    assert image == JPEG
    [request] = requests
    assert str(request.url) == "https://front.test/api/render"
    assert request.headers["authorization"] == f"Bearer {SECRET}"
    body = json.loads(request.content)
    assert body["headline"] == "Tu comedor, a medida"
    assert body["brand"]["colors"] == BrandColors().model_dump()


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(400, json={"error": "invalid_spec", "detail": "headline too long"}),
        httpx.Response(200, json={"ok": True}),
    ],
)
async def test_takumi_fails_on_anything_but_a_jpeg(response: httpx.Response) -> None:
    with pytest.raises(RendererError):
        await renderer(httpx.MockTransport(lambda request: response)).render(slide_render())


@pytest.mark.parametrize(
    "failure",
    [httpx.Response(503, text="cold start"), httpx.ReadTimeout("slow")],
    ids=["5xx", "timeout"],
)
async def test_takumi_retries_a_5xx_or_a_timeout_once(
    failure: httpx.Response | httpx.TimeoutException,
) -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if len(requests) == 1:
            if isinstance(failure, Exception):
                raise failure
            return failure
        return httpx.Response(200, content=JPEG, headers={"content-type": "image/jpeg"})

    assert await renderer(httpx.MockTransport(handle)).render(slide_render()) == JPEG
    assert len(requests) == 2


async def test_takumi_gives_up_after_a_second_5xx() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500)

    with pytest.raises(RendererError, match="500"):
        await renderer(httpx.MockTransport(handle)).render(slide_render())
    assert len(requests) == 2


async def test_takumi_doesnt_retry_a_4xx() -> None:
    requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(401)

    with pytest.raises(RendererError, match="401"):
        await renderer(httpx.MockTransport(handle)).render(slide_render())
    assert len(requests) == 1


async def test_takumi_fails_when_the_frontend_is_unreachable() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with pytest.raises(RendererError, match="unreachable"):
        await renderer(httpx.MockTransport(handle)).render(slide_render())


def test_brand_tokens_take_the_brand_brain_and_keep_defaults_for_bad_colors() -> None:
    brand = brand_brain()
    brand.visual_identity.accent_color = "terracota"

    tokens = render_brand(brand)

    assert tokens.name == "Katei"
    assert tokens.colors.primary == "#111111"
    assert tokens.colors.accent == BrandColors().accent


def test_brand_tokens_drop_a_color_with_a_trailing_newline_and_cut_a_long_name() -> None:
    brand = brand_brain(business_name="Muebles " * 20)
    brand.visual_identity.primary_color = "#C8833B\n"

    tokens = render_brand(brand)

    assert tokens.colors.primary == BrandColors().primary
    assert tokens.name is not None and len(tokens.name) <= MAX_BRAND_NAME


def scenes(count: int) -> list[GeneratedSlide]:
    return [
        GeneratedSlide(
            index=n, image=JPEG, prompt="", provider="fake", model=None, usage={}, attempts=1
        )
        for n in range(1, count + 1)
    ]


async def test_render_slides_sends_each_slide_with_its_scene_and_the_prepared_logo(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    mock = MockRenderer()
    logo = make_image((300, 120), color="white", format="PNG")

    images = await render_slides(mock, copy, brief, scenes(4), brand_brain(), logo)

    assert images == [JPEG] * 4
    assert [(s.index, s.count, s.role) for s in mock.slides] == [
        (1, 4, "cover"),
        (2, 4, "content"),
        (3, 4, "content"),
        (4, 4, "cta"),
    ]
    logo_render = mock.slides[0].logo
    assert logo_render is not None and logo_render.tone == "light"
    assert image_mime(base64.b64decode(logo_render.src.split(",", 1)[1])) == "image/png"


async def test_a_one_slide_panorama_renders_as_editorial(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec
    copy = copy.model_copy(update={"slides": copy.slides[:1]})
    brief = brief.model_copy(update={"family": "panorama"})
    mock = MockRenderer()

    await render_slides(mock, copy, brief, scenes(1), None, None)

    assert mock.slides[0].family == "editorial"


async def test_render_slides_needs_one_scene_per_slide(
    carousel_spec: tuple[CarouselCopy, CarouselBrief],
) -> None:
    copy, brief = carousel_spec

    with pytest.raises(ValueError, match="one scene per slide"):
        await render_slides(MockRenderer(), copy, brief, scenes(3), None, None)


def test_the_default_renderer_is_the_mock() -> None:
    settings = Settings(_env_file=None)

    assert settings.renderer == "mock"
    assert isinstance(build_renderer(settings), MockRenderer)


def test_takumi_without_url_or_secret_fails_fast() -> None:
    with pytest.raises(ValueError, match="RENDERER_URL and RENDERER_SECRET"):
        build_renderer(Settings(_env_file=None, renderer="takumi", renderer_url="https://x"))


def test_takumi_switch() -> None:
    settings = Settings(
        _env_file=None, renderer="takumi", renderer_url="https://x", renderer_secret=SECRET
    )

    assert isinstance(build_renderer(settings), TakumiRenderer)
