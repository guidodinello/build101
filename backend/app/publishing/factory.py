from app.config import Settings

from .base import PublisherPort
from .mock import MockPublisher
from .zernio import ZernioPublisher


def build_publisher(settings: Settings) -> PublisherPort:
    match settings.publisher:
        case "zernio":
            if not settings.zernio_api_key:
                raise ValueError("PUBLISHER=zernio needs ZERNIO_API_KEY")
            return ZernioPublisher.from_settings(
                api_key=settings.zernio_api_key,
                base_url=settings.zernio_base_url,
            )
        case "mock":
            return MockPublisher()
