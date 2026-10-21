"""Jobs a restart interrupts (#178): one safe to repeat goes back to the queue once, and an
abandoned one fails as if it had failed itself. A Business still stuck generating its brand gets
a new brand job when the runner starts. The shutdown's drain is in test_jobs.py."""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.base import Button, ChannelError
from app.conversation.brand import BrandFlow
from app.conversation.events import JobRetried, StaleButton
from app.conversation.history import DbHistory
from app.conversation.outbound import FixedReplies
from app.copy import messages_es
from app.db.models import Business, Job
from app.jobs.brand import generate_brand, queue_stranded_brands
from app.jobs.queue import requeue, retry_failed
from app.jobs.runner import INTERRUPTED, JobContext, PeriodicCheck
from tests.conftest import migration_statements, requires_db
from tests.fakes import EventLog, FakeChannel, SequenceModel, brand_brain
from tests.test_jobs import PHONE, add_business, job_row, queue, router, runner

pytestmark = requires_db

JOB_RECOVERY = Path(__file__).parents[1] / "migrations" / "versions" / "0008_job_recovery.sql"
SUMMARY = "• *Cómo hablamos:* cálidos"


async def add_job(
    sessions: async_sessionmaker[AsyncSession],
    business: Business,
    kind: str = "generate_brand",
    **fields: Any,
) -> Job:
    async with sessions() as db:
        job = Job(business_id=business.id, kind=kind, **fields)
        db.add(job)
        await db.commit()
        return job


def left_running(attempts: int) -> dict[str, Any]:
    """A row its process left behind when it died, after claiming it `attempts` times."""
    return {
        "status": "running",
        "attempts": attempts,
        "started_at": datetime.now(UTC) - timedelta(minutes=10),
    }


async def brand_jobs(sessions: async_sessionmaker[AsyncSession], business: Business) -> list[Job]:
    async with sessions() as db:
        jobs = await db.scalars(
            select(Job)
            .where(Job.business_id == business.id, Job.kind == "generate_brand")
            .order_by(Job.created_at)
        )
        return list(jobs.all())


async def stuck(context: JobContext, payload: dict[str, Any]) -> None:
    await asyncio.Event().wait()


async def test_a_brand_job_stopped_by_the_shutdown_is_queued_and_the_next_process_sends_it(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    job_id = await queue(sessions, "generate_brand", business)
    gated = SequenceModel([brand_brain()], gate=asyncio.Event())
    first, background = runner(sessions, {"generate_brand": generate_brand}, FakeChannel(), gated)
    assert await first.run_due() == 1

    first.stop()
    await asyncio.wait_for(background.drain(timeout_s=0.1), timeout=2)

    requeued = await job_row(sessions, job_id)
    assert (requeued.status, requeued.attempts, requeued.started_at) == ("queued", 1, None)
    channel, model = FakeChannel(), SequenceModel([brand_brain(whatsapp_summary=SUMMARY)])
    second, background = runner(sessions, {"generate_brand": generate_brand}, channel, model)
    assert await second.run_due() == 1
    await background.join()

    assert (await job_row(sessions, job_id)).status == "succeeded"
    assert [body for _, body, _ in channel.buttons] == [messages_es.brand_summary("Katei", SUMMARY)]


async def test_a_brand_job_the_shutdown_stops_a_second_time_fails_and_offers_reintentar(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel = await add_business(sessions), FakeChannel()
    job = await add_job(sessions, business, attempts=1)
    jobs, background = runner(sessions, {"generate_brand": stuck}, channel)
    assert await jobs.run_due() == 1

    jobs.stop()
    await asyncio.wait_for(background.drain(timeout_s=0.1), timeout=2)

    failed = await job_row(sessions, job.id)
    assert (failed.status, failed.error, failed.attempts) == ("failed", INTERRUPTED, 2)
    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{job.id}"])]
    assert failed.retry_offered_at is not None


async def test_a_brand_job_left_running_by_a_dead_process_runs_once_more_then_fails(
    sessions: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    business, channel = await add_business(sessions), FakeChannel()
    job = await add_job(sessions, business, **left_running(attempts=1))
    survivor, survivor_work = runner(sessions, {"generate_brand": stuck}, channel)

    with caplog.at_level(logging.WARNING, logger="app.jobs.runner"):
        assert await survivor.recover_stale() == 1
    requeued = await job_row(sessions, job.id)
    assert (requeued.status, requeued.started_at) == ("queued", None)
    assert f"job {job.id} (generate_brand) interrupted on attempt 1: queued again" in caplog.text

    assert await survivor.run_due() == 1
    async with sessions() as db:
        # The survivor dies on it too: its run is still going when the next process looks.
        await db.execute(update(Job).where(Job.id == job.id).values(**left_running(attempts=2)))
        await db.commit()
    jobs, background = runner(sessions, {}, channel)
    assert await jobs.recover_stale() == 1
    await background.join()
    await survivor_work.stop()

    failed = await job_row(sessions, job.id)
    assert (failed.status, failed.error, failed.attempts) == ("failed", INTERRUPTED, 2)
    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{job.id}"])]
    async with sessions() as db:
        assert (await db.get_one(Business, business.id)).onboarding_state == "generating_brand"

    tapped = await router(sessions).handle(PHONE, f"retry:{job.id}", FakeChannel(), EventLog())

    assert tapped == JobRetried("generate_brand")
    assert [(j.status, j.attempts) for j in await brand_jobs(sessions, business)] == [
        ("failed", 2),
        ("queued", 0),
    ]


@pytest.mark.parametrize("state", ["awaiting_brand_confirmation", "active"])
async def test_an_abandoned_brand_revision_puts_the_business_back(
    sessions: async_sessionmaker[AsyncSession], state: str
) -> None:
    business, channel = await add_business(sessions, state=state), FakeChannel()
    assert await BrandFlow(sessions).revise(PHONE, "más formales")
    async with sessions() as db:
        await db.execute(
            update(Job).where(Job.business_id == business.id).values(**left_running(attempts=2))
        )
        await db.commit()
    jobs, background = runner(sessions, {}, channel)

    assert await jobs.recover_stale() == 1
    await background.join()

    async with sessions() as db:
        restored = await db.get_one(Business, business.id)
    assert (restored.onboarding_state, restored.conversation_state) == (state, {})
    [revision] = await brand_jobs(sessions, business)
    assert (revision.status, revision.payload) == ("failed", {"correction": "más formales"})
    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{revision.id}"])]


async def test_the_stale_check_doesnt_wait_for_a_turn_the_owner_is_in(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel, history = await add_business(sessions), FakeChannel(), DbHistory(sessions)
    job = await add_job(sessions, business, **left_running(attempts=2))
    jobs, background = runner(sessions, {}, channel, notify=FixedReplies(history))

    async with history.lock(PHONE):
        assert await asyncio.wait_for(jobs.recover_stale(), timeout=1) == 1
        assert (await job_row(sessions, job.id)).status == "failed"
    await background.join()

    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{job.id}"])]


async def test_an_interrupted_photo_analysis_runs_once_more_and_tells_no_one(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel = await add_business(sessions), FakeChannel()
    first = await add_job(sessions, business, "analyze_asset", **left_running(attempts=1))
    second = await add_job(sessions, business, "analyze_asset", **left_running(attempts=2))
    jobs, background = runner(sessions, {}, channel)

    assert await jobs.recover_stale() == 2
    await background.join()

    assert (await job_row(sessions, first.id)).status == "queued"
    assert (await job_row(sessions, second.id)).status == "failed"
    assert channel.buttons == []


async def test_an_interrupted_instagram_import_fails_without_running_again(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel = await add_business(sessions), FakeChannel()
    left = await add_job(sessions, business, "import_instagram", **left_running(attempts=1))
    stopped = await add_job(sessions, business, "import_instagram")
    jobs, background = runner(sessions, {"import_instagram": stuck}, channel)

    assert await jobs.recover_stale() == 1
    assert await jobs.run_due() == 1
    jobs.stop()
    await asyncio.wait_for(background.drain(timeout_s=0.1), timeout=2)

    for job in (left, stopped):
        row = await job_row(sessions, job.id)
        assert (row.status, row.error, row.attempts) == ("failed", INTERRUPTED, 1)
    assert channel.buttons == []


async def look_dead(sessions: async_sessionmaker[AsyncSession], job_id: uuid.UUID) -> None:
    """The old instance's run (attempt 1) started long enough ago for the new one to take it for
    dead."""
    async with sessions() as db:
        await db.execute(update(Job).where(Job.id == job_id).values(**left_running(attempts=1)))
        await db.commit()


async def test_a_run_another_instance_took_for_dead_no_longer_owns_its_row(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # A deploy's overlap: the old instance is still on a revision the new one requeued and claimed.
    business, old_channel = await add_business(sessions, state="active"), FakeChannel()
    assert await BrandFlow(sessions).revise(PHONE, "más formales")
    [job] = await brand_jobs(sessions, business)
    old_gate, new_gate = asyncio.Event(), asyncio.Event()

    async def fails(context: JobContext, payload: dict[str, Any]) -> None:
        await old_gate.wait()
        raise RuntimeError("the old run fails")

    async def succeeds(context: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        await new_gate.wait()
        return {"run": "new"}

    old, old_work = runner(sessions, {"generate_brand": fails}, old_channel)
    assert await old.run_due() == 1
    await look_dead(sessions, job.id)
    new, new_work = runner(sessions, {"generate_brand": succeeds}, FakeChannel())
    assert await new.recover_stale() == 1
    assert await new.run_due() == 1

    old_gate.set()
    await old_work.join()
    taken = await job_row(sessions, job.id)
    assert (taken.status, taken.attempts, taken.retry_offered_at) == ("running", 2, None)
    assert old_channel.buttons == []
    async with sessions() as db:
        assert (await db.get_one(Business, business.id)).onboarding_state == "generating_brand"
    new_gate.set()
    await new_work.join()

    done = await job_row(sessions, job.id)
    assert (done.status, done.result, done.attempts) == ("succeeded", {"run": "new"}, 2)


async def test_the_old_instances_shutdown_leaves_a_job_the_new_one_took_over(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, old_channel = await add_business(sessions), FakeChannel()
    job_id = await queue(sessions, "generate_brand", business)
    old, old_work = runner(sessions, {"generate_brand": stuck}, old_channel)
    assert await old.run_due() == 1
    await look_dead(sessions, job_id)
    new, new_work = runner(sessions, {"generate_brand": stuck}, FakeChannel())
    assert await new.recover_stale() == 1
    assert await new.run_due() == 1

    old.stop()
    await asyncio.wait_for(old_work.drain(timeout_s=0.1), timeout=2)

    taken = await job_row(sessions, job_id)
    assert (taken.status, taken.attempts) == ("running", 2)
    assert old_channel.buttons == []
    await new_work.stop()


async def test_a_job_queued_again_after_an_interruption_has_no_reintentar_to_tap(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    job = await add_job(sessions, business, **left_running(attempts=1))
    await runner(sessions, {}, FakeChannel())[0].recover_stale()

    tapped = await router(sessions).handle(PHONE, f"retry:{job.id}", FakeChannel(), EventLog())

    assert tapped == StaleButton()
    assert [j.status for j in await brand_jobs(sessions, business)] == ["queued"]


async def test_an_ordinary_brand_failure_is_left_to_the_owners_reintentar(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel = await add_business(sessions), FakeChannel()
    job_id = await queue(sessions, "generate_brand", business)
    jobs, background = runner(
        sessions, {"generate_brand": generate_brand}, channel, SequenceModel([])
    )

    await jobs.run_due()
    await background.join()

    failed = await job_row(sessions, job_id)
    assert (failed.status, failed.retry_offered_at is not None) == ("failed", True)
    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{job_id}"])]
    assert await queue_stranded_brands(sessions) == 0
    async with sessions() as db:
        assert (await db.get_one(Business, business.id)).onboarding_state == "generating_brand"


class NoButtonsChannel(FakeChannel):
    """WhatsApp down: the failure message never reaches the Owner."""

    async def send_buttons(self, to: str, body: str, buttons: list[Button], **headers: Any) -> str:
        raise ChannelError("boom")


async def test_a_brand_failure_the_owner_never_heard_of_gets_a_new_job_at_startup(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    job_id = await queue(sessions, "generate_brand", business)
    jobs, background = runner(
        sessions, {"generate_brand": generate_brand}, NoButtonsChannel(), SequenceModel([])
    )
    await jobs.run_due()
    await background.join()

    assert (await job_row(sessions, job_id)).retry_offered_at is None
    assert await queue_stranded_brands(sessions) == 1
    assert [j.status for j in await brand_jobs(sessions, business)] == ["failed", "queued"]


async def test_at_startup_a_business_stuck_with_no_brand_job_gets_exactly_one(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    check = PeriodicCheck("stranded brands", None, queue_stranded_brands)
    jobs, background = runner(sessions, {}, FakeChannel(), poll_interval_s=0.01, checks=(check,))

    await jobs.start()
    await asyncio.sleep(0.1)
    jobs.stop()
    await background.drain(timeout_s=1)

    [job] = await brand_jobs(sessions, business)
    assert (job.status, job.payload) == ("queued", {})
    assert await queue_stranded_brands(sessions) == 0


async def test_a_brand_job_abandoned_at_startup_is_left_to_the_owners_reintentar(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel = await add_business(sessions), FakeChannel()
    job = await add_job(sessions, business, **left_running(attempts=2))
    check = PeriodicCheck("stranded brands", None, queue_stranded_brands)
    jobs, background = runner(sessions, {}, channel, poll_interval_s=0.01, checks=(check,))

    await jobs.start()
    await asyncio.sleep(0.1)
    jobs.stop()
    await background.drain(timeout_s=1)

    [failed] = await brand_jobs(sessions, business)
    assert (failed.status, failed.error, failed.result) == ("failed", INTERRUPTED, None)
    assert failed.retry_offered_at is not None
    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{job.id}"])]

    tapped = await router(sessions).handle(PHONE, f"retry:{job.id}", FakeChannel(), EventLog())

    assert tapped == JobRetried("generate_brand")


async def test_a_brand_the_old_stale_check_failed_gets_exactly_one_new_job(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # What the stale check left before #178: failed, and no message to the Owner.
    business = await add_business(sessions)
    stale = await add_job(
        sessions,
        business,
        status="failed",
        error=INTERRUPTED,
        attempts=1,
        payload={"correction": "más formales"},
    )

    assert await queue_stranded_brands(sessions) == 1
    assert await queue_stranded_brands(sessions) == 0

    old, new = await brand_jobs(sessions, business)
    assert old.result == {"retried_by": str(new.id)}
    assert (new.status, new.payload) == ("queued", {"correction": "más formales"})
    assert await retry_failed(sessions, PHONE, str(stale.id)) is None


@pytest.mark.parametrize(
    "fields",
    [
        {"status": "queued"},
        {"status": "running", "attempts": 1, "started_at": datetime.now(UTC)},
        {"status": "failed", "error": "RuntimeError()", "retry_offered_at": datetime.now(UTC)},
    ],
    ids=["queued", "running", "failed-with-reintentar"],
)
async def test_the_startup_check_leaves_a_brand_job_that_will_still_end(
    sessions: async_sessionmaker[AsyncSession], fields: dict[str, Any]
) -> None:
    business = await add_business(sessions)
    await add_job(sessions, business, **fields)

    assert await queue_stranded_brands(sessions) == 0
    assert len(await brand_jobs(sessions, business)) == 1


async def test_the_startup_check_leaves_a_business_past_generating_its_brand(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions, state="awaiting_brand_confirmation")
    await add_job(sessions, business, status="failed", error=INTERRUPTED, attempts=1)

    assert await queue_stranded_brands(sessions) == 0


async def test_the_startup_check_and_a_reintentar_tap_queue_one_job_between_them(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # The failure message went out but its record didn't: both see a failed job to retry.
    business = await add_business(sessions)
    failed = await add_job(sessions, business, status="failed", error="RuntimeError()")

    async with sessions() as tap:
        # `retry_failed` midway: the job locked and its copy added, not committed yet.
        requeue(tap, await tap.get_one(Job, failed.id, with_for_update=True))
        check = asyncio.create_task(queue_stranded_brands(sessions))
        await asyncio.sleep(0.2)
        assert not check.done()
        await tap.commit()

    assert await check == 0
    assert [j.status for j in await brand_jobs(sessions, business)] == ["failed", "queued"]
    assert await retry_failed(sessions, PHONE, str(failed.id)) is None


async def test_the_startup_check_waits_for_a_route_that_holds_the_business(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # The Owner writes in that instant: the onboarding gate locks their Business for a moment.
    business = await add_business(sessions)

    async with sessions() as route:
        await route.get_one(Business, business.id, with_for_update=True)
        check = asyncio.create_task(queue_stranded_brands(sessions))
        await asyncio.sleep(0.2)
        assert not check.done()
        await route.rollback()

    assert await check == 1


async def test_a_check_with_no_period_runs_until_it_succeeds_once(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    runs: list[datetime] = []

    async def flaky(sessions: async_sessionmaker[AsyncSession]) -> None:
        runs.append(datetime.now(UTC))
        if len(runs) == 1:
            raise ConnectionError("a blip at startup")

    jobs, background = runner(
        sessions,
        {},
        FakeChannel(),
        poll_interval_s=0.01,
        checks=(PeriodicCheck("flaky", None, flaky),),
    )
    await jobs.start()
    await asyncio.sleep(0.1)
    jobs.stop()
    await background.drain(timeout_s=1)

    assert len(runs) == 2


async def test_the_migration_counts_past_runs_and_marks_no_reintentar_as_sent(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    finished = datetime(2026, 10, 19, 12, tzinfo=UTC)
    async with sessions() as db:
        await db.execute(
            text("alter table jobs drop column attempts, drop column retry_offered_at")
        )
        whatsapp = await db.scalar(
            text("insert into businesses (owner_phone) values ('598991') returning id")
        )
        simulator = await db.scalar(
            text(
                "insert into businesses (owner_phone, channel) values ('sim-1', 'simulator')"
                " returning id"
            )
        )
        rows = {
            "queued": (whatsapp, "generate_brand", "queued", None, None),
            "succeeded": (whatsapp, "analyze_asset", "succeeded", None, finished),
            "brand failed": (whatsapp, "generate_brand", "failed", "RuntimeError()", finished),
            "brand stale": (whatsapp, "generate_brand", "failed", INTERRUPTED, finished),
            "photo failed": (whatsapp, "analyze_asset", "failed", "RuntimeError()", finished),
            "simulator": (simulator, "generate_brand", "failed", "RuntimeError()", finished),
        }
        ids = {}
        for name, (business_id, kind, status, error, at) in rows.items():
            ids[name] = await db.scalar(
                text(
                    "insert into jobs (business_id, kind, status, error, started_at, finished_at)"
                    " values (:business_id, :kind, :status, :error, :at, :at) returning id"
                ),
                {
                    "business_id": business_id,
                    "kind": kind,
                    "status": status,
                    "error": error,
                    "at": at,
                },
            )
        for statement in migration_statements(JOB_RECOVERY):
            await db.execute(text(statement))
        await db.commit()

    async with sessions() as db:
        jobs = {name: await db.get_one(Job, job_id) for name, job_id in ids.items()}
    assert {name: job.attempts for name, job in jobs.items()} == {
        "queued": 0,
        "succeeded": 1,
        "brand failed": 1,
        "brand stale": 1,
        "photo failed": 1,
        "simulator": 1,
    }
    assert [name for name, job in jobs.items() if job.retry_offered_at] == []
