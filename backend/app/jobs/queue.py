import uuid
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Job

JobKind = Literal["analyze_asset", "generate_brand"]


def enqueue(
    session: AsyncSession, kind: JobKind, business_id: uuid.UUID, payload: dict[str, Any]
) -> Job:
    """Add a queued job to the session; it is committed with the caller's changes.

    Nothing runs it yet: the job runner (T16) picks up queued rows.
    """
    job = Job(business_id=business_id, kind=kind, payload=payload)
    session.add(job)
    return job
