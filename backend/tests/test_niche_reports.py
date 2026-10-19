"""The weekly Niche Report per niche: the due check, the job and its readers (ADR 0025)."""

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.data.niches import CURATED_WOOD_FURNITURE_UY
from app.agents.niche_analyst import (
    InsightDraft,
    NicheReport,
    NicheReportDraft,
    trend_notes,
    week_start,
)
from app.conversation.context import BusinessContexts
from app.conversation.library import NicheTrends
from app.db.models import Business, Job, NicheReportRow
from app.jobs.niche import (
    KIND,
    attempt_due,
    enqueue_due_niche_reports,
    latest_niche_report,
    local_today,
    niche_report_job,
    save_report,
    week_began_at,
)
from app.jobs.runner import JobContext, JobRunner, PeriodicCheck
from app.llm.client import Content, Grounded, Tool
from tests.conftest import requires_db
from tests.fakes import FakeChannel, FakeStorage, SequenceModel

NICHE = CURATED_WOOD_FURNITURE_UY
MONTEVIDEO = "America/Montevideo"
# Wednesday 2026-10-21, 15:00 UTC (12:00 in Montevideo): the week of Monday 2026-10-19
WEDNESDAY = datetime(2026, 10, 21, 15, tzinfo=UTC)
MONDAY = date(2026, 10, 19)


def report(week: date, insight: str = "Las tiendas muestran la veta.") -> NicheReport:
    return NicheReport.model_validate(
        {
            "week_start": week.isoformat(),
            "summary": "Pega la madera cálida.",
            "insights": [
                {
                    "kind": "theme",
                    "insight": insight,
                    "post_idea": None,
                    "source_urls": ["https://kateiuy.lovable.app"],
                }
            ]
            * 3,
        }
    )


@dataclass
class FakeGroundedModel:
    insight: str = "Las tiendas muestran la veta."
    requests: list[str] = field(default_factory=list)

    async def grounded[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: str,
        tools: list[Tool],
    ) -> Grounded[T]:
        self.requests.append(content[0]["text"])
        sourced = InsightDraft(
            kind="theme",
            insight=self.insight,
            post_idea="",
            source_urls=["https://kateiuy.lovable.app"],
        )
        draft = NicheReportDraft(summary="Pega la madera.", insights=[sourced] * 3)
        return Grounded(draft, [])  # type: ignore[arg-type]


# Pure date math


def test_the_week_starts_on_the_local_monday() -> None:
    assert local_today(MONTEVIDEO, WEDNESDAY) == date(2026, 10, 21)
    # Monday 02:00 UTC is still Sunday 23:00 in Montevideo: last week
    assert local_today(MONTEVIDEO, datetime(2026, 10, 19, 2, tzinfo=UTC)) == date(2026, 10, 18)
    assert week_began_at(MONDAY, MONTEVIDEO) == datetime(2026, 10, 19, 3, tzinfo=UTC)


@pytest.mark.parametrize(
    ("statuses", "due"),
    [
        ([], True),
        (["failed"], True),
        (["failed", "failed"], False),
        (["queued"], False),
        (["running"], False),
        (["succeeded"], False),
    ],
)
def test_an_attempt_is_due_only_after_failures_and_under_the_cap(
    statuses: list[str], due: bool
) -> None:
    assert attempt_due(statuses) is due


# Against the database. Jobs get created_at = now() from Postgres, so the tests that count them
# use the real clock.


def this_monday() -> date:
    return week_start(local_today(MONTEVIDEO, datetime.now(UTC)))


async def add_business(
    sessions: async_sessionmaker[AsyncSession], phone: str, state: str = "active"
) -> Business:
    async with sessions() as db:
        business = Business(owner_phone=phone, name="Katei", onboarding_state=state)
        db.add(business)
        await db.commit()
        return business


async def niche_jobs(sessions: async_sessionmaker[AsyncSession]) -> list[Job]:
    async with sessions() as db:
        return list((await db.scalars(select(Job).where(Job.kind == KIND))).all())


async def add_job(
    sessions: async_sessionmaker[AsyncSession], status: str, created_at: datetime
) -> None:
    async with sessions() as db:
        db.add(
            Job(
                kind=KIND,
                payload={"niche_id": NICHE.id},
                status=status,
                created_at=created_at,
            )
        )
        await db.commit()


@requires_db
async def test_no_active_business_queues_nothing(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_business(sessions, "59899000001", state="awaiting_brand_confirmation")

    assert await enqueue_due_niche_reports(sessions, WEDNESDAY) == 0
    assert await niche_jobs(sessions) == []


@requires_db
async def test_one_job_per_niche_however_many_businesses(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_business(sessions, "59899000001")
    await add_business(sessions, "59899000002")

    assert await enqueue_due_niche_reports(sessions) == 1
    assert await enqueue_due_niche_reports(sessions) == 0  # the first is queued

    [job] = await niche_jobs(sessions)
    assert job.business_id is None
    assert job.payload == {"niche_id": NICHE.id, "week_start": this_monday().isoformat()}


@requires_db
async def test_a_failed_job_gets_one_more_attempt_that_week(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_business(sessions, "59899000001")
    await add_job(sessions, "failed", datetime.now(UTC))

    assert await enqueue_due_niche_reports(sessions) == 1
    async with sessions() as db:
        await db.execute(Job.__table__.update().values(status="failed"))
        await db.commit()

    assert await enqueue_due_niche_reports(sessions) == 0  # 2 failed: capped
    assert len(await niche_jobs(sessions)) == 2


@requires_db
async def test_last_weeks_attempts_dont_count(sessions: async_sessionmaker[AsyncSession]) -> None:
    await add_business(sessions, "59899000001")
    last_sunday_night = week_began_at(MONDAY, MONTEVIDEO) - timedelta(minutes=1)
    await add_job(sessions, "failed", last_sunday_night)
    await add_job(sessions, "failed", last_sunday_night)

    assert await enqueue_due_niche_reports(sessions, WEDNESDAY) == 1


@requires_db
async def test_a_niche_with_this_weeks_report_is_not_due(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_business(sessions, "59899000001")
    async with sessions() as db:
        await save_report(db, NICHE.id, report(MONDAY))
        await db.commit()

    assert await enqueue_due_niche_reports(sessions, WEDNESDAY) == 0
    # Next Monday it is due again
    assert await enqueue_due_niche_reports(sessions, WEDNESDAY + timedelta(days=5)) == 1


@requires_db
async def test_the_job_writes_the_niches_report_and_a_retry_replaces_it(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    def context() -> JobContext:
        return JobContext(
            uuid.uuid4(), None, sessions, FakeStorage(), FakeChannel(), SequenceModel([])
        )

    payload = {"niche_id": NICHE.id, "week_start": MONDAY.isoformat()}
    first = FakeGroundedModel("Primera versión.")
    result = await niche_report_job(first, now=lambda: WEDNESDAY)(context(), payload)
    retry = niche_report_job(FakeGroundedModel("Segunda versión."), now=lambda: WEDNESDAY)
    await retry(context(), payload)

    assert result == {"niche_id": NICHE.id, "week_start": "2026-10-19", "insights": 3}
    assert "Today is 2026-10-21" in first.requests[0]
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(NicheReportRow)) == 1
        latest = await latest_niche_report(db, NICHE.id)
    assert latest is not None
    assert latest.insights[0].insight == "Segunda versión."


@requires_db
async def test_readers_get_the_latest_report_of_the_businesss_niche(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_business(sessions, "59899000001")
    async with sessions() as db:
        await save_report(db, NICHE.id, report(MONDAY - timedelta(days=7), "Vieja."))
        await save_report(db, NICHE.id, report(MONDAY, "Nueva."))
        await save_report(db, "another-niche", report(MONDAY + timedelta(days=7), "Otro rubro."))
        await db.commit()
    expected = trend_notes(report(MONDAY, "Nueva."))

    context = await BusinessContexts(sessions).load("59899000001")

    assert context.trend_notes == expected
    assert await NicheTrends(sessions).latest("59899000001") == expected
    assert await NicheTrends(sessions).latest("59899000009") is None


@requires_db
async def test_before_the_first_report_there_are_no_trend_notes(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_business(sessions, "59899000001")

    assert (await BusinessContexts(sessions).load("59899000001")).trend_notes is None
    assert await NicheTrends(sessions).latest("59899000001") is None


@requires_db
async def test_the_runner_runs_its_checks_when_it_starts_and_survives_a_failing_one(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    calls: list[str] = []

    async def failing(_: Any) -> None:
        calls.append("failing")
        raise RuntimeError("boom")

    async def queueing(_: Any) -> None:
        calls.append("queueing")

    checks = (
        PeriodicCheck("failing", timedelta(minutes=15), failing),
        PeriodicCheck("queueing", timedelta(minutes=15), queueing),
    )
    runner = JobRunner(
        sessions,
        {},
        FakeStorage(),
        FakeChannel(),
        SequenceModel([]),
        poll_interval_s=0.01,
        checks=checks,
    )
    await runner.start()
    await asyncio.sleep(0.1)
    await runner.stop()

    # Once at start, not again on each poll within 15 minutes
    assert calls == ["failing", "queueing"]
