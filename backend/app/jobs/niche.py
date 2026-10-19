"""The weekly Niche Report (ADR 0025): the `generate_niche_report` job and the check that queues it.

A report is per niche, not per Business: what works in a niche is the same for every Business in
it, and each Business's own angle comes downstream, where the Brand Brain is. There is no cron: a
check every `CHECK_EVERY` (and once when the runner starts, so a deploy runs it at once) queues
the job for each niche with an active Business and no report for the current week. The weekly
run is silent: it saves the report and sends no Owner anything.
"""

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.data.niches import NICHES
from app.agents.niche_analyst import (
    HttpRedirectResolver,
    NicheAnalyst,
    NicheReport,
    week_start,
)
from app.db.models import Business, Job, NicheReportRow
from app.knowledge.db import niche_of
from app.llm.client import GroundedModel

from .queue import enqueue
from .runner import JobContext, JobFunction

logger = logging.getLogger(__name__)

KIND = "generate_niche_report"
CHECK_EVERY = timedelta(minutes=15)
# Onboarding is complete once the Owner confirmed the brand (conversation/brand.py).
ELIGIBLE_STATE = "active"
# Each attempt can run several billed Google searches: a failing call (a 429, fewer than 3
# sourced insights) is tried once more that week, then waits for next week.
MAX_ATTEMPTS_PER_WEEK = 2


def niche_report_job(
    model: GroundedModel, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> JobFunction:
    async def generate_niche_report(context: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        """Niche Analyst → this week's `niche_reports` row, replaced if a retry already wrote it."""
        niche = NICHES[payload["niche_id"]]
        today = local_today(niche.timezone, now())
        async with httpx.AsyncClient() as http:
            report = await NicheAnalyst(model, HttpRedirectResolver(http)).report(niche, today)
        async with context.sessions() as db:
            await save_report(db, niche.id, report)
            await db.commit()
        return {
            "niche_id": niche.id,
            "week_start": report.week_start.isoformat(),
            "insights": len(report.insights),
        }

    return generate_niche_report


async def save_report(db: AsyncSession, niche_id: str, report: NicheReport) -> None:
    """Insert the week's report, or replace it: a retry never hits the unique key."""
    statement = insert(NicheReportRow).values(
        niche_id=niche_id, week_start=report.week_start, report=report.model_dump(mode="json")
    )
    await db.execute(
        statement.on_conflict_do_update(
            constraint="uq_niche_reports_niche_id_week_start",
            set_={"report": statement.excluded.report},
        )
    )


async def enqueue_due_niche_reports(
    sessions: async_sessionmaker[AsyncSession], now: datetime | None = None
) -> int:
    """Queue `generate_niche_report` for each niche due this week; returns how many."""
    now = now or datetime.now(UTC)
    async with sessions() as db:
        businesses = (
            await db.scalars(select(Business).where(Business.onboarding_state == ELIGIBLE_STATE))
        ).all()
        niches = {niche.id: niche for niche in map(niche_of, businesses)}
        queued = 0
        for niche in sorted(niches.values(), key=lambda niche: niche.id):
            week = week_start(local_today(niche.timezone, now))
            has_report = await db.scalar(
                select(NicheReportRow.id).where(
                    NicheReportRow.niche_id == niche.id, NicheReportRow.week_start == week
                )
            )
            if has_report:
                continue
            statuses = (
                await db.scalars(
                    select(Job.status).where(
                        Job.kind == KIND,
                        Job.payload["niche_id"].astext == niche.id,
                        Job.created_at >= week_began_at(week, niche.timezone),
                    )
                )
            ).all()
            if not attempt_due(statuses):
                continue
            # No Business: the report serves all of the niche's (jobs.business_id is nullable).
            enqueue(db, KIND, None, {"niche_id": niche.id, "week_start": week.isoformat()})
            queued += 1
        await db.commit()
    if queued:
        logger.info("queued %d niche reports", queued)
    return queued


def attempt_due(statuses: Sequence[str]) -> bool:
    """Another attempt this week: none so far, or only failed ones and fewer than the cap."""
    return len(statuses) < MAX_ATTEMPTS_PER_WEEK and all(s == "failed" for s in statuses)


def local_today(timezone: str, now: datetime) -> date:
    return now.astimezone(ZoneInfo(timezone)).date()


def week_began_at(week: date, timezone: str) -> datetime:
    """Monday 00:00 in the niche's timezone: the jobs created since then count for this week."""
    return datetime.combine(week, time(), tzinfo=ZoneInfo(timezone))
