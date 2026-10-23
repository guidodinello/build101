import asyncio
import logging
from datetime import timedelta
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.background import BackgroundWork
from app.channels.inbound import DbDedupeStore
from tests.conftest import requires_db

pytestmark = requires_db


async def test_the_first_delivery_is_new_and_the_replay_is_not(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    store = DbDedupeStore(sessions, BackgroundWork())

    assert await store.first_seen("wamid.A") is True
    assert await store.first_seen("wamid.A") is False
    assert await store.first_seen("wamid.B") is True


async def test_a_replayed_id_is_ignored_across_restarts(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    assert await DbDedupeStore(sessions, BackgroundWork()).first_seen("wamid.A") is True

    # A new store on the same database is what a restart or a deploy leaves behind.
    assert await DbDedupeStore(sessions, BackgroundWork()).first_seen("wamid.A") is False


async def pruned(store: DbDedupeStore) -> None:
    """Waits for the background prune the last `first_seen` started."""
    assert store._prune_task is not None
    await store._prune_task


async def test_only_expired_ids_are_pruned(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as db:
        await db.execute(
            text(
                "insert into inbound_deliveries (external_id, received_at) values "
                "('old', now() - interval '49 hours'), ('recent', now() - interval '47 hours')"
            )
        )
        await db.commit()

    store = DbDedupeStore(sessions, BackgroundWork(), retention=timedelta(hours=48))
    assert await store.first_seen("fresh") is True
    await pruned(store)

    async with sessions() as db:
        kept = set((await db.execute(text("select external_id from inbound_deliveries"))).scalars())
    assert kept == {"recent", "fresh"}
    assert await store.first_seen("old") is True


class FailingDelete:
    """A session whose DELETE fails, e.g. on a lock timeout."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error or OperationalError(
            "delete from inbound_deliveries", {}, Exception("lock timeout")
        )

    async def __aenter__(self) -> "FailingDelete":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def execute(self, *args: object, **kwargs: object) -> None:
        raise self.error


class UseCounter:
    """Hands out real sessions, except that the `fail_on`-th use is a failing prune."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        fail_on: int,
        error: Exception | None = None,
    ) -> None:
        self.sessions = sessions
        self.fail_on = fail_on
        self.error = error
        self.uses = 0

    def __call__(self) -> object:
        self.uses += 1
        return FailingDelete(self.error) if self.uses == self.fail_on else self.sessions()

    def as_sessionmaker(self) -> async_sessionmaker[AsyncSession]:
        return cast(async_sessionmaker[AsyncSession], self)


async def test_a_failed_prune_never_fails_first_seen(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    counter = UseCounter(sessions, fail_on=2)  # 1: the insert, 2: the prune
    store = DbDedupeStore(counter.as_sessionmaker(), BackgroundWork())

    # The prune runs after the id is committed. If it failed the request, Kapso's retry would
    # find the id stored and the message would never be handled.
    assert await store.first_seen("wamid.A") is True
    await pruned(store)

    assert counter.uses == 2
    assert await DbDedupeStore(sessions, BackgroundWork()).first_seen("wamid.A") is False


@pytest.mark.parametrize(
    "error", [OSError("connection reset"), RuntimeError("driver bug")], ids=["oserror", "other"]
)
async def test_a_prune_failing_with_any_error_is_logged_and_the_store_still_works(
    sessions: async_sessionmaker[AsyncSession],
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    now = [0.0]
    counter = UseCounter(sessions, fail_on=2, error=error)  # asyncpg can raise a bare OSError
    store = DbDedupeStore(counter.as_sessionmaker(), BackgroundWork(), clock=lambda: now[0])

    with caplog.at_level(logging.WARNING, logger="app.channels.inbound"):
        assert await store.first_seen("wamid.A") is True
        await pruned(store)

    assert "pruning inbound_deliveries failed" in caplog.text
    now[0] = 60  # the retry delay, not a whole interval
    assert await store.first_seen("wamid.B") is True
    await pruned(store)
    assert counter.uses == 4  # insert, failed prune, insert, prune that ran
    assert await store.first_seen("wamid.A") is False


async def test_a_failed_prune_is_retried_soon_and_a_good_one_waits_the_interval(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    now = [0.0]
    counter = UseCounter(sessions, fail_on=2)
    store = DbDedupeStore(
        counter.as_sessionmaker(), BackgroundWork(), prune_every_s=3600, clock=lambda: now[0]
    )

    await store.first_seen("a")  # use 1 inserts, use 2 is the prune that fails
    await pruned(store)
    assert counter.uses == 2

    now[0] = 59
    await store.first_seen("b")  # not due yet: one use, the insert
    assert counter.uses == 3

    now[0] = 60
    await store.first_seen("c")  # due again after the retry delay: insert + prune
    await pruned(store)
    assert counter.uses == 5

    now[0] = 61
    await store.first_seen("d")  # the prune worked, so the next one is an interval away
    assert counter.uses == 6


async def test_first_seen_does_not_wait_for_the_prune(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    store = DbDedupeStore(sessions, BackgroundWork())
    release = asyncio.Event()

    async def slow_prune() -> None:
        await release.wait()

    monkeypatch.setattr(store, "_prune", slow_prune)

    assert await asyncio.wait_for(store.first_seen("wamid.A"), timeout=5) is True
    assert store._prune_task is not None
    assert not store._prune_task.done()  # still running, and the webhook is already answered

    release.set()
    await pruned(store)


async def test_never_more_than_one_prune_is_in_flight(
    sessions: async_sessionmaker[AsyncSession], monkeypatch: pytest.MonkeyPatch
) -> None:
    store = DbDedupeStore(
        sessions, BackgroundWork(), prune_every_s=0
    )  # always due once the last one is done
    release = asyncio.Event()
    started = 0

    async def slow_prune() -> None:
        nonlocal started
        started += 1
        await release.wait()

    monkeypatch.setattr(store, "_prune", slow_prune)

    for key in ("a", "b", "c"):
        await store.first_seen(key)
    assert started == 1

    release.set()
    await pruned(store)
    await store.first_seen("d")  # the first one is done: the next one may start
    await pruned(store)
    assert started == 2
