import asyncio
import time
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any, cast

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api import ready
from app.api.ready import (
    DATABASE_RECHECK_S,
    POLLED_WITHIN,
    DatabaseProbe,
    get_database,
    get_job_runner,
)
from app.background import BackgroundWork
from app.channels.router import get_channel, get_inbound_handler
from app.config import Settings, get_settings
from app.db.session import create_engine, get_sessionmaker
from app.jobs.runner import JobRunner, PeriodicCheck
from app.main import app
from tests.conftest import TEST_DATABASE_URL, requires_db
from tests.fakes import EventLog, FakeChannel, FakeStorage, SequenceModel
from tests.test_production_config import set_production_env

COMMIT = "a1b2c3d4e5f60718293a4b5c6d7e8f9012345678"
# Nothing listens on port 1: the connection is refused at once
UNREACHABLE = "postgresql+asyncpg://postgres:db-password@127.0.0.1:1/unreachable"


def real() -> Settings:
    """Built in each test, after conftest has stopped Settings from reading backend/.env."""
    return Settings(publisher="zernio", railway_git_commit_sha=COMMIT)


def new_runner(
    sessions: async_sessionmaker[AsyncSession],
    *checks: PeriodicCheck,
    background: BackgroundWork | None = None,
) -> JobRunner:
    model: Any = SequenceModel([])
    return JobRunner(
        sessions,
        {},
        FakeStorage(),
        FakeChannel(),
        model,
        EventLog(),
        poll_interval_s=0.01,
        checks=checks,
        background=background or BackgroundWork(),
    )


async def polled(runner: JobRunner) -> JobRunner:
    async with asyncio.timeout(2):
        while not runner.polled_within(POLLED_WITHIN):
            await asyncio.sleep(0.01)
    return runner


@pytest.fixture
async def unreachable() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_engine(UNREACHABLE)
    yield async_sessionmaker(engine)
    await engine.dispose()


class CountedSessions:
    """Real sessions, counted: each database probe opens one."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions
        self.opened = 0

    def __call__(self) -> AsyncSession:
        self.opened += 1
        return self.sessions()

    def as_sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        return cast(async_sessionmaker[AsyncSession], self)


async def get_ready(
    settings: Settings,
    database: DatabaseProbe | None,
    runner: JobRunner | None,
    path: str = "/ready",
) -> httpx.Response:
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_database] = lambda: database
    app.dependency_overrides[get_job_runner] = lambda: runner
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://t"
        ) as client:
            return await client.get(path)
    finally:
        app.dependency_overrides.clear()


def checks(response: httpx.Response) -> dict[str, str]:
    return response.json()["checks"]


def ready_soon(client: TestClient) -> httpx.Response:
    """/ready, asked again until it answers 200 or 2 s pass."""
    deadline = time.monotonic() + 2
    while (response := client.get("/ready")).status_code != 200 and time.monotonic() < deadline:
        time.sleep(0.01)
    return response


@requires_db
async def test_ready_when_the_database_answers_the_runner_polls_and_the_publisher_is_real(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    background = BackgroundWork()
    runner = new_runner(sessions, background=background)
    await runner.start()
    try:
        response = await get_ready(real(), DatabaseProbe(sessions), await polled(runner))
    finally:
        runner.stop()
        await background.stop()

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "checks": {"database": "ok", "job_runner": "ok", "publisher": "ok"},
        "commit": COMMIT,
    }


@requires_db
async def test_not_ready_when_the_database_is_unreachable(
    sessions: async_sessionmaker[AsyncSession],
    unreachable: async_sessionmaker[AsyncSession],
) -> None:
    background = BackgroundWork()
    runner = new_runner(sessions, background=background)
    await runner.start()
    try:
        response = await get_ready(real(), DatabaseProbe(unreachable), await polled(runner))
    finally:
        runner.stop()
        await background.stop()

    assert response.status_code == 503
    assert checks(response) == {"database": "fail", "job_runner": "ok", "publisher": "ok"}


async def test_not_ready_without_a_database(unreachable: async_sessionmaker[AsyncSession]) -> None:
    unset = await get_ready(real(), None, None)
    down = await get_ready(real(), DatabaseProbe(unreachable), None)

    assert unset.status_code == down.status_code == 503
    assert checks(unset)["database"] == checks(down)["database"] == "fail"


@requires_db
async def test_not_ready_when_the_job_runner_is_off_or_stopped(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    background = BackgroundWork()
    runner = new_runner(sessions, background=background)
    await runner.start()
    await polled(runner)
    runner.stop()
    await background.stop()

    off = await get_ready(real(), DatabaseProbe(sessions), None)
    stopped = await get_ready(real(), DatabaseProbe(sessions), runner)

    for response in (off, stopped):
        assert response.status_code == 503
        assert checks(response) == {"database": "ok", "job_runner": "fail", "publisher": "ok"}


@requires_db
async def test_not_ready_when_the_job_runner_stopped_polling(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    rounds: list[None] = []
    never = asyncio.Event()

    async def hangs_after_the_first_round(_: Any) -> None:
        rounds.append(None)
        if len(rounds) > 1:
            await never.wait()

    background = BackgroundWork()
    runner = new_runner(
        sessions,
        PeriodicCheck("hangs", timedelta(0), hangs_after_the_first_round),
        background=background,
    )
    await runner.start()
    try:
        await polled(runner)
        await asyncio.sleep(0.1)
        monkeypatch.setattr(ready, "POLLED_WITHIN", timedelta(milliseconds=50))
        response = await get_ready(real(), DatabaseProbe(sessions), runner)
    finally:
        runner.stop()
        await background.stop()

    assert response.status_code == 503
    assert checks(response) == {"database": "ok", "job_runner": "fail", "publisher": "ok"}


@requires_db
async def test_ready_asks_the_database_once_per_recheck_window(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = [0.0]
    counted = CountedSessions(sessions)
    database = DatabaseProbe(counted.as_sessionmaker(), clock=lambda: now[0])

    await get_ready(real(), database, None)
    now[0] = DATABASE_RECHECK_S / 2
    within = await get_ready(real(), database, None)
    assert counted.opened == 1
    assert checks(within)["database"] == "ok"

    now[0] = DATABASE_RECHECK_S
    await get_ready(real(), database, None)
    assert counted.opened == 2


async def test_a_failed_database_answer_is_reused_within_the_window_too(
    unreachable: async_sessionmaker[AsyncSession],
) -> None:
    counted = CountedSessions(unreachable)
    database = DatabaseProbe(counted.as_sessionmaker(), clock=lambda: 0.0)

    responses = [await get_ready(real(), database, None) for _ in range(3)]

    assert counted.opened == 1
    assert [checks(response)["database"] for response in responses] == ["fail"] * 3


@requires_db
async def test_concurrent_calls_share_one_database_probe(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    counted = CountedSessions(sessions)
    database = DatabaseProbe(counted.as_sessionmaker())

    answers = await asyncio.gather(*(database.answers() for _ in range(5)))

    assert answers == [True] * 5
    assert counted.opened == 1


def test_every_ready_call_asks_the_same_database_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", UNREACHABLE)
    get_sessionmaker.cache_clear()
    try:
        assert get_database(get_settings()) is get_database(get_settings())
    finally:
        get_sessionmaker.cache_clear()


async def test_not_ready_on_the_mock_publisher() -> None:
    response = await get_ready(Settings(publisher="mock"), None, None)

    assert response.status_code == 503
    assert checks(response)["publisher"] == "fail"


async def test_ready_shows_check_names_and_the_commit_only(
    unreachable: async_sessionmaker[AsyncSession],
) -> None:
    response = await get_ready(real(), DatabaseProbe(unreachable), None)

    assert response.json() == {
        "status": "fail",
        "checks": {"database": "fail", "job_runner": "fail", "publisher": "ok"},
        "commit": COMMIT,
    }
    for leak in ("127.0.0.1", "db-password", "refused", "zernio"):
        assert leak not in response.text


async def test_health_answers_ok_while_not_ready() -> None:
    not_ready = await get_ready(Settings(), None, None)
    health = await get_ready(Settings(), None, None, path="/health")

    assert not_ready.status_code == 503
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}


def test_the_commit_is_railways(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", COMMIT)

    assert Settings().railway_git_commit_sha == COMMIT


def test_the_running_app_reports_its_own_runner_and_database() -> None:
    app.dependency_overrides[get_inbound_handler] = lambda: None
    try:
        with TestClient(app) as client:
            response = client.get("/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "status": "fail",
        "checks": {"database": "fail", "job_runner": "fail", "publisher": "fail"},
        "commit": None,
    }


@requires_db
def test_the_app_in_production_is_ready_once_its_job_runner_polls(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    assert TEST_DATABASE_URL
    set_production_env(monkeypatch, database_url=TEST_DATABASE_URL)
    monkeypatch.setattr("app.main.build_job_runner", lambda *_: new_runner(get_sessionmaker()))
    get_channel.cache_clear()
    get_sessionmaker.cache_clear()
    app.dependency_overrides[get_inbound_handler] = lambda: None
    try:
        with TestClient(app) as client:
            response = ready_soon(client)
    finally:
        app.dependency_overrides.clear()
        get_channel.cache_clear()
        get_sessionmaker.cache_clear()

    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "job_runner": "ok", "publisher": "ok"}
