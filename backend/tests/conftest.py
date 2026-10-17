import json
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.carousel.schemas import CarouselBrief, CarouselCopy

FIXTURES = Path(__file__).parent / "fixtures"


def make_image(size: tuple[int, int], color: str = "sienna", format: str = "JPEG") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format=format)
    return buffer.getvalue()


@pytest.fixture
def carousel_spec() -> tuple[CarouselCopy, CarouselBrief]:
    spec = json.loads((FIXTURES / "carousel_spec.json").read_text())
    return CarouselCopy.model_validate(spec["copy"]), CarouselBrief.model_validate(spec["brief"])
