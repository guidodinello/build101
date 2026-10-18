import hashlib
import hmac
import json
import os
import re
from collections.abc import AsyncIterator
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.carousel.schemas import CarouselBrief, CarouselCopy
from app.config import Settings, get_settings
from app.db.session import create_engine

FIXTURES = Path(__file__).parent / "fixtures"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
MIGRATIONS = sorted((Path(__file__).parents[1] / "migrations" / "versions").glob("*.sql"))

requires_db = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="set TEST_DATABASE_URL to a Postgres the tests can wipe"
)


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


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """A fresh schema per test, from the migrations' SQL in order."""
    assert TEST_DATABASE_URL
    engine = create_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("drop schema public cascade"))
        await connection.execute(text("create schema public"))
        for migration in MIGRATIONS:
            for statement in re.split(r";\s*$", migration.read_text(), flags=re.MULTILINE):
                if statement.strip():
                    await connection.exec_driver_sql(statement)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()
