from datetime import timedelta

from sqlalchemy import text
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
