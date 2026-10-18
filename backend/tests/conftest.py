import hashlib
import hmac
import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.carousel.schemas import CarouselBrief, CarouselCopy
from app.config import Settings, get_settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def ignore_local_env_file(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests see only the settings they pass; live tests read backend/.env for the keys."""
    if request.node.get_closest_marker("live") is None:
        monkeypatch.setitem(Settings.model_config, "env_file", None)
    get_settings.cache_clear()


def make_image(size: tuple[int, int], color: str = "sienna", format: str = "JPEG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=format)
    return buffer.getvalue()


@pytest.fixture
def carousel_spec() -> tuple[CarouselCopy, CarouselBrief]:
    spec = json.loads((FIXTURES / "carousel_spec.json").read_text())
    return CarouselCopy.model_validate(spec["copy"]), CarouselBrief.model_validate(spec["brief"])


def sign(raw: bytes, secret: str) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
