import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.schemas import AssetAnalysis
from app.background import BackgroundWork
from app.channels.base import Button, ChannelError
from app.conversation.brand import BrandFlow
from app.conversation.button_router import ButtonRouter
from app.conversation.events import (
    BrandConfirmed,
    BrandFixAsked,
    BrandSummaryReady,
    JobFailed,
    JobRetried,
    StaleButton,
)
from app.conversation.factory import ChatParts, build_chat
from app.conversation.history import DbHistory
from app.conversation.outbound import FixedReplies
from app.copy import messages_es
from app.db.models import (
    AssetProduct,
    BrandAsset,
    BrandBrainVersion,
    Business,
    Job,
    Product,
)
from app.imagegen.mock import MockImageGen
from app.jobs.asset import analyze_asset
from app.jobs.brand import generate_brand
from app.jobs.queue import enqueue, retry_failed
from app.jobs.runner import JobContext, JobRunner
from app.jobs.setup import NOTIFY_ON_FAILURE, REQUEUE_IF_INTERRUPTED, UNDO
from app.llm.client import Step, user_step
from app.media.public import PublicImages, PublicVideos
from app.posts.lifecycle import PostLifecycle
from app.publishing.mock import MOCK_ACCOUNT_ID, MockPublisher
from app.rendering.mock import MockRenderer
from tests.conftest import make_image, requires_db
from tests.fakes import EventLog, FakeChannel, FakeStorage, SequenceModel, brand_brain

pytestmark = requires_db

PHONE = "59899123456"


def photo_analysis() -> AssetAnalysis:
    return AssetAnalysis(
        description="Mesa de roble en un living.",
        subjects=["mesa"],
        product_ids=[],
        quality="high",
        orientation="portrait",
        has_people=False,
        has_text=False,
        dominant_colors=[],
        best_for=["hero"],
        safe_crop_focus="center",
    )


async def add_business(
    sessions: async_sessionmaker[AsyncSession], state: str = "generating_brand"
) -> Business:
    async with sessions() as db:
        business = Business(
            owner_phone=PHONE,
            name="Katei",
            category="Muebles y deco",
            one_liner="Muebles restaurados",
            location="Montevideo",
            onboarding_state=state,
            onboarding_data={
                "brand": {"three_words": ["a", "b", "c"], "colors": ["#2f3e2c"]},
                "preferences": {"goal": "sales", "posts_per_week": 3, "avoid": "precios"},
            },
        )
        db.add(business)
        await db.commit()
        return business


def runner(
    sessions: async_sessionmaker[AsyncSession],
    jobs: dict[str, Any],
    channel: FakeChannel,
    model: Any = None,
    storage: FakeStorage | None = None,
    notify: Any = None,
    **options: Any,
) -> tuple[JobRunner, BackgroundWork]:
    background = BackgroundWork()
    return JobRunner(
        sessions,
        jobs,
        storage or FakeStorage(),
        channel,
        model or SequenceModel([]),
        notify or FixedReplies(DbHistory(sessions)),
        NOTIFY_ON_FAILURE,
        REQUEUE_IF_INTERRUPTED,
        UNDO,
        background=background,
        **options,
    ), background


async def queue(
    sessions: async_sessionmaker[AsyncSession], kind: str, business: Business, **payload: Any
) -> uuid.UUID:
    async with sessions() as db:
        job = enqueue(db, kind, business.id, payload)  # type: ignore[arg-type]
        await db.commit()
        return job.id


async def job_row(sessions: async_sessionmaker[AsyncSession], job_id: uuid.UUID) -> Job:
    async with sessions() as db:
        return await db.get_one(Job, job_id)


async def test_a_queued_job_runs_and_records_its_result(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    seen: list[dict[str, Any]] = []

    async def ok(context: JobContext, payload: dict[str, Any]) -> dict[str, Any]:
        seen.append(payload)
        return {"done": True}

    job_id = await queue(sessions, "analyze_asset", business, n=1)
    jobs, background = runner(sessions, {"analyze_asset": ok}, FakeChannel())

    assert await jobs.run_due() == 1
    await background.join()

    job = await job_row(sessions, job_id)
    assert (job.status, job.result, job.error) == ("succeeded", {"done": True}, None)
    assert job.started_at and job.finished_at
    assert seen == [{"n": 1}]


async def test_a_failed_job_tells_the_owner_with_a_retry_button(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)

    async def boom(context: JobContext, payload: dict[str, Any]) -> None:
        raise RuntimeError("kaput")

    job_id = await queue(sessions, "generate_brand", business)
    channel = FakeChannel()
    jobs, background = runner(sessions, {"generate_brand": boom}, channel)

    await jobs.run_due()
    await background.join()

    job = await job_row(sessions, job_id)
    assert job.status == "failed"
    assert "kaput" in (job.error or "")
    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{job_id}"])]


async def test_a_failed_job_raises_job_failed_for_its_owner(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)

    async def boom(context: JobContext, payload: dict[str, Any]) -> None:
        raise RuntimeError("kaput")

    job_id = await queue(sessions, "generate_brand", business)
    events = EventLog()
    jobs, background = runner(sessions, {"generate_brand": boom}, FakeChannel(), notify=events)

    await jobs.run_due()
    await background.join()

    assert events.events == [(PHONE, JobFailed(job_id, "generate_brand"))]


async def test_other_failures_are_only_logged(sessions: async_sessionmaker[AsyncSession]) -> None:
    business = await add_business(sessions)

    async def boom(context: JobContext, payload: dict[str, Any]) -> None:
        raise RuntimeError("kaput")

    job_id = await queue(sessions, "analyze_asset", business)
    channel = FakeChannel()
    jobs, background = runner(sessions, {"analyze_asset": boom}, channel)

    await jobs.run_due()
    await background.join()

    assert (await job_row(sessions, job_id)).status == "failed"
    assert channel.buttons == []


async def test_a_kind_this_process_cant_run_stays_queued(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # The old instance during a deploy: it must not claim, and fail, a kind only the new one knows
    business = await add_business(sessions)
    job_id = await queue(sessions, "generate_niche_report", business)
    jobs, background = runner(sessions, {"analyze_asset": analyze_asset}, FakeChannel())

    assert await jobs.run_due() == 0
    assert (await job_row(sessions, job_id)).status == "queued"


async def test_only_free_slots_are_claimed(sessions: async_sessionmaker[AsyncSession]) -> None:
    business = await add_business(sessions)

    async def ok(context: JobContext, payload: dict[str, Any]) -> None:
        return None

    for _ in range(3):
        await queue(sessions, "analyze_asset", business)
    jobs, background = runner(sessions, {"analyze_asset": ok}, FakeChannel(), max_concurrent=2)

    assert await jobs.run_due() == 2
    await background.join()
    assert await jobs.run_due() == 1
    await background.join()


async def test_once_stopped_the_poller_claims_no_new_job_and_ends_on_its_own(
    sessions: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    business, ran = await add_business(sessions), asyncio.Event()

    async def ok(context: JobContext, payload: dict[str, Any]) -> None:
        ran.set()

    before = await queue(sessions, "analyze_asset", business)
    jobs, background = runner(sessions, {"analyze_asset": ok}, FakeChannel(), poll_interval_s=0.01)
    await jobs.start()
    await asyncio.wait_for(ran.wait(), timeout=2)

    jobs.stop()
    after = await queue(sessions, "analyze_asset", business)
    await asyncio.sleep(0.1)
    with caplog.at_level(logging.WARNING, logger="app.background"):
        await background.drain(timeout_s=1)

    assert (await job_row(sessions, before)).status == "succeeded"
    assert (await job_row(sessions, after)).status == "queued"
    assert await jobs.run_due() == 0
    assert "shutdown deadline passed" not in caplog.text


async def test_a_brand_being_written_at_shutdown_still_reaches_the_owner(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel, gate = await add_business(sessions), FakeChannel(), asyncio.Event()
    model = SequenceModel([brand_brain(whatsapp_summary="• *Cómo hablamos:* cálidos")], gate=gate)
    job_id = await queue(sessions, "generate_brand", business)
    jobs, background = runner(sessions, {"generate_brand": generate_brand}, channel, model)
    assert await jobs.run_due() == 1

    jobs.stop()
    asyncio.get_running_loop().call_later(0.05, gate.set)
    await background.drain(timeout_s=5)

    assert (await job_row(sessions, job_id)).status == "succeeded"
    assert [body for _, body, _ in channel.buttons] == [
        messages_es.brand_summary("Katei", "• *Cómo hablamos:* cálidos")
    ]


async def test_a_job_still_running_at_the_deadline_is_cancelled_and_logged_with_its_ids(
    sessions: async_sessionmaker[AsyncSession], caplog: pytest.LogCaptureFixture
) -> None:
    business = await add_business(sessions)

    async def stuck(context: JobContext, payload: dict[str, Any]) -> None:
        await asyncio.Event().wait()

    job_id = await queue(sessions, "generate_brand", business)
    jobs, background = runner(sessions, {"generate_brand": stuck}, FakeChannel())
    assert await jobs.run_due() == 1

    jobs.stop()
    with caplog.at_level(logging.WARNING, logger="app.background"):
        await asyncio.wait_for(background.drain(timeout_s=0.1), timeout=2)

    assert f"job {job_id} (generate_brand) for business {business.id}" in caplog.text
    assert (await job_row(sessions, job_id)).status == "queued"


async def test_only_jobs_left_running_long_enough_are_taken_for_dead(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    async with sessions() as db:
        stale = Job(
            business_id=business.id,
            kind="analyze_asset",
            status="running",
            attempts=1,
            started_at=datetime.now(UTC) - timedelta(minutes=10),
        )
        fresh = Job(
            business_id=business.id,
            kind="analyze_asset",
            status="running",
            attempts=1,
            started_at=datetime.now(UTC),
        )
        db.add_all([stale, fresh])
        await db.commit()

    assert await runner(sessions, {}, FakeChannel())[0].recover_stale() == 1
    assert (await job_row(sessions, stale.id)).status == "queued"
    assert (await job_row(sessions, fresh.id)).status == "running"


async def test_a_failed_job_is_retried_once_and_only_by_its_owner(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    async with sessions() as db:
        failed = Job(
            business_id=business.id, kind="generate_brand", status="failed", payload={"a": 1}
        )
        db.add(failed)
        await db.commit()

    stranger = await retry_failed(sessions, "59800000000", str(failed.id))
    first = await retry_failed(sessions, PHONE, str(failed.id))
    second = await retry_failed(sessions, PHONE, str(failed.id))

    assert stranger is None
    assert first and (first.kind, first.payload, first.status) == (
        "generate_brand",
        {"a": 1},
        "queued",
    )
    assert second is None
    assert await retry_failed(sessions, PHONE, "not-a-uuid") is None


async def add_photo(
    sessions: async_sessionmaker[AsyncSession], business: Business, storage: FakeStorage
) -> BrandAsset:
    async with sessions() as db:
        product = Product(business_id=business.id, name="Mesa", description="Roble")
        asset = BrandAsset(
            business_id=business.id,
            kind="photo",
            source="web",
            status="ready",
            storage_path=f"{business.id}/a.jpg",
            mime_type="image/jpeg",
            owner_hint="la nueva",
        )
        db.add_all([product, asset])
        await db.flush()
        db.add(AssetProduct(asset_id=asset.id, product_id=product.id, source="owner"))
        await db.commit()
    storage.put("assets", f"{business.id}/{asset.id}-llm.jpg", make_image((100, 100)))
    return asset


def context(
    sessions: async_sessionmaker[AsyncSession],
    business: Business,
    model: Any,
    storage: FakeStorage | None = None,
    channel: FakeChannel | None = None,
    notify: Any = None,
) -> JobContext:
    return JobContext(
        uuid.uuid4(),
        business.id,
        sessions,
        storage or FakeStorage(),
        channel or FakeChannel(),
        model,
        notify or EventLog(),
    )


async def test_analyze_asset_saves_the_analysis_of_the_agents_copy(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, storage = await add_business(sessions), FakeStorage()
    asset = await add_photo(sessions, business, storage)
    model = SequenceModel([photo_analysis()])

    await analyze_asset(context(sessions, business, model, storage), {"asset_id": str(asset.id)})
    again = await analyze_asset(
        context(sessions, business, model, storage), {"asset_id": str(asset.id)}
    )

    async with sessions() as db:
        saved = await db.get_one(BrandAsset, asset.id)
    assert saved.analysis and saved.analysis["description"] == "Mesa de roble en un living."
    assert again == {"skipped": "already analyzed"}
    assert '<owner_hint>\n"la nueva"\n</owner_hint>' in model.contents[0][0]["text"]


async def test_analyze_asset_fails_without_the_agents_copy(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, storage = await add_business(sessions), FakeStorage()
    asset = await add_photo(sessions, business, storage)
    storage.objects.clear()

    with pytest.raises(FileNotFoundError):
        await analyze_asset(
            context(sessions, business, SequenceModel([]), storage), {"asset_id": str(asset.id)}
        )


async def test_analyze_asset_skips_a_photo_archived_after_the_job_started(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    class ArchivedMidJob(FakeStorage):
        """The Owner's ✕ lands after the job read the asset: its files are gone."""

        async def download(
            self, bucket: str, path: str, *, max_bytes: int | None = None
        ) -> bytes | None:
            async with sessions() as db:
                (await db.get_one(BrandAsset, asset.id)).archived_at = datetime.now(UTC)
                await db.commit()
            self.objects.clear()
            return await super().download(bucket, path, max_bytes=max_bytes)

    business, storage = await add_business(sessions), ArchivedMidJob()
    asset = await add_photo(sessions, business, storage)

    result = await analyze_asset(
        context(sessions, business, SequenceModel([]), storage), {"asset_id": str(asset.id)}
    )

    assert result == {"skipped": "archived while queued"}


async def test_generate_brand_saves_a_version_and_raises_the_summary_event(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, events = await add_business(sessions), EventLog()
    model = SequenceModel([brand_brain(whatsapp_summary="• *Cómo hablamos:* cálidos")])

    result = await generate_brand(context(sessions, business, model, notify=events), {})

    assert result == {"version": 1}
    async with sessions() as db:
        saved = await db.get_one(Business, business.id)
        version = await db.scalar(select(BrandBrainVersion))
    assert saved.onboarding_state == "awaiting_brand_confirmation"
    assert version and (version.version, version.reason) == (1, "onboarding")
    assert version.data["constraints"][0] == "precios"
    assert events.events == [(PHONE, BrandSummaryReady("Katei", "• *Cómo hablamos:* cálidos"))]


async def test_concurrent_brand_generations_save_distinct_versions(
    sessions: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import app.jobs.brand as brand_job

    business = await add_business(sessions)
    both_generated = asyncio.Event()
    generation_count = 0

    async def coordinated_generation(model: Any, inputs: Any) -> Any:
        nonlocal generation_count
        generation_count += 1
        if generation_count == 2:
            both_generated.set()
        await asyncio.wait_for(both_generated.wait(), timeout=5)
        return brand_brain()

    monkeypatch.setattr(
        brand_job, "write_brand_brain", AsyncMock(side_effect=coordinated_generation)
    )

    first, second = await asyncio.gather(
        generate_brand(context(sessions, business, SequenceModel([])), {}),
        generate_brand(context(sessions, business, SequenceModel([])), {}),
    )

    assert {first["version"], second["version"]} == {1, 2}

    async with sessions() as db:
        versions = (
            await db.scalars(select(BrandBrainVersion.version).order_by(BrandBrainVersion.version))
        ).all()

    assert versions == [1, 2]


async def test_the_summary_reaches_the_owner_and_the_history_through_fixed_replies(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel = await add_business(sessions), FakeChannel()
    model = SequenceModel([brand_brain(whatsapp_summary="• *Cómo hablamos:* cálidos")])
    history = DbHistory(sessions)

    await generate_brand(
        context(sessions, business, model, channel=channel, notify=FixedReplies(history)), {}
    )

    event = BrandSummaryReady("Katei", "• *Cómo hablamos:* cálidos")
    assert channel.buttons == [
        (PHONE, messages_es.brand_summary("Katei", event.summary), ["brand_ok", "brand_fix"])
    ]
    # The orchestrator knows what the Owner was just shown (ADR 0030).
    assert await history.get(PHONE) == [user_step(event.note())]


class FailsOnceChannel(FakeChannel):
    """The first buttons message doesn't go out, like a WhatsApp outage that clears up."""

    failed = False

    async def send_buttons(self, to: str, body: str, buttons: list[Button], **headers: Any) -> str:
        if not self.failed:
            self.failed = True
            raise ChannelError("boom")
        return await super().send_buttons(to, body, buttons, **headers)


class FailsOnceHistory(DbHistory):
    """The first read of the history fails, like a database blip while the summary is told."""

    failed = False

    async def get(self, sender: str) -> list[Step]:
        if not self.failed:
            self.failed = True
            raise SQLAlchemyError("boom")
        return await super().get(sender)


async def test_a_summary_that_fails_before_the_send_fails_the_job_and_offers_a_retry(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel = await add_business(sessions), FakeChannel()
    chat = build_chat(
        ChatParts(
            model=SequenceModel([]),
            image_gen=MockImageGen(),
            renderer=MockRenderer(),
            publisher=MockPublisher(delay_s=0),
            images=PublicImages(),
            videos=PublicVideos(),
            background=BackgroundWork(),
            public_backend_url="https://backend.test",
            account_id=MOCK_ACCOUNT_ID,
            assistant_name="Mora",
            max_photo_mb=10,
            max_posts_per_day=5,
            max_videos_per_day=2,
            history=FailsOnceHistory(sessions),
        )
    )
    job_id = await queue(sessions, "generate_brand", business)
    jobs, background = runner(
        sessions,
        {"generate_brand": generate_brand},
        channel,
        SequenceModel([brand_brain()]),
        notify=chat.notify,
    )

    await jobs.run_due()
    await background.join()

    assert (await job_row(sessions, job_id)).status == "failed"
    # The Owner never got the summary, and is told with the retry.
    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{job_id}"])]


async def test_a_summary_that_cant_be_delivered_fails_the_job_and_offers_a_retry(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business, channel = await add_business(sessions), FailsOnceChannel()
    job_id = await queue(sessions, "generate_brand", business)
    jobs, background = runner(
        sessions, {"generate_brand": generate_brand}, channel, SequenceModel([brand_brain()])
    )

    await jobs.run_due()
    await background.join()

    assert (await job_row(sessions, job_id)).status == "failed"
    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{job_id}"])]
    # The summary never reached the Owner, so the history has no note about it.
    assert await DbHistory(sessions).get(PHONE) == [
        user_step(JobFailed(job_id, "generate_brand").note())
    ]


async def test_a_correction_makes_a_new_version_from_the_previous_one(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    model = SequenceModel([brand_brain(), brand_brain(whatsapp_summary="• formales")])
    await generate_brand(context(sessions, business, model), {})

    await generate_brand(context(sessions, business, model), {"correction": "más formales"})

    async with sessions() as db:
        versions = (
            await db.scalars(select(BrandBrainVersion).order_by(BrandBrainVersion.version))
        ).all()
    assert [(v.version, v.reason) for v in versions] == [(1, "onboarding"), (2, "correction")]
    assert '<correction>\n"más formales"\n</correction>' in model.contents[1][0]["text"]


def router(sessions: async_sessionmaker[AsyncSession]) -> ButtonRouter:
    return ButtonRouter(  # type: ignore[arg-type]
        PostLifecycle(), maker=None, publisher=None, sessions=sessions, brand=BrandFlow(sessions)
    )


async def test_brand_ok_activates_the_business_once(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions, state="awaiting_brand_confirmation")
    buttons = router(sessions)

    first = await buttons.handle(PHONE, "brand_ok", FakeChannel(), EventLog())
    second = await buttons.handle(PHONE, "brand_ok", FakeChannel(), EventLog())

    assert (first, second) == (BrandConfirmed(), StaleButton())
    async with sessions() as db:
        assert (await db.get_one(Business, business.id)).onboarding_state == "active"


async def test_a_brand_change_queues_revise_mode_once(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions, state="awaiting_brand_confirmation")
    buttons = router(sessions)
    flow = BrandFlow(sessions)

    asked = await buttons.handle(PHONE, "brand_fix", FakeChannel(), EventLog())
    taken = await flow.revise(PHONE, "somos más formales")
    again = await flow.revise(PHONE, "y otra cosa")

    assert (asked, taken, again) == (BrandFixAsked(), True, False)
    async with sessions() as db:
        jobs = (await db.scalars(select(Job).where(Job.business_id == business.id))).all()
        updated = await db.get_one(Business, business.id)
    # The old summary's buttons go stale while the revised one is made.
    assert (updated.onboarding_state, updated.conversation_state) == (
        "generating_brand",
        {"resume_state": "awaiting_brand_confirmation"},
    )
    assert await buttons.handle(PHONE, "brand_ok", FakeChannel(), EventLog()) == StaleButton()
    assert [(job.kind, job.payload) for job in jobs] == [
        ("generate_brand", {"correction": "somos más formales"})
    ]


async def test_a_failed_revision_puts_an_active_business_back(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions, state="active")
    await BrandFlow(sessions).revise(PHONE, "más formales")
    # The model has no answer: the Strategist fails.
    jobs, background = runner(
        sessions, {"generate_brand": generate_brand}, FakeChannel(), SequenceModel([])
    )

    await jobs.run_due()
    await background.join()

    async with sessions() as db:
        restored = await db.get_one(Business, business.id)
    assert (restored.onboarding_state, restored.conversation_state) == ("active", {})


async def test_a_failed_first_brand_stays_generating(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    await queue(sessions, "generate_brand", business)
    jobs, background = runner(
        sessions, {"generate_brand": generate_brand}, FakeChannel(), SequenceModel([])
    )

    await jobs.run_due()
    await background.join()

    async with sessions() as db:
        assert (await db.get_one(Business, business.id)).onboarding_state == "generating_brand"


async def test_an_active_brand_can_be_changed_but_not_before_onboarding(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_business(sessions, state="awaiting_web_form")
    flow = BrandFlow(sessions)
    assert await flow.revise(PHONE, "más formales") is False

    async with sessions() as db:
        business = await db.scalar(select(Business).where(Business.owner_phone == PHONE))
        business.onboarding_state = "active"
        await db.commit()
    assert await flow.revise(PHONE, "más formales") is True


async def test_brand_buttons_are_stale_in_another_state(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await add_business(sessions, state="active")
    buttons = router(sessions)

    assert await buttons.handle(PHONE, "brand_ok", FakeChannel(), EventLog()) == StaleButton()
    assert await buttons.handle(PHONE, "brand_fix", FakeChannel(), EventLog()) == StaleButton()


async def test_retry_button_requeues_the_failed_job(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    business = await add_business(sessions)
    async with sessions() as db:
        failed = Job(business_id=business.id, kind="generate_brand", status="failed")
        db.add(failed)
        await db.commit()
    buttons = router(sessions)

    first = await buttons.handle(PHONE, f"retry:{failed.id}", FakeChannel(), EventLog())
    second = await buttons.handle(PHONE, f"retry:{failed.id}", FakeChannel(), EventLog())

    assert (first, second) == (JobRetried("generate_brand"), StaleButton())
