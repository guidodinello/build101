from datetime import timedelta
from typing import cast

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.inbound import DbDedupeStore
from tests.conftest import requires_db

pytestmark = requires_db


async def test_the_first_delivery_is_new_and_the_replay_is_not(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    store = DbDedupeStore(sessions)

    assert await store.first_seen("wamid.A") is True
    assert await store.first_seen("wamid.A") is False
    assert await store.first_seen("wamid.B") is True


async def test_a_replayed_id_is_ignored_across_restarts(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    assert await DbDedupeStore(sessions).first_seen("wamid.A") is True

    # A new store on the same database is what a restart or a deploy leaves behind.
    assert await DbDedupeStore(sessions).first_seen("wamid.A") is False


async def test_only_expired_ids_are_pruned(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with sessions() as db:
        await db.execute(
            text(
                "insert into inbound_deliveries (external_id, received_at) values "
                "('old', now() - interval '49 hours'), ('recent', now() - interval '47 hours')"
            )
        )
        await db.commit()

    store = DbDedupeStore(sessions, retention=timedelta(hours=48))
    assert await store.first_seen("fresh") is True

    async with sessions() as db:
        kept = set((await db.execute(text("select external_id from inbound_deliveries"))).scalars())
    assert kept == {"recent", "fresh"}
    assert await store.first_seen("old") is True


class FailingDelete:
    """A session whose DELETE fails, e.g. on a lock timeout."""

    async def __aenter__(self) -> "FailingDelete":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def execute(self, *args: object, **kwargs: object) -> None:
        raise OperationalError("delete from inbound_deliveries", {}, Exception("lock timeout"))


async def test_a_failed_prune_never_fails_first_seen(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    calls = 0

    def sessions_whose_second_use_fails() -> object:
        nonlocal calls
        calls += 1
        return sessions() if calls == 1 else FailingDelete()  # 1: the insert, 2: the prune

    store = DbDedupeStore(cast(async_sessionmaker[AsyncSession], sessions_whose_second_use_fails))

    # The prune runs after the id is committed. If it raised out of first_seen, Kapso's retry
    # would find the id stored and the message would never be handled.
    assert await store.first_seen("wamid.A") is True
    assert calls == 2
    assert await DbDedupeStore(sessions).first_seen("wamid.A") is False
