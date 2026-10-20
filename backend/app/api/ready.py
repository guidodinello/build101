"""Whether this instance can serve Owners (api.md § Health): Railway's deploy healthcheck.

`/health` only says the process is up. The answer names each check, pass or fail, and the
deployed commit: never a setting, a hostname or an error, since anyone can call it.
"""

import asyncio
import logging
from datetime import timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings, get_settings
from app.db.session import get_sessionmaker
from app.jobs.runner import JobRunner

logger = logging.getLogger(__name__)

# The poller goes round every second; a last round this old means it is stuck or gone
POLLED_WITHIN = timedelta(seconds=30)
DATABASE_TIMEOUT_S = 5.0

router = APIRouter()

Outcome = Literal["ok", "fail"]


class Readiness(BaseModel):
    status: Outcome
    checks: dict[str, Outcome]
    commit: str | None


def get_database(
    settings: Annotated[Settings, Depends(get_settings)],
) -> async_sessionmaker[AsyncSession] | None:
    return get_sessionmaker() if settings.database_url else None


def get_job_runner(request: Request) -> JobRunner | None:
    """The runner the app's lifespan started, or None when it is off."""
    return getattr(request.app.state, "job_runner", None)


async def database_answers(sessions: async_sessionmaker[AsyncSession]) -> bool:
    try:
        async with asyncio.timeout(DATABASE_TIMEOUT_S), sessions() as db:
            await db.execute(text("select 1"))
    except Exception:
        logger.warning("ready: the database did not answer", exc_info=True)
        return False
    return True


@router.get("/ready")
async def ready(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    sessions: Annotated[async_sessionmaker[AsyncSession] | None, Depends(get_database)],
    runner: Annotated[JobRunner | None, Depends(get_job_runner)],
) -> Readiness:
    passed = {
        "database": sessions is not None and await database_answers(sessions),
        "job_runner": runner is not None and runner.polled_within(POLLED_WITHIN),
        "publisher": settings.publisher != "mock",
    }
    is_ready = all(passed.values())
    if not is_ready:
        response.status_code = 503
    return Readiness(
        status="ok" if is_ready else "fail",
        checks={name: "ok" if ok else "fail" for name, ok in passed.items()},
        commit=settings.railway_git_commit_sha,
    )
