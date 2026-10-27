"""Background jobs in the backend process (ADR 0005, overview.md § Background jobs).

Jobs are rows in `jobs`. The runner polls for `queued` rows, so a job starts only after the
transaction that queued it commits, and the jobs queued before a restart still run. A job a
restart interrupts goes back to the queue once if it is safe to repeat (#178).
"""

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.background import BackgroundWork
from app.channels.base import ChannelPort
from app.conversation.events import JobFailed, Notify
from app.db.models import Business, Job
from app.llm.client import ChatModel
from app.llm.ledger import scoped
from app.storage import StoragePort

logger = logging.getLogger(__name__)

MAX_CONCURRENT_JOBS = 4
POLL_INTERVAL_S = 1.0
# A job still running after this was left by a process that died (a crash, out of memory).
STALE_AFTER = timedelta(minutes=5)
STALE_CHECK_EVERY = timedelta(minutes=1)
# An interrupted job runs once more, then fails: a job that kills its process (out of memory)
# takes down at most one more.
MAX_ATTEMPTS = 2
INTERRUPTED = "interrupted by a restart"
MAX_ERROR_CHARS = 1000


@dataclass(frozen=True, slots=True)
class JobContext:
    job_id: uuid.UUID
    business_id: uuid.UUID | None
    sessions: async_sessionmaker[AsyncSession]
    storage: StoragePort
    channel: ChannelPort
    model: ChatModel
    notify: Notify


JobFunction = Callable[[JobContext, dict[str, Any]], Awaitable[dict[str, Any] | None]]
# What the runner undoes for the Business of a failed job, e.g. the state a brand revision left.
Undo = Callable[[async_sessionmaker[AsyncSession], uuid.UUID], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class PeriodicCheck:
    """Work the poller runs on its first round and then every `every` (when None, on each round
    until it succeeds once: once per process), e.g. queueing the weekly jobs. The poller awaits a
    check before it claims jobs, so a check must return at once: it queues, or starts
    housekeeping that needs no row of its own as a background task (the orphaned-upload sweep,
    jobs/uploads.py)."""

    name: str
    every: timedelta | None
    run: Callable[[async_sessionmaker[AsyncSession]], Awaitable[object]]


class JobRunner:
    """Runs `jobs` rows with their function from `jobs`, at most `max_concurrent` at a time.

    A failed job's Business first gets its kind's `undo`. Then a kind in `notify_on_failure`
    raises `JobFailed` (its `retry:{job_id}` button goes with it) for the Business's Owner through
    `notify`; other failures are only logged.

    A job is interrupted when the shutdown cancels it or its process dies. One of a kind in
    `requeue_if_interrupted` goes back to the queue, up to `MAX_ATTEMPTS` runs in all. Any other
    is abandoned: failed by the runner, with the same `undo` and `JobFailed` as a failure of its
    own.
    """

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        jobs: dict[str, JobFunction],
        storage: StoragePort,
        channel: ChannelPort,
        model: ChatModel,
        notify: Notify,
        notify_on_failure: frozenset[str] = frozenset(),
        requeue_if_interrupted: frozenset[str] = frozenset(),
        undo: Mapping[str, Undo] | None = None,
        max_concurrent: int = MAX_CONCURRENT_JOBS,
        poll_interval_s: float = POLL_INTERVAL_S,
        checks: tuple[PeriodicCheck, ...] = (),
        *,
        background: BackgroundWork,
    ) -> None:
        self._sessions = sessions
        self._jobs = jobs
        self._storage = storage
        self._channel = channel
        self._model = model
        self._notify = notify
        self._notify_on_failure = notify_on_failure
        self._requeue_if_interrupted = requeue_if_interrupted
        self._undo = undo or {}
        self._max_concurrent = max_concurrent
        self._poll_interval_s = poll_interval_s
        self._checks = checks
        self._background = background
        self._running: set[asyncio.Task[None]] = set()
        self._running_ids: set[uuid.UUID] = set()
        self._stopping = False
        self._poller: asyncio.Task[None] | None = None
        self._last_poll: datetime | None = None

    def polled_within(self, window: timedelta) -> bool:
        """Whether the poller is alive and last polled for jobs less than `window` ago (/ready)."""
        return (
            self._poller is not None
            and not self._poller.done()
            and self._last_poll is not None
            and datetime.now(UTC) - self._last_poll < window
        )

    async def start(self) -> None:
        _, abandoned = await self._take_stale(STALE_AFTER)
        # Awaited, unlike the poller's: the poller's first round runs the startup check of stuck
        # brands, which would queue a copy of a brand job abandoned here before its Reintentar is
        # out. Still started as background work, which logs a failure instead of ending startup.
        await asyncio.gather(*(self._start_after_failure(job) for job in abandoned))
        self._poller = self._background.start_service(self._poll(), "job poller")

    def stop(self) -> None:
        """Claim no new job (the shutdown): the poller ends after its round. The jobs already
        running go on; the shutdown's `BackgroundWork.drain` waits for them and the poller."""
        self._stopping = True

    async def recover_stale(self, older_than: timedelta = STALE_AFTER) -> int:
        """Requeue or abandon the jobs a process that died left `running`; returns how many.

        This process's own jobs are skipped however long they take: they are alive.
        """
        stale, abandoned = await self._take_stale(older_than)
        for job in abandoned:
            # Not in the poller's round: `JobFailed` waits for any turn the Owner is in.
            self._start_after_failure(job)
        return stale

    async def _take_stale(self, older_than: timedelta) -> tuple[int, list[Job]]:
        """Requeue or abandon the stale jobs; returns how many there were and the abandoned ones."""
        cutoff = datetime.now(UTC) - older_than
        async with self._sessions() as db:
            stale = (
                await db.scalars(
                    select(Job)
                    .where(
                        Job.status == "running",
                        Job.started_at < cutoff,
                        Job.id.not_in(self._running_ids),
                    )
                    .with_for_update(skip_locked=True)
                )
            ).all()
            return len(stale), await self._recover(db, stale)

    def _start_after_failure(self, job: Job) -> asyncio.Task[None]:
        return self._background.start(
            self._after_failure(job.id, job.kind, job.business_id), _task_name(job)
        )

    async def run_due(self) -> int:
        """Claim as many queued jobs as there are free slots and start them; none once stopped."""
        free = self._max_concurrent - len(self._running)
        if free <= 0 or self._stopping:
            return 0
        async with self._sessions() as db:
            jobs = (
                await db.scalars(
                    select(Job)
                    # Only kinds this process can run: during a deploy the old instance keeps
                    # polling for a few seconds and must leave a new kind to the new one.
                    .where(Job.status == "queued", Job.kind.in_(self._jobs))
                    .order_by(Job.created_at)
                    .limit(free)
                    .with_for_update(skip_locked=True)
                )
            ).all()
            for job in jobs:
                job.status = "running"
                job.started_at = datetime.now(UTC)
                job.attempts += 1
            await db.commit()
        for job in jobs:
            self._running_ids.add(job.id)
            task = self._background.start(
                self._run(job.id, job.kind, job.business_id, job.payload, job.attempts),
                _task_name(job),
            )
            self._running.add(task)
            task.add_done_callback(self._running.discard)
        return len(jobs)

    async def _poll(self) -> None:
        last_stale_check = datetime.now(UTC)
        last_checked: dict[str, datetime] = {}
        while not self._stopping:
            await self._run_checks(last_checked)
            try:
                if datetime.now(UTC) - last_stale_check >= STALE_CHECK_EVERY:
                    last_stale_check = datetime.now(UTC)
                    await self.recover_stale()
                await self.run_due()
                self._last_poll = datetime.now(UTC)
            except Exception:
                logger.exception("polling for jobs failed")
            await asyncio.sleep(self._poll_interval_s)

    async def _run_checks(self, last_checked: dict[str, datetime]) -> None:
        """Each periodic check that is due; one failing doesn't stop the others or the jobs."""
        for check in self._checks:
            last = last_checked.get(check.name)
            if last is not None and (check.every is None or datetime.now(UTC) - last < check.every):
                continue
            started = datetime.now(UTC)
            try:
                await check.run(self._sessions)
            except Exception:
                logger.exception("periodic check %s failed", check.name)
                if check.every is None:
                    continue
            last_checked[check.name] = started

    async def _run(
        self,
        job_id: uuid.UUID,
        kind: str,
        business_id: uuid.UUID | None,
        payload: dict[str, Any],
        attempt: int,
    ) -> None:
        context = JobContext(
            job_id,
            business_id,
            self._sessions,
            self._storage,
            self._channel,
            self._model,
            self._notify,
        )
        result: dict[str, Any] | None = None
        error: str | None = None
        try:
            function = self._jobs.get(kind)
            if function is None:
                raise LookupError(f"no function for job kind {kind!r}")
            with scoped(job_id=job_id, business_id=business_id):
                result = await function(context, payload)
        except asyncio.CancelledError:
            await self._interrupted(job_id, attempt)
            raise
        except Exception as exc:
            # The task's boundary: nobody awaits it, so the row and the log carry the error.
            logger.exception("job %s (%s) failed", job_id, kind)
            error = repr(exc)[:MAX_ERROR_CHARS]
        async with self._sessions() as db:
            # Only while the row is still this run's: once another instance took the job for dead,
            # this run's outcome is dropped, a failure's `undo` and `JobFailed` with it.
            owned = await db.scalar(
                update(Job)
                .where(Job.id == job_id, Job.status == "running", Job.attempts == attempt)
                .values(
                    status="failed" if error else "succeeded",
                    result=result,
                    error=error,
                    finished_at=datetime.now(UTC),
                )
                .returning(Job.id)
            )
            await db.commit()
        self._running_ids.discard(job_id)
        if owned is None:
            logger.warning(
                "job %s (%s) attempt %d was taken for dead elsewhere: its outcome is dropped",
                job_id,
                kind,
                attempt,
            )
            return
        logger.info("job %s (%s): %s", job_id, kind, "failed" if error else "succeeded")
        if error:
            await self._after_failure(job_id, kind, business_id)

    async def _interrupted(self, job_id: uuid.UUID, attempt: int) -> None:
        """The shutdown cancelled this run at the drain's deadline: requeue or abandon its job."""
        async with self._sessions() as db:
            job = await db.scalar(
                select(Job)
                .where(Job.id == job_id, Job.status == "running", Job.attempts == attempt)
                .with_for_update()
            )
            abandoned = await self._recover(db, [job] if job else [])
        for failed in abandoned:
            await self._after_failure(failed.id, failed.kind, failed.business_id)

    async def _recover(self, db: AsyncSession, interrupted: Sequence[Job]) -> list[Job]:
        """Put each interrupted job back in the queue or abandon it; commits `db` and returns the
        abandoned ones."""
        for job in interrupted:
            if job.kind in self._requeue_if_interrupted and job.attempts < MAX_ATTEMPTS:
                job.status = "queued"
                job.started_at = None
            else:
                job.status = "failed"
                job.error = INTERRUPTED
                job.finished_at = datetime.now(UTC)
        await db.commit()
        for job in interrupted:
            logger.warning(
                "job %s (%s) interrupted on attempt %d: %s",
                job.id,
                job.kind,
                job.attempts,
                "queued again" if job.status == "queued" else "failed",
            )
        return [job for job in interrupted if job.status == "failed"]

    async def _after_failure(
        self, job_id: uuid.UUID, kind: str, business_id: uuid.UUID | None
    ) -> None:
        """The kind's `undo`, then the Owner's `JobFailed`; nothing for a job of no Business."""
        if business_id is None:
            return
        if undo := self._undo.get(kind):
            await undo(self._sessions, business_id)
        if kind in self._notify_on_failure:
            await self._tell_owner(job_id, kind, business_id)

    async def _tell_owner(self, job_id: uuid.UUID, kind: str, business_id: uuid.UUID) -> None:
        async with self._sessions() as db:
            business = await db.get_one(Business, business_id)
        if business.channel != "whatsapp":
            return
        try:
            await self._notify(business.owner_phone, JobFailed(job_id, kind), self._channel)
        except Exception:
            logger.warning("could not tell the Owner that job %s failed", job_id, exc_info=True)
            return
        async with self._sessions() as db:
            # So the startup check of stuck brands leaves this one to the Owner's Reintentar.
            await db.execute(
                update(Job).where(Job.id == job_id).values(retry_offered_at=datetime.now(UTC))
            )
            await db.commit()


def _task_name(job: Job) -> str:
    """The job's ids, as the logs show them; a niche report belongs to no Business."""
    name = f"job {job.id} ({job.kind})"
    return f"{name} for business {job.business_id}" if job.business_id else name
