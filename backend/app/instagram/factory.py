from functools import cache

from app.config import Settings, get_settings

from .base import InstagramPort
from .meta import MetaInstagram
from .mock import MockInstagram


def build_instagram(settings: Settings) -> InstagramPort:
    match settings.instagram:
        case "meta":
            if not settings.instagram_app_id or not settings.instagram_app_secret:
                raise ValueError("INSTAGRAM=meta needs INSTAGRAM_APP_ID and INSTAGRAM_APP_SECRET")
            return MetaInstagram.from_settings(
                app_id=settings.instagram_app_id,
                app_secret=settings.instagram_app_secret,
                graph_version=settings.instagram_graph_version,
            )
        case "mock":
            return MockInstagram()
        case "off":
            raise ValueError("INSTAGRAM=off has no adapter: the connect and the import are off")


@cache
def get_instagram() -> InstagramPort:
    return build_instagram(get_settings())
