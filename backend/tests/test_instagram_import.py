import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any, cast
from urllib.parse import urlsplit

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.instagram import DEV_STATE_SECRET
from app.config import Settings, get_settings
from app.db.models import BrandAsset, Business, Job, MagicLink, SocialAccount
from app.db.session import get_session
from app.instagram.base import InstagramError, InstagramImage, InstagramMedia, InstagramProfile
from app.instagram.factory import get_instagram
from app.instagram.mock import MockInstagram
from app.instagram.oauth_state import sign_state
from app.jobs.instagram import import_instagram_job
from app.jobs.runner import JobContext
from app.main import app
from app.storage import get_storage
from tests.conftest import requires_db
from tests.fakes import FakeChannel, FakeStorage, SequenceModel
from tests.test_onboarding_api import new_link, upload

pytestmark = requires_db

FRONTEND = "https://app.test"


class BrokenDownloads(MockInstagram):
    """Every image of the second post fails to download."""

    async def download(self, url: str) -> tuple[bytes, str]:
        if url.endswith("olivedrab"):
            raise InstagramError("403 from the CDN", status=403)
        return await super().download(url)


class Carousel(MockInstagram):
    async def recent_media(self, access_token: str, limit: int) -> list[InstagramMedia]:
        slides = [InstagramImage(id=f"slide-{i}", url="mock://tan") for i in range(5)]
        return [InstagramMedia(id="album", media_type="CAROUSEL_ALBUM", images=slides)]


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
async def client(
    sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> AsyncIterator[httpx.AsyncClient]:
    async def session() -> AsyncIterator[AsyncSession]:
        async with sessions() as db:
            yield db

    settings = Settings(
        enable_dev_endpoints=True,
        dev_token="dev-secret",
        frontend_url=FRONTEND,
        public_backend_url="https://api.test",
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_instagram] = MockInstagram
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


async def connect(client: httpx.AsyncClient, token: str) -> httpx.Response:
    """Connect, then follow the mock's consent screen straight to the callback."""
    response = await client.post(f"/api/o/{token}/instagram/connect")
    assert response.status_code == 200, response.text
    auth_url = urlsplit(response.json()["auth_url"])
    assert f"{auth_url.scheme}://{auth_url.netloc}{auth_url.path}" == (
        "https://api.test/oauth/instagram/callback"
    )
    return await client.get(f"{auth_url.path}?{auth_url.query}")


async def business_of(sessions: async_sessionmaker[AsyncSession]) -> Business:
    async with sessions() as db:
        business = await db.scalar(select(Business))
        assert business is not None
        return business


async def test_connecting_keeps_the_token_queues_the_import_and_returns_to_the_wizard(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)

    response = await connect(client, token)

    assert response.status_code == 303
    assert response.headers["location"] == f"{FRONTEND}/o/{token}?step=instagram&connected=1"
    async with sessions() as db:
        account = await db.scalar(select(SocialAccount))
        jobs = (await db.scalars(select(Job.kind))).all()
        business = await db.scalar(select(Business))
    assert account is not None and business is not None
    assert (account.status, account.provider, account.handle) == ("connected", "mock", "tunegocio")
    assert account.access_token and account.token_expires_at
    assert jobs == ["import_instagram"]
    assert business.instagram_handle == "tunegocio"
    state = (await client.get(f"/api/o/{token}")).json()
    assert state["instagram"] == {"status": "connected", "handle": "tunegocio"}


async def test_connecting_twice_updates_the_same_account(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)

    await connect(client, token)
    await connect(client, token)

    async with sessions() as db:
        assert len((await db.scalars(select(SocialAccount))).all()) == 1


async def test_a_refused_consent_returns_to_the_wizard_without_connecting(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    state = sign_state(token, DEV_STATE_SECRET)

    response = await client.get(
        "/oauth/instagram/callback", params={"error": "access_denied", "state": state}
    )

    assert response.headers["location"].endswith("?step=instagram&connected=0")
    async with sessions() as db:
        assert await db.scalar(select(SocialAccount)) is None


async def test_a_callback_after_the_onboarding_was_completed_changes_nothing(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    response = await client.post(f"/api/o/{token}/instagram/connect")
    auth_url = urlsplit(response.json()["auth_url"])
    async with sessions() as db:
        link = await db.scalar(select(MagicLink))
        assert link is not None
        link.completed_at = datetime.now(UTC)
        await db.commit()

    response = await client.get(f"{auth_url.path}?{auth_url.query}")

    assert response.status_code == 303
    assert response.headers["location"] == f"{FRONTEND}/o/{token}"
    async with sessions() as db:
        assert await db.scalar(select(SocialAccount)) is None
        assert (await db.scalars(select(Job.kind))).all() == []


async def test_a_forged_state_is_rejected(client: httpx.AsyncClient) -> None:
    token = await new_link(client)

    response = await client.get(
        "/oauth/instagram/callback",
        params={"code": "c", "state": sign_state(token, "not-our-secret")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_state"


def job_context(
    sessions: async_sessionmaker[AsyncSession], storage: FakeStorage, business_id: uuid.UUID
) -> JobContext:
    return JobContext(
        uuid.uuid4(), business_id, sessions, storage, FakeChannel(), SequenceModel([])
    )


async def run_import(
    sessions: async_sessionmaker[AsyncSession],
    storage: FakeStorage,
    instagram: MockInstagram,
    max_images: int = 24,
) -> dict[str, Any]:
    business = await business_of(sessions)
    job = import_instagram_job(instagram, max_posts=100, max_images=max_images)
    result = await job(job_context(sessions, storage, business.id), {})
    assert result is not None
    return result


async def test_the_import_feeds_the_brand_inputs_and_queues_the_analyses(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    token = await new_link(client)
    await connect(client, token)

    result = await run_import(sessions, storage, MockInstagram())

    assert result == {"posts": 3, "images": 3, "skipped": 0}
    async with sessions() as db:
        assets = (await db.scalars(select(BrandAsset).order_by(BrandAsset.external_id))).all()
        analyses = (await db.scalars(select(Job).where(Job.kind == "analyze_asset"))).all()
        business = await db.scalar(select(Business))
    assert business is not None
    assert [(a.source, a.kind, a.status) for a in assets] == [("instagram", "photo", "ready")] * 3
    assert [a.external_id for a in assets] == ["mock-media-0", "mock-media-1", "mock-media-2"]
    assert assets[0].owner_hint and assets[0].owner_hint.startswith("Mesa de roble")
    for asset in assets:
        assert f"assets/{asset.storage_path}" in storage.objects
        assert f"assets/{asset.business_id}/{asset.id}-llm.jpg" in storage.objects
    assert sorted(job.payload["asset_id"] for job in analyses) == sorted(str(a.id) for a in assets)
    imported = business.onboarding_data["instagram"]
    assert imported["biography"] == "Muebles de madera hechos a mano en Montevideo."
    assert [post["likes"] for post in imported["posts"]] == [40, 30, 20]


async def stored_token(sessions: async_sessionmaker[AsyncSession]) -> str | None:
    async with sessions() as db:
        account = await db.scalar(select(SocialAccount))
        assert account is not None
        return account.access_token


async def test_the_import_deletes_the_token_it_used(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    token = await new_link(client)
    await connect(client, token)
    assert await stored_token(sessions)

    await run_import(sessions, storage, MockInstagram())

    assert await stored_token(sessions) is None
    async with sessions() as db:
        account = await db.scalar(select(SocialAccount))
    assert account is not None
    assert account.status == "connected" and account.token_expires_at


async def test_a_failed_import_still_deletes_the_token(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    class Unauthorized(MockInstagram):
        async def profile(self, access_token: str) -> InstagramProfile:
            raise InstagramError("401 from Instagram", status=401)

    token = await new_link(client)
    await connect(client, token)

    with pytest.raises(InstagramError):
        await run_import(sessions, storage, Unauthorized())

    assert await stored_token(sessions) is None


async def test_the_import_does_not_run_twice_on_one_token(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    token = await new_link(client)
    await connect(client, token)
    await run_import(sessions, storage, MockInstagram())

    assert await run_import(sessions, storage, MockInstagram()) == {
        "skipped": "no connected instagram"
    }


async def test_a_job_on_the_old_token_does_not_clear_the_reconnects_token(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    class ReconnectsMidImport(MockInstagram):
        """The Owner reconnects while this job is reading Instagram: the callback overwrites the
        token on the same row and queues a second import."""

        async def profile(self, access_token: str) -> InstagramProfile:
            async with sessions() as db:
                account = await db.scalar(select(SocialAccount))
                assert account is not None
                account.access_token = "fresh-token"
                await db.commit()
            return await super().profile(access_token)

    token = await new_link(client)
    await connect(client, token)

    await run_import(sessions, storage, ReconnectsMidImport())

    assert await stored_token(sessions) == "fresh-token"
    second = await run_import(sessions, storage, MockInstagram())
    assert second["posts"] == 3  # the second import ran; it was not skipped for want of a token
    assert await stored_token(sessions) is None


async def test_a_cancelled_import_still_deletes_the_token(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    started = asyncio.Event()

    class Hangs(MockInstagram):
        async def profile(self, access_token: str) -> InstagramProfile:
            started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

    token = await new_link(client)
    await connect(client, token)
    business = await business_of(sessions)
    job = import_instagram_job(Hangs(), max_posts=100, max_images=24)
    task = asyncio.create_task(job(job_context(sessions, storage, business.id), {}))
    await started.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert await stored_token(sessions) is None


def failing_sessions(
    sessions: async_sessionmaker[AsyncSession], fail_on: set[int]
) -> async_sessionmaker[AsyncSession]:
    """The job's database sessions, where the numbered calls (1 = the first) raise."""
    calls = 0

    def factory() -> AsyncSession:
        nonlocal calls
        calls += 1
        if calls in fail_on:
            raise RuntimeError(f"database unavailable (session {calls})")
        return sessions()

    return cast(async_sessionmaker[AsyncSession], factory)


async def test_a_failure_right_after_reading_the_token_still_deletes_it(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    token = await new_link(client)
    await connect(client, token)
    business = await business_of(sessions)
    job = import_instagram_job(MockInstagram(), max_posts=100, max_images=24)
    # session 2 is the read of the images imported before, right after the token's read
    context = job_context(failing_sessions(sessions, {2}), storage, business.id)

    with pytest.raises(RuntimeError, match="session 2"):
        await job(context, {})

    assert await stored_token(sessions) is None


async def test_a_failed_cleanup_is_logged_and_the_original_error_is_raised(
    client: httpx.AsyncClient,
    sessions: async_sessionmaker[AsyncSession],
    storage: FakeStorage,
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = await new_link(client)
    await connect(client, token)
    business = await business_of(sessions)
    job = import_instagram_job(MockInstagram(), max_posts=100, max_images=24)
    context = job_context(failing_sessions(sessions, {2, 3}), storage, business.id)

    with pytest.raises(RuntimeError, match="session 2"):
        await job(context, {})

    assert "could not clear the instagram token" in caplog.text
    assert await stored_token(sessions) == "mock-token-mock-code"


async def test_a_reconnect_stores_a_fresh_token_and_only_adds_what_is_new(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    token = await new_link(client)
    await connect(client, token)
    await run_import(sessions, storage, MockInstagram())
    await connect(client, token)
    assert await stored_token(sessions)

    result = await run_import(sessions, storage, MockInstagram())

    assert result["images"] == 0
    async with sessions() as db:
        assert len((await db.scalars(select(BrandAsset))).all()) == 3


async def test_an_image_that_fails_to_download_is_skipped(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    token = await new_link(client)
    await connect(client, token)

    result = await run_import(sessions, storage, BrokenDownloads())

    assert result == {"posts": 3, "images": 2, "skipped": 1}


async def test_the_import_stops_at_the_image_limit(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    token = await new_link(client)
    await connect(client, token)

    result = await run_import(sessions, storage, Carousel(), max_images=3)

    assert result["images"] == 3
    async with sessions() as db:
        ids = sorted((await db.scalars(select(BrandAsset.external_id))).all())
    assert ids == ["slide-0", "slide-1", "slide-2"]


async def test_without_a_connected_account_the_import_does_nothing(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    await new_link(client)

    assert await run_import(sessions, storage, MockInstagram()) == {
        "skipped": "no connected instagram"
    }


async def test_imported_photos_show_in_the_wizard_without_taking_upload_slots(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    token = await new_link(client)
    await connect(client, token)
    await run_import(sessions, storage, Carousel(), max_images=5)
    await upload(client, storage, token)

    state = (await client.get(f"/api/o/{token}")).json()

    sources = [asset["source"] for asset in state["assets"]]
    assert sorted(sources) == ["instagram"] * 5 + ["web"]
    assert {asset["kind"] for asset in state["assets"]} == {"photo"}
