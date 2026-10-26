import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.instagram import BINDING_COOKIE, DEV_STATE_SECRET
from app.config import Settings, get_settings
from app.db.models import BrandAsset, Business, Job, MagicLink, SocialAccount
from app.db.session import get_session
from app.instagram.base import InstagramError, InstagramImage, InstagramMedia, InstagramProfile
from app.instagram.factory import get_instagram
from app.instagram.mock import MockInstagram
from app.instagram.oauth_state import sign_ticket
from app.jobs.instagram import import_instagram_job
from app.jobs.runner import JobContext
from app.main import app
from app.onboarding.links import hash_token
from app.pilot import get_pilot_list
from app.storage import get_storage
from tests.conftest import requires_db
from tests.fakes import EventLog, FakeChannel, FakeStorage, SequenceModel
from tests.test_onboarding_api import new_link, off_the_pilot_list, upload

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


async def start(client: httpx.AsyncClient, token: str) -> httpx.Response:
    """POST /connect, then navigate to the `auth_url` it returns, as the wizard does."""
    response = await client.post(f"/api/o/{token}/instagram/connect")
    assert response.status_code == 200, response.text
    auth_url = urlsplit(response.json()["auth_url"])
    assert f"{auth_url.scheme}://{auth_url.netloc}{auth_url.path}" == (
        f"https://api.test/api/o/{token}/instagram/start"
    )
    return await client.get(f"{auth_url.path}?{auth_url.query}")


def binding_cookie(started: httpx.Response) -> dict[str, str]:
    """The browser's side of the start hop: the cookie it sends back to the callback."""
    cookie = SimpleCookie(started.headers["set-cookie"])
    return {"Cookie": f"{BINDING_COOKIE}={cookie[BINDING_COOKIE].value}"}


def assert_cookie_cleared(response: httpx.Response) -> None:
    cleared = response.headers["set-cookie"].lower()
    assert f"{BINDING_COOKIE}=" in cleared and "max-age=0" in cleared


def callback_params(started: httpx.Response, **extra: str) -> dict[str, str]:
    """What the consent screen sends back: our `state`, plus the `code` (or `error`) it adds."""
    query = parse_qs(urlsplit(started.headers["location"]).query)
    return {"state": query["state"][0], **extra}


async def connect(client: httpx.AsyncClient, token: str) -> httpx.Response:
    """The whole flow with the mock adapter: start hop, consent screen, callback."""
    started = await start(client, token)
    assert started.status_code == 303
    location = urlsplit(started.headers["location"])
    assert f"{location.scheme}://{location.netloc}{location.path}" == (
        "https://api.test/oauth/instagram/callback"
    )
    return await client.get(f"{location.path}?{location.query}", headers=binding_cookie(started))


async def business_of(sessions: async_sessionmaker[AsyncSession]) -> Business:
    async with sessions() as db:
        business = await db.scalar(select(Business))
        assert business is not None
        return business


async def test_connect_is_refused_when_business_is_not_in_instagram_pilot(
    client: httpx.AsyncClient,
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    token = await new_link(client)
    app.dependency_overrides[get_settings] = lambda: Settings(
        enable_dev_endpoints=True,
        dev_token="dev-secret",
        frontend_url=FRONTEND,
        public_backend_url="https://api.test",
        instagram="meta",
        instagram_pilot_businesses="",
    )

    response = await client.post(f"/api/o/{token}/instagram/connect")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "instagram_not_allowed"


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
    started = await start(client, token)

    response = await client.get(
        "/oauth/instagram/callback",
        params=callback_params(started, error="access_denied"),
        headers=binding_cookie(started),
    )

    assert response.headers["location"].endswith("?step=instagram&connected=0&reason=declined")
    async with sessions() as db:
        assert await db.scalar(select(SocialAccount)) is None


async def test_a_callback_after_the_onboarding_was_completed_changes_nothing(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    started = await start(client, token)
    async with sessions() as db:
        link = await db.scalar(select(MagicLink))
        assert link is not None
        link.completed_at = datetime.now(UTC)
        await db.commit()

    response = await client.get(
        urlsplit(started.headers["location"]).path,
        params=callback_params(started, code="c"),
        headers=binding_cookie(started),
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"{FRONTEND}/o/{token}"
    async with sessions() as db:
        assert await db.scalar(select(SocialAccount)) is None
        assert (await db.scalars(select(Job.kind))).all() == []


async def test_the_oauth_state_carries_no_magic_link_token(client: httpx.AsyncClient) -> None:
    token = await new_link(client)

    started = await start(client, token)

    assert started.status_code == 303
    assert token not in started.headers["location"]
    assert token not in started.headers["location"].lower()


async def test_the_start_hop_sets_a_browser_bound_cookie_for_the_callback_only(
    client: httpx.AsyncClient,
) -> None:
    token = await new_link(client)

    started = await start(client, token)

    attributes = started.headers["set-cookie"].lower()
    assert f"{BINDING_COOKIE}=" in attributes
    for attribute in ("httponly", "secure", "samesite=lax", "path=/oauth/instagram", "max-age=900"):
        assert attribute in attributes


async def test_the_cookie_is_cleared_once_the_callback_ran(client: httpx.AsyncClient) -> None:
    token = await new_link(client)

    response = await connect(client, token)

    assert_cookie_cleared(response)


async def test_a_callback_without_the_cookie_is_refused(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    started = await start(client, token)

    response = await client.get(
        "/oauth/instagram/callback", params=callback_params(started, code="c")
    )

    assert response.status_code == 400
    assert "No pudimos continuar con Instagram" in response.text
    assert "Volver a WhatsApp" in response.text
    async with sessions() as db:
        assert await db.scalar(select(SocialAccount)) is None


async def test_a_callback_with_another_browsers_cookie_is_refused(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    """Login CSRF: the attacker's `state` reaches the victim, whose cookie is for another nonce."""
    attacker_token = await new_link(client)
    attacker = await start(client, attacker_token)
    victim_token = await new_link(client)
    victim = await start(client, victim_token)

    response = await client.get(
        "/oauth/instagram/callback",
        params=callback_params(attacker, code="c"),
        headers=binding_cookie(victim),
    )

    assert response.status_code == 400
    assert "No pudimos continuar con Instagram" in response.text
    assert "Volver a WhatsApp" in response.text
    assert_cookie_cleared(response)
    async with sessions() as db:
        assert await db.scalar(select(SocialAccount)) is None


async def test_a_callback_for_a_link_that_is_gone_clears_the_cookie(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    started = await start(client, token)
    async with sessions() as db:
        link = await db.scalar(select(MagicLink))
        assert link is not None
        link.expires_at = datetime.now(UTC)
        await db.commit()

    response = await client.get(
        "/oauth/instagram/callback",
        params=callback_params(started, code="c"),
        headers=binding_cookie(started),
    )

    assert response.status_code == 410
    assert_cookie_cleared(response)


async def test_an_unexpected_failure_in_the_callback_clears_the_cookie(
    client: httpx.AsyncClient,
) -> None:
    class Crashing(MockInstagram):
        async def exchange_code(self, code: str, redirect_uri: str) -> Any:
            raise RuntimeError("boom")

    token = await new_link(client)
    started = await start(client, token)
    app.dependency_overrides[get_instagram] = Crashing

    response = await client.get(
        "/oauth/instagram/callback",
        params=callback_params(started, code="c"),
        headers=binding_cookie(started),
    )

    assert response.status_code == 500
    assert_cookie_cleared(response)


async def test_a_forged_cookie_is_refused(client: httpx.AsyncClient) -> None:
    token = await new_link(client)
    started = await start(client, token)

    response = await client.get(
        "/oauth/instagram/callback",
        params=callback_params(started, code="c"),
        headers={"Cookie": f"{BINDING_COOKIE}={token}.nonce.9999999999.forged"},
    )

    assert response.status_code == 400
    assert "No pudimos continuar con Instagram" in response.text
    assert "Volver a WhatsApp" in response.text


async def test_an_expired_or_forged_ticket_does_not_start_a_connect(
    client: httpx.AsyncClient,
) -> None:
    token = await new_link(client)
    expired = sign_ticket(token, DEV_STATE_SECRET, now=1)
    forged = sign_ticket(token, "not-our-secret")

    for ticket in (expired, forged, ""):
        response = await client.get(f"/api/o/{token}/instagram/start", params={"ticket": ticket})

        assert response.status_code == 400
        assert "No pudimos continuar con Instagram" in response.text
        assert "Volver a WhatsApp" in response.text
        assert "set-cookie" not in response.headers


async def test_a_ticket_for_one_link_does_not_start_another(client: httpx.AsyncClient) -> None:
    token, other = await new_link(client), await new_link(client)
    ticket = sign_ticket(token, DEV_STATE_SECRET)

    response = await client.get(f"/api/o/{other}/instagram/start", params={"ticket": ticket})

    assert response.status_code == 400
    assert "set-cookie" not in response.headers


async def test_the_start_hop_refuses_a_completed_onboarding(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    ticket = sign_ticket(token, DEV_STATE_SECRET)
    async with sessions() as db:
        link = await db.scalar(select(MagicLink))
        assert link is not None
        link.completed_at = datetime.now(UTC)
        await db.commit()

    response = await client.get(f"/api/o/{token}/instagram/start", params={"ticket": ticket})

    assert response.status_code == 409


async def test_the_start_hop_refuses_a_number_not_on_the_pilot_list(
    client: httpx.AsyncClient,
) -> None:
    token = await new_link(client)
    ticket = sign_ticket(token, DEV_STATE_SECRET)
    app.dependency_overrides[get_pilot_list] = off_the_pilot_list

    response = await client.get(f"/api/o/{token}/instagram/start", params={"ticket": ticket})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_in_pilot"
    assert "set-cookie" not in response.headers


async def test_a_callback_for_a_number_not_on_the_pilot_list_connects_and_imports_nothing(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    token = await new_link(client)
    started = await start(client, token)
    app.dependency_overrides[get_pilot_list] = off_the_pilot_list

    response = await client.get(
        urlsplit(started.headers["location"]).path,
        params=callback_params(started, code="c"),
        headers=binding_cookie(started),
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_in_pilot"
    assert_cookie_cleared(response)
    async with sessions() as db:
        assert await db.scalar(select(SocialAccount)) is None
        assert (await db.scalars(select(Job.kind))).all() == []


def job_context(
    sessions: async_sessionmaker[AsyncSession], storage: FakeStorage, business_id: uuid.UUID
) -> JobContext:
    return JobContext(
        uuid.uuid4(), business_id, sessions, storage, FakeChannel(), SequenceModel([]), EventLog()
    )


async def run_import(
    sessions: async_sessionmaker[AsyncSession],
    storage: FakeStorage,
    instagram: MockInstagram,
    max_images: int = 24,
) -> dict[str, Any]:
    job = import_instagram_job(instagram, max_posts=100, max_images=max_images)
    business = await business_of(sessions)
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


async def test_the_import_claims_the_token_before_calling_instagram(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    in_the_database: list[str | None] = []

    class Peeks(MockInstagram):
        async def profile(self, access_token: str) -> InstagramProfile:
            in_the_database.append(await stored_token(sessions))
            return await super().profile(access_token)

    token = await new_link(client)
    await connect(client, token)
    assert await stored_token(sessions)

    result = await run_import(sessions, storage, Peeks())

    assert result["posts"] == 3
    assert in_the_database == [None]  # already gone when the first call to Instagram is made
    async with sessions() as db:
        account = await db.scalar(select(SocialAccount))
    assert account is not None
    assert account.status == "connected" and account.token_expires_at


async def test_a_failed_import_leaves_no_token(
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


async def test_while_the_import_is_in_flight_the_database_holds_no_token(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    """What a killed process (SIGKILL, OOM) or a deploy's cancellation leaves behind: the state
    in the middle of the import, with nothing to clean up."""
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

    assert await stored_token(sessions) is None
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
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


async def test_a_claim_waits_for_one_in_progress_and_then_finds_no_token(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    """Two imports that claim at the same instant: the second is held on the row lock until the
    first commits, then sees no token, instead of reading the same one."""
    token = await new_link(client)
    await connect(client, token)
    business = await business_of(sessions)
    job = import_instagram_job(MockInstagram(), max_posts=100, max_images=24)

    async with sessions() as first_claim:
        account = await first_claim.scalar(select(SocialAccount).with_for_update())
        assert account is not None and account.access_token
        second = asyncio.create_task(job(job_context(sessions, storage, business.id), {}))
        finished, _ = await asyncio.wait({second}, timeout=0.5)
        assert not finished  # waiting on the row lock
        account.access_token = None
        await first_claim.commit()

    assert await second == {"skipped": "no connected instagram"}


async def test_an_import_started_while_another_is_reading_instagram_is_skipped(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    started, release = asyncio.Event(), asyncio.Event()

    class Waits(MockInstagram):
        async def profile(self, access_token: str) -> InstagramProfile:
            started.set()
            await release.wait()
            return await super().profile(access_token)

    token = await new_link(client)
    await connect(client, token)
    business = await business_of(sessions)
    job = import_instagram_job(Waits(), max_posts=100, max_images=24)
    first = asyncio.create_task(job(job_context(sessions, storage, business.id), {}))
    await started.wait()

    second = await run_import(sessions, storage, MockInstagram())
    release.set()
    imported = await first

    assert second == {"skipped": "no connected instagram"}
    assert imported["posts"] == 3


async def test_a_reconnect_during_an_import_keeps_its_token_for_the_next_one(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession], storage: FakeStorage
) -> None:
    class ReconnectsMidImport(MockInstagram):
        """The Owner reconnects while this job is reading Instagram: the callback stores a fresh
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


async def submit_through(sessions: async_sessionmaker[AsyncSession], token: str) -> None:
    """What `/complete` leaves behind on the link it was called with."""
    async with sessions() as db:
        link = await db.scalar(select(MagicLink).where(MagicLink.token_hash == hash_token(token)))
        assert link is not None
        link.completed_at = datetime.now(UTC)
        await db.commit()


async def test_a_callback_through_a_sibling_link_after_submitting_changes_nothing(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    first = await new_link(client)
    second = await new_link(client)
    started = await start(client, second)
    await submit_through(sessions, first)

    response = await client.get(
        urlsplit(started.headers["location"]).path,
        params=callback_params(started, code="c"),
        headers=binding_cookie(started),
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"{FRONTEND}/o/{second}"
    assert_cookie_cleared(response)
    async with sessions() as db:
        assert await db.scalar(select(SocialAccount)) is None
        assert (await db.scalars(select(Job.kind))).all() == []


async def test_the_start_hop_through_a_sibling_link_is_refused_after_submitting(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    first = await new_link(client)
    second = await new_link(client)
    ticket_url = (await client.post(f"/api/o/{second}/instagram/connect")).json()["auth_url"]
    await submit_through(sessions, first)

    started = await client.get(f"{urlsplit(ticket_url).path}?{urlsplit(ticket_url).query}")

    assert started.status_code == 409
    assert started.json()["error"]["code"] == "onboarding_completed"
    assert "set-cookie" not in started.headers


async def test_a_callback_waiting_on_the_submit_imports_nothing_once_it_commits(
    client: httpx.AsyncClient, sessions: async_sessionmaker[AsyncSession]
) -> None:
    """A callback that reaches the check while `/complete` holds the Business waits for the lock,
    then sees the submit: no import is queued after the Brand Brain started."""
    first = await new_link(client)
    second = await new_link(client)
    started = await start(client, second)
    async with sessions() as db:
        business = await db.scalar(select(Business))
        assert business is not None
        await db.refresh(business, with_for_update=True)  # what /complete holds while it stamps
        callback = asyncio.create_task(
            client.get(
                urlsplit(started.headers["location"]).path,
                params=callback_params(started, code="c"),
                headers=binding_cookie(started),
            )
        )
        await asyncio.sleep(0.3)
        assert not callback.done()
        link = await db.scalar(select(MagicLink).where(MagicLink.token_hash == hash_token(first)))
        assert link is not None
        link.completed_at = datetime.now(UTC)
        await db.commit()

    response = await asyncio.wait_for(callback, timeout=5)

    assert response.status_code == 303
    assert response.headers["location"] == f"{FRONTEND}/o/{second}"
    async with sessions() as db:
        assert await db.scalar(select(SocialAccount)) is None
        assert (await db.scalars(select(Job.kind))).all() == []
