import uuid
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import Business, Job

JobKind = Literal["analyze_asset", "generate_brand", "generate_niche_report", "import_instagram"]


def enqueue(
    session: AsyncSession, kind: JobKind, business_id: uuid.UUID | None, payload: dict[str, Any]
) -> Job:
    """Add a queued job to the session; the runner starts it once the caller commits."""
    job = Job(business_id=business_id, kind=kind, payload=payload)
    session.add(job)
    return job


def requeue(session: AsyncSession, failed: Job) -> Job:
    """A new queued job with the same kind and payload as a failed one, recorded on it as
    `retried_by` so it is retried only once (`retry:{job_id}`, `queue_stranded_brands`)."""
    job = Job(
        id=uuid.uuid4(),
        business_id=failed.business_id,
        kind=failed.kind,
        payload=dict(failed.payload),
    )
    session.add(job)
    failed.result = {**(failed.result or {}), "retried_by": str(job.id)}
    return job


async def retry_failed(
    sessions: async_sessionmaker[AsyncSession], owner_phone: str, job_id: str
) -> Job | None:
    """Requeue the Owner's failed job; None when it isn't theirs or didn't fail."""
    try:
        failed_id = uuid.UUID(job_id)
    except ValueError:
        return None
    async with sessions() as db:
        failed = await db.scalar(
            select(Job)
            .join(Business, Business.id == Job.business_id)
            .where(Job.id == failed_id, Job.status == "failed", Business.owner_phone == owner_phone)
            .with_for_update(of=Job)
        )
        if failed is None or (failed.result or {}).get("retried_by"):
            return None
        job = requeue(db, failed)
        await db.commit()
    return job
