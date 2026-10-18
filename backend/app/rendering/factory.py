import logging

from app.config import Settings

from .base import RendererPort
from .mock import MockRenderer
from .takumi import TakumiRenderer

logger = logging.getLogger(__name__)


def build_renderer(settings: Settings) -> RendererPort:
    match settings.renderer:
        case "takumi":
            if not settings.renderer_url or not settings.renderer_secret:
                raise ValueError("RENDERER=takumi needs RENDERER_URL and RENDERER_SECRET")
            return TakumiRenderer.from_settings(settings.renderer_url, settings.renderer_secret)
        case "mock":
            logger.warning("RENDERER=mock: designed slides go out as bare scenes, without text")
            return MockRenderer()
