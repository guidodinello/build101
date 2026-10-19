"""The sweep of orphaned onboarding uploads (#134): Storage objects no active asset owns.

A signed upload URL outlives a DELETE of its asset, and an asset that ends `failed` keeps what
was uploaded, so objects can pile up in the `assets` bucket under `{business_id}/`. Every
`SWEEP_EVERY` (and once when the runner starts) this removes, per Business:

- the objects of an asset that is archived or `failed`, and
- the objects with no asset row at all, once older than the upload ticket TTL. Rows can trail
  their object (the WhatsApp photo keeper and the Instagram import upload first), so a young
  object is left alone; an old one can no longer be PUT again, its signed URL has expired.

An object is protected by the asset id in its name, not by `storage_path`: the original of a
converted HEIC and the `-llm` copy belong to an active asset though no row points at them.
Names that don't parse are never touched. Assets still `uploading` are out of scope: a late
`/complete` still works, and removing the object would turn it into a 409.
"""

import logging
import re
import uuid
from collections.abc import Awaitable, Callable, Collection
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import BrandAsset, Business
from app.onboarding.uploads import EXTENSIONS
from app.storage import ASSETS_BUCKET, SIGNED_UPLOAD_URL_TTL, StoragePort, StoredObject

logger = logging.getLogger(__name__)

SWEEP_EVERY = timedelta(hours=1)
# `{asset_id}.{ext}` (an original or its JPEG) or `{asset_id}-llm.jpg` (the agents' copy)
OBJECT_NAME = re.compile(
    rf"^(?P<id>[0-9a-f]{{8}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{4}}-[0-9a-f]{{12}})"
    rf"(?:-llm\.jpg|\.(?:{'|'.join(EXTENSIONS.values())}))$"
)


def asset_id_of(name: str) -> uuid.UUID | None:
    match = OBJECT_NAME.match(name)
    return uuid.UUID(match["id"]) if match else None


def orphaned(
    objects: Collection[StoredObject],
    dead_assets: Collection[uuid.UUID],
    active_assets: Collection[uuid.UUID],
    now: datetime,
) -> list[str]:
    """The names to delete. `dead_assets` are archived or failed, `active_assets` the rest."""
    doomed: list[str] = []
    for item in objects:
        asset_id = asset_id_of(item.name)
        if asset_id is None or asset_id in active_assets:
            continue
        if asset_id in dead_assets or now - item.created_at > SIGNED_UPLOAD_URL_TTL:
            doomed.append(item.name)
    return doomed


async def sweep_orphaned_uploads(
    sessions: async_sessionmaker[AsyncSession],
    storage: StoragePort,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    """Remove the orphaned objects of every Business; the number removed. One Business failing
    doesn't stop the others."""
    async with sessions() as db:
        business_ids = (await db.scalars(select(Business.id))).all()
    removed = 0
    for business_id in business_ids:
        try:
            removed += await _sweep_business(sessions, storage, business_id, now())
        except Exception:
            logger.exception("sweeping the uploads of business %s failed", business_id)
    if removed:
        logger.info("upload sweep removed %d orphaned objects", removed)
    return removed


async def _sweep_business(
    sessions: async_sessionmaker[AsyncSession],
    storage: StoragePort,
    business_id: uuid.UUID,
    now: datetime,
) -> int:
    objects = await storage.list_objects(ASSETS_BUCKET, str(business_id))
    if not objects:
        return 0
    # Read the rows after the listing: an asset created in between is then seen as active.
    async with sessions() as db:
        rows = (
            await db.execute(
                select(BrandAsset.id, BrandAsset.status, BrandAsset.archived_at).where(
                    BrandAsset.business_id == business_id
                )
            )
        ).all()
    dead = {row.id for row in rows if row.archived_at is not None or row.status == "failed"}
    active = {row.id for row in rows} - dead
    names = orphaned(objects, dead, active, now)
    if names:
        await storage.remove(ASSETS_BUCKET, [f"{business_id}/{name}" for name in names])
    return len(names)


def upload_sweep(
    storage: StoragePort,
) -> Callable[[async_sessionmaker[AsyncSession]], Awaitable[object]]:
    """The `PeriodicCheck.run` of the sweep."""

    async def run(sessions: async_sessionmaker[AsyncSession]) -> int:
        return await sweep_orphaned_uploads(sessions, storage)

    return run
