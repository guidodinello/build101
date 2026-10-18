"""Background jobs in the backend process (ADR 0005, overview.md § Background jobs).

Jobs are rows in `jobs`. The runner polls for `queued` rows, so a job starts only after the
transaction that queued it commits, and the jobs queued before a restart still run.
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import Button, ChannelError, ChannelPort
from app.copy import messages_es
from app.db.models import Business, Job
from app.llm.client import ChatModel
from app.storage import StoragePort

logger = logging.getLogger(__name__)

MAX_CONCURRENT_JOBS = 4
POLL_INTERVAL_S = 1.0
# A job still running after this was left by a process that died (a deploy, a dev reload).
STALE_AFTER = timedelta(minutes=5)
STALE_CHECK_EVERY = timedelta(minutes=1)
MAX_ERROR_CHARS = 1000


@dataclass(frozen=True, slots=True)
class JobContext:
    job_id: uuid.UUID
    business_id: uuid.UUID | None
    sessions: async_sessionmaker[AsyncSession]
    storage: StoragePort
    channel: ChannelPort
    model: ChatModel


JobFunction = Callable[[JobContext, dict[str, Any]], Awaitable[dict[str, Any] | None]]


class JobRunner:
    """Runs `jobs` rows with their function from `jobs`, at most `max_concurrent` at a time.

    A failed job of a kind in `notify_on_failure` sends `job_failed` with a `retry:{job_id}`
    button to the Business's Owner; other failures are only logged.
    """

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        jobs: dict[str, JobFunction],
        storage: StoragePort,
        channel: ChannelPort,
        model: ChatModel,
        notify_on_failure: frozenset[str] = frozenset(),
        max_concurrent: int = MAX_CONCURRENT_JOBS,
        poll_interval_s: float = POLL_INTERVAL_S,
    ) -> None:
        self._sessions = sessions
        self._jobs = jobs
        self._storage = storage
        self._channel = channel
        self._model = model
        self._notify_on_failure = notify_on_failure
        self._max_concurrent = max_concurrent
        self._poll_interval_s = poll_interval_s
        self._running: set[asyncio.Task[None]] = set()
        self._running_ids: set[uuid.UUID] = set()
        self._poller: asyncio.Task[None] | None = None

    async def start(self) -> None:
        await self.fail_stale()
        self._poller = asyncio.create_task(self._poll())

    async def stop(self) -> None:
        if self._poller:
            self._poller.cancel()
        for task in self._running:
            task.cancel()
        await asyncio.gather(*self._running, return_exceptions=True)

    async def fail_stale(self, older_than: timedelta = STALE_AFTER) -> int:
        """Mark as failed the jobs a previous process left `running` (no retries in the MVP).

        This process's own jobs are skipped however long they take: they are alive.
        """
        cutoff = datetime.now(UTC) - older_than
        async with self._sessions() as db:
            result = await db.execute(
                update(Job)
                .where(
                    Job.status == "running",
                    Job.started_at < cutoff,
                    Job.id.not_in(self._running_ids),
                )
                .values(
                    status="failed", error="interrupted by a restart", finished_at=datetime.now(UTC)
                )
            )
            await db.commit()
        if result.rowcount:
            logger.warning("marked %d stale running jobs as failed", result.rowcount)
        return result.rowcount

    async def run_due(self) -> int:
        """Claim as many queued jobs as there are free slots and start them."""
        free = self._max_concurrent - len(self._running)
        if free <= 0:
            return 0
        async with self._sessions() as db:
            jobs = (
                await db.scalars(
                    select(Job)
                    .where(Job.status == "queued")
                    .order_by(Job.created_at)
                    .limit(free)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for job in jobs:
                job.status = "running"
                job.started_at = datetime.now(UTC)
            await db.commit()
        for job in jobs:
            self._running_ids.add(job.id)
            task = asyncio.create_task(self._run(job.id, job.kind, job.business_id, job.payload))
            self._running.add(task)
            task.add_done_callback(self._running.discard)
        return len(jobs)

    async def join(self) -> None:
        """Wait for the running jobs (tests)."""
        while self._running:
            await asyncio.gather(*self._running)

    async def _poll(self) -> None:
        last_stale_check = datetime.now(UTC)
        while True:
            try:
                if datetime.now(UTC) - last_stale_check >= STALE_CHECK_EVERY:
                    last_stale_check = datetime.now(UTC)
                    await self.fail_stale()
                await self.run_due()
            except Exception:
                logger.exception("polling for jobs failed")
            await asyncio.sleep(self._poll_interval_s)

    async def _run(
        self, job_id: uuid.UUID, kind: str, business_id: uuid.UUID | None, payload: dict[str, Any]
    ) -> None:
        context = JobContext(
            job_id, business_id, self._sessions, self._storage, self._channel, self._model
        )
        result: dict[str, Any] | None = None
        error: str | None = None
        try:
            function = self._jobs.get(kind)
            if function is None:
                raise LookupError(f"no function for job kind {kind!r}")
            result = await function(context, payload)
        except Exception as exc:
            # The task's boundary: nobody awaits it, so the row and the log carry the error.
            logger.exception("job %s (%s) failed", job_id, kind)
            error = repr(exc)[:MAX_ERROR_CHARS]
        async with self._sessions() as db:
            # Only a row still `running`: anything else was decided elsewhere and stays.
            await db.execute(
                update(Job)
                .where(Job.id == job_id, Job.status == "running")
                .values(
                    status="failed" if error else "succeeded",
                    result=result,
                    error=error,
                    finished_at=datetime.now(UTC),
                )
            )
            await db.commit()
        self._running_ids.discard(job_id)
        logger.info("job %s (%s): %s", job_id, kind, "failed" if error else "succeeded")
        if error and kind in self._notify_on_failure and business_id:
            await self._tell_owner(job_id, business_id)

    async def _tell_owner(self, job_id: uuid.UUID, business_id: uuid.UUID) -> None:
        async with self._sessions() as db:
            business = await db.get_one(Business, business_id)
        if business.channel != "whatsapp":
            return
        try:
            await self._channel.send_buttons(
                business.owner_phone,
                messages_es.JOB_FAILED,
                [Button(id=f"retry:{job_id}", title=messages_es.BUTTON_RETRY)],
            )
        except ChannelError:
            logger.warning("could not tell the Owner that job %s failed", job_id, exc_info=True)
