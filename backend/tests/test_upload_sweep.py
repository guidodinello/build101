import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import BrandAsset, Business
from app.jobs.queue import enqueue
from app.jobs.runner import JobContext, JobRunner, PeriodicCheck
from app.jobs.uploads import (
    SWEEP_EVERY,
    asset_id_of,
    orphaned,
    sweep_orphaned_uploads,
    upload_sweep,
)
from app.storage import SIGNED_UPLOAD_URL_TTL, StorageError, StoredObject
from tests.conftest import requires_db
from tests.fakes import FakeChannel, FakeStorage, SequenceModel

NOW = datetime(2026, 10, 19, 12, 0, tzinfo=UTC)
OLD = NOW - SIGNED_UPLOAD_URL_TTL - timedelta(minutes=1)
YOUNG = NOW - timedelta(minutes=5)


def test_asset_id_of_reads_originals_jpegs_and_llm_copies() -> None:
    asset_id = uuid.uuid4()

    assert asset_id_of(f"{asset_id}.heic") == asset_id
    assert asset_id_of(f"{asset_id}.jpg") == asset_id
    assert asset_id_of(f"{asset_id}-llm.jpg") == asset_id


@pytest.mark.parametrize("name", ["notes.txt", "x.jpg", f"{uuid.uuid4()}.gif", f"{uuid.uuid4()}"])
def test_asset_id_of_ignores_names_that_are_not_ours(name: str) -> None:
    assert asset_id_of(name) is None


def test_orphaned_keeps_an_active_assets_objects_whatever_their_age() -> None:
    active = uuid.uuid4()
    objects = [
        StoredObject(f"{active}.heic", OLD),
        StoredObject(f"{active}.jpg", OLD),
        StoredObject(f"{active}-llm.jpg", OLD),
    ]

    assert orphaned(objects, dead_assets=set(), active_assets={active}, now=NOW) == []


def test_orphaned_takes_dead_assets_at_once_and_unowned_objects_once_old() -> None:
    dead, old, young = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    objects = [
        StoredObject(f"{dead}.jpg", YOUNG),
        StoredObject(f"{old}.jpg", OLD),
        StoredObject(f"{young}.jpg", YOUNG),
        StoredObject("readme.txt", OLD),
    ]

    assert orphaned(objects, dead_assets={dead}, active_assets=set(), now=NOW) == [
        f"{dead}.jpg",
        f"{old}.jpg",
    ]


async def business_with_assets(
    sessions: async_sessionmaker[AsyncSession], **statuses: dict[str, object]
) -> tuple[uuid.UUID, dict[str, uuid.UUID]]:
    ids = {name: uuid.uuid4() for name in statuses}
    async with sessions() as db:
        business = Business(owner_phone="59899000000")
        db.add(business)
        await db.flush()
        for name, fields in statuses.items():
            db.add(
                BrandAsset(
                    id=ids[name],
                    business_id=business.id,
                    kind="photo",
                    source="web",
                    storage_path=f"{business.id}/{ids[name]}.jpg",
                    mime_type="image/jpeg",
                    **fields,
                )
            )
        await db.commit()
        return business.id, ids


@requires_db
async def test_the_sweep_removes_dead_and_unowned_objects_and_never_an_active_one(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business_id, ids = await business_with_assets(
        sessions,
        ready={"status": "ready"},
        uploading={"status": "uploading"},
        archived={"status": "ready", "archived_at": NOW},
        failed={"status": "failed"},
    )
    storage = FakeStorage()
    keep = [
        f"{ids['ready']}.heic",  # the original of a converted HEIC: no storage_path points at it
        f"{ids['ready']}.jpg",
        f"{ids['ready']}-llm.jpg",
        f"{ids['uploading']}.jpg",
    ]
    drop = [f"{ids['archived']}.jpg", f"{ids['archived']}-llm.jpg", f"{ids['failed']}.jpg"]
    unowned_old, unowned_young = f"{uuid.uuid4()}.jpg", f"{uuid.uuid4()}.jpg"
    for name in [*keep, *drop, unowned_old, unowned_young, "stray.txt"]:
        storage.put("assets", f"{business_id}/{name}", b"x")
    storage.age("assets", SIGNED_UPLOAD_URL_TTL + timedelta(minutes=1))
    # `age` moved everything back; the young object is made young again.
    storage.created_at[f"assets/{business_id}/{unowned_young}"] = datetime.now(UTC)

    removed = await sweep_orphaned_uploads(sessions, storage)

    assert removed == len(drop) + 1
    left = {key.removeprefix(f"assets/{business_id}/") for key in storage.objects}
    assert left == {*keep, unowned_young, "stray.txt"}


@dataclass
class StuckStorage(FakeStorage):
    """Storage whose listing hangs until `release` is set, or raises `StorageError` instead."""

    release: asyncio.Event = field(default_factory=asyncio.Event)
    fail: bool = False
    listings: int = 0

    async def list_objects(self, bucket: str, prefix: str) -> list[StoredObject]:
        self.listings += 1
        if self.fail:
            raise StorageError("supabase is down")
        await self.release.wait()
        return []


async def add_businesses(sessions: async_sessionmaker[AsyncSession], count: int) -> None:
    async with sessions() as db:
        db.add_all(Business(owner_phone=f"5989900000{n}") for n in range(count))
        await db.commit()


@requires_db
async def test_a_storage_failure_ends_the_round_after_one_listing(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_businesses(sessions, 3)
    storage = StuckStorage(fail=True)

    removed = await sweep_orphaned_uploads(sessions, storage)

    assert removed == 0
    assert storage.listings == 1


@requires_db
async def test_the_check_returns_at_once_and_skips_a_round_while_one_is_running(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_businesses(sessions, 2)
    storage = StuckStorage()
    check = upload_sweep(storage)

    await asyncio.wait_for(check(sessions), timeout=1)
    await asyncio.sleep(0.05)
    await asyncio.wait_for(check(sessions), timeout=1)
    await asyncio.sleep(0.05)
    storage.release.set()

    assert storage.listings == 1


@requires_db
async def test_a_stuck_sweep_does_not_delay_a_due_job(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    storage = StuckStorage()
    await add_businesses(sessions, 2)
    ran = asyncio.Event()

    async def job(context: JobContext, payload: dict[str, Any]) -> None:
        ran.set()

    async with sessions() as db:
        enqueue(db, "analyze_asset", None, {})
        await db.commit()
    model: Any = SequenceModel([])
    runner = JobRunner(
        sessions,
        {"analyze_asset": job},
        storage,
        FakeChannel(),
        model,
        poll_interval_s=0.01,
        checks=(PeriodicCheck("upload sweep", SWEEP_EVERY, upload_sweep(storage)),),
    )
    await runner.start()
    try:
        await asyncio.wait_for(ran.wait(), timeout=2)
    finally:
        storage.release.set()
        await runner.stop()
