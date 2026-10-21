"""Whether this instance can serve Owners (api.md § Health): Railway's deploy healthcheck.

`/health` only says the process is up. The answer names each check, pass or fail, and the
deployed commit: never a setting, a hostname or an error, since anyone can call it.
"""

import asyncio
import logging
import time
from collections.abc import Callable
from datetime import timedelta
from functools import cache
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
DATABASE_RECHECK_S = 5.0

router = APIRouter()

Outcome = Literal["ok", "fail"]


class Readiness(BaseModel):
    status: Outcome
    checks: dict[str, Outcome]
    commit: str | None


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


class DatabaseProbe:
    """`database_answers`, asked at most once every `DATABASE_RECHECK_S`: anyone can call /ready,
    and each probe holds a connection the app serves Owners with. Calls that arrive while a probe
    runs wait for its answer, and a failure is reused like a success."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._sessions = sessions
        self._clock = clock
        self._lock = asyncio.Lock()
        self._answer = False
        self._recheck_at = float("-inf")

    async def answers(self) -> bool:
        async with self._lock:
            if self._clock() >= self._recheck_at:
                self._answer = await database_answers(self._sessions)
                self._recheck_at = self._clock() + DATABASE_RECHECK_S
            return self._answer


@cache
def database_probe(sessions: async_sessionmaker[AsyncSession]) -> DatabaseProbe:
    """One per sessionmaker, so every /ready call shares its last answer."""
    return DatabaseProbe(sessions)


def get_database(
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatabaseProbe | None:
    return database_probe(get_sessionmaker()) if settings.database_url else None


@router.get("/ready")
async def ready(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
    database: Annotated[DatabaseProbe | None, Depends(get_database)],
    runner: Annotated[JobRunner | None, Depends(get_job_runner)],
) -> Readiness:
    passed = {
        "database": database is not None and await database.answers(),
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
