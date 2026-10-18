import pytest

from app.config import Settings
from app.publishing.factory import build_publisher
from app.publishing.mock import MockPublisher
from app.publishing.zernio import ZernioPublisher


def test_the_default_publisher_is_the_mock() -> None:
    assert Settings(_env_file=None).publisher == "mock"


def test_mock_switch() -> None:
    assert isinstance(build_publisher(Settings(publisher="mock")), MockPublisher)


def test_zernio_without_a_key_fails_fast() -> None:
    with pytest.raises(ValueError, match="ZERNIO_API_KEY"):
        build_publisher(Settings(_env_file=None, publisher="zernio", zernio_api_key=None))


def test_zernio_switch() -> None:
    settings = Settings(publisher="zernio", zernio_api_key="sk_test")

    assert isinstance(build_publisher(settings), ZernioPublisher)
