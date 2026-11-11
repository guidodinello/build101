import logging
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.background import BackgroundWork
from app.conversation.factory import ChatParts, build_chat
from app.db.models import AgentRun, Business, Job
from app.jobs.brand import generate_brand
from app.jobs.queue import enqueue
from app.jobs.runner import JobRunner
from app.jobs.setup import NOTIFY_ON_FAILURE, REQUEUE_IF_INTERRUPTED, UNDO
from app.llm.client import Grounded, LLMError, text_content
from app.llm.ledger import (
    IMAGE_AGENT,
    VIDEO_AGENT,
    Ledger,
    MeteredChat,
    MeteredGrounded,
    MeteredImageGen,
    MeteredStructured,
    MeteredVideoGen,
    Run,
    Scope,
    current_scope,
    scoped,
)
from app.llm.prices import cost_usd
from app.llm.usage import Usage, report_usage
from app.media.public import PublicImages, PublicVideos
from app.posts.drafts import CarouselDraft, PostCopy
from app.publishing.mock import MOCK_ACCOUNT_ID, MockPublisher
from app.rendering.mock import MockRenderer
from app.videogen.mock import MockVideoGen
from tests.conftest import requires_db
from tests.fakes import (
    CountingImageGen,
    EventLog,
    FakeChannel,
    FakeStorage,
    ScriptedModel,
    SequenceModel,
    brand_brain,
    call_reply,
    text_reply,
)
from tests.test_chat_handler import (
    DEBOUNCE_S,
    DRAFT,
    MAX_PHOTO_MB,
    SENDER,
    carousel_draft,
    message,
)

CHAT_MODEL = "gemini-3.8-flash"
IMAGE_MODEL = "gemini-nano-banana-2.1"
FLASH_USAGE = Usage(input_tokens=10_000, cached_tokens=4_000, thought_tokens=500, output_tokens=500)


def open_ledger(keep_content: bool = False) -> Ledger:
    ledger = Ledger(keep_content=keep_content)
    ledger.open()
    return ledger


class Answer(BaseModel):
    text: str


class ReportingModel:
    """A text adapter that reports its usage the way GeminiChat does."""

    def __init__(self, usage: Usage, fail: bool = False) -> None:
        self._usage = usage
        self._fail = fail

    async def structured[T: BaseModel](
        self, agent: str, system: str, content: Any, schema: type[T], thinking_level: str
    ) -> T:
        report_usage(self._usage)
        if self._fail:
            raise LLMError(f"{agent}: output doesn't match")
        return schema.model_validate({"text": "hola"})

    async def grounded[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: Any,
        schema: type[T],
        thinking_level: str,
        tools: Any,
    ) -> Grounded[T]:
        report_usage(self._usage)
        return Grounded(schema.model_validate({"text": "tendencias"}), [])


# Prices


def test_a_flash_call_is_priced_at_the_price_of_its_day() -> None:
    before = cost_usd(CHAT_MODEL, FLASH_USAGE, date(2026, 12, 31))
    after = cost_usd(CHAT_MODEL, FLASH_USAGE, date(2027, 1, 1))

    # 6,000 uncached at 0.75, 4,000 cached at 0.075 and 1,000 output at 3.75 per 1M
    assert before == Decimal("0.008550")
    assert after == Decimal("0.017100")


def test_an_image_is_priced_per_image_and_size_plus_its_tokens() -> None:
    usage = Usage(input_tokens=1_000, thought_tokens=1_000, image_size="1K", image_count=1)

    assert cost_usd(IMAGE_MODEL, usage, date(2026, 10, 27)) == Decimal("0.042600")


def test_flex_is_half_price() -> None:
    flex = Usage(input_tokens=1_000_000, service_tier="flex")

    assert cost_usd(CHAT_MODEL, flex, date(2026, 10, 27)) == Decimal("0.375000")


@pytest.mark.parametrize(
    ("model", "usage"),
    [
        ("claude-sonnet-unknown", FLASH_USAGE),
        (IMAGE_MODEL, Usage(image_size="8K", image_count=1)),
        (CHAT_MODEL, Usage(input_tokens=1, service_tier="deferred")),
    ],
)
def test_a_call_without_a_known_price_has_no_cost(model: str, usage: Usage) -> None:
    assert cost_usd(model, usage, date(2026, 10, 27)) is None


# Metering


async def test_one_owner_turn_leaves_a_run_per_text_call_and_per_image() -> None:
    request = call_reply(
        "create_post", brief="mesa", asset_ids=["f1"], style="design", slide_count=5
    )
    model = ScriptedModel(replies=[request, text_reply("Dale ⏳"), text_reply("¿Lo subo?")])
    model.drafts[CarouselDraft] = carousel_draft(5)
    model.drafts[PostCopy] = DRAFT
    ledger, image_gen, background = open_ledger(), CountingImageGen(), BackgroundWork()
    chat = build_chat(
        ChatParts(
            model=MeteredChat(model, CHAT_MODEL, ledger),
            image_gen=MeteredImageGen(image_gen, IMAGE_MODEL, "medium", "2K", ledger),
            renderer=MockRenderer(),
            publisher=MockPublisher(delay_s=0),
            images=PublicImages(),
            videos=PublicVideos(),
            background=background,
            public_backend_url="https://backend.test",
            account_id=MOCK_ACCOUNT_ID,
            assistant_name="Mora",
            max_photo_mb=MAX_PHOTO_MB,
            max_posts_per_day=5,
            max_videos_per_day=2,
            photo_debounce_s=DEBOUNCE_S,
        )
    )

    await chat.handler.handle(message("image", text=None), FakeChannel())
    await chat.handler.handle(message("text", text="armame un carrusel"), FakeChannel())
    await background.join()

    runs = ledger.pending()
    agents = [run.agent for run in runs]
    assert agents.count("orchestrator") == len(model.calls)
    assert agents.count("post_drafter") == len(model.structured_calls) >= 1
    assert agents.count(IMAGE_AGENT) == len(image_gen.calls) == 5
    assert len(runs) == len(model.calls) + len(model.structured_calls) + 5
    assert {run.scope.sender for run in runs} == {SENDER}
    images = [run for run in runs if run.agent == IMAGE_AGENT]
    post_ids = {run.scope.post_id for run in images}
    assert len(post_ids) == 1 and None not in post_ids
    assert all(run.usage.image_count == 1 and run.usage.image_size == "2K" for run in images)
    assert all(run.input is None and run.output is None for run in runs)


async def test_a_text_run_takes_the_usage_the_adapter_reported() -> None:
    ledger = open_ledger()
    model = MeteredStructured(ReportingModel(FLASH_USAGE), CHAT_MODEL, ledger)

    with scoped(post_id="abc12345"):
        await model.structured("post_drafter", "", [text_content("hola")], Answer, "low")

    [run] = ledger.pending()
    assert (run.agent, run.model, run.effort, run.usage) == (
        "post_drafter",
        CHAT_MODEL,
        "low",
        FLASH_USAGE,
    )
    assert run.scope == Scope(post_id="abc12345") and run.error is None


async def test_a_failed_call_leaves_a_run_with_its_error_and_still_raises() -> None:
    ledger = open_ledger()
    model = MeteredStructured(ReportingModel(FLASH_USAGE, fail=True), CHAT_MODEL, ledger)

    with pytest.raises(LLMError):
        await model.structured("asset_analyst", "", [], Answer, "low")

    [run] = ledger.pending()
    assert run.error and "LLMError" in run.error
    assert run.usage == FLASH_USAGE


async def test_a_failed_image_leaves_a_run_without_usage() -> None:
    ledger = open_ledger()
    image_gen = MeteredImageGen(CountingImageGen(fail=True), IMAGE_MODEL, "medium", "2K", ledger)

    with pytest.raises(RuntimeError):
        await image_gen.generate("scene", [])

    [run] = ledger.pending()
    assert run.error == "RuntimeError: image service down"
    assert run.usage == Usage()


async def test_a_clip_leaves_a_run_with_its_length_in_seconds() -> None:
    ledger = open_ledger()
    video_gen = MeteredVideoGen(MockVideoGen(delay_s=0), "veo-3.1-lite-generate-preview", ledger)

    await video_gen.generate("a slow pan", [], duration_seconds=6)

    [run] = ledger.pending()
    assert (run.agent, run.usage.video_seconds) == (VIDEO_AGENT, 6)


async def test_content_is_kept_only_with_the_debug_setting() -> None:
    ledger = open_ledger(keep_content=True)
    model = MeteredStructured(ReportingModel(FLASH_USAGE), CHAT_MODEL, ledger)

    await model.structured("post_drafter", "", [text_content("mesa de roble")], Answer, "low")

    [run] = ledger.pending()
    assert run.input == {"text": ["mesa de roble"], "images": 0}
    assert run.output == {"text": "hola"}


async def test_a_closed_ledger_keeps_nothing() -> None:
    ledger = Ledger()
    model = MeteredStructured(ReportingModel(FLASH_USAGE), CHAT_MODEL, ledger)

    await model.structured("post_drafter", "", [], Answer, "low")

    assert ledger.pending() == []


def test_scopes_nest_and_unwind() -> None:
    job_id = uuid.uuid4()
    with scoped(job_id=job_id), scoped(sender=SENDER):
        assert current_scope() == Scope(sender=SENDER, job_id=job_id)
    assert current_scope() == Scope()


# Writing


def run_of(agent: str, scope: Scope, usage: Usage = FLASH_USAGE, **changes: Any) -> Run:
    fields: dict[str, Any] = {
        "scope": scope,
        "agent": agent,
        "model": CHAT_MODEL,
        "effort": "medium",
        "usage": usage,
        "latency_ms": 1200,
        "error": None,
        "at": datetime(2026, 10, 27, 15, tzinfo=UTC),
    } | changes
    return Run(**fields)


class BrokenSessions:
    def __call__(self) -> Any:
        raise OSError("database down")


async def test_a_failed_write_is_logged_and_dropped(caplog: pytest.LogCaptureFixture) -> None:
    ledger = open_ledger()
    ledger.record(run_of("orchestrator", Scope(sender=SENDER)))

    with caplog.at_level(logging.ERROR):
        await ledger.write(BrokenSessions())  # type: ignore[arg-type]

    assert ledger.pending() == []
    assert "could not write 1 agent runs" in caplog.text


@requires_db
async def test_written_runs_carry_the_business_job_post_and_cost(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=SENDER, name="Katei")
        db.add(business)
        await db.flush()
        job = Job(business_id=business.id, kind="generate_brand")
        db.add(job)
        await db.commit()
    ledger = open_ledger()
    ledger.record(run_of("orchestrator", Scope(sender=SENDER, post_id="abc12345")))
    ledger.record(run_of("brand_strategist", Scope(business_id=business.id, job_id=job.id)))
    ledger.record(run_of("niche_analyst", Scope()))
    ledger.record(run_of("post_drafter", Scope(sender=SENDER), error="LLMError: boom"))

    await ledger.write(sessions)

    async with sessions() as db:
        rows = {row.agent: row for row in await db.scalars(select(AgentRun))}
    assert rows["orchestrator"].business_id == business.id
    assert rows["orchestrator"].post_id == "abc12345"
    assert rows["orchestrator"].cost_usd == Decimal("0.008550")
    assert (rows["orchestrator"].input, rows["orchestrator"].output) == (None, None)
    assert (rows["brand_strategist"].business_id, rows["brand_strategist"].job_id) == (
        business.id,
        job.id,
    )
    assert rows["niche_analyst"].business_id is None
    assert (rows["post_drafter"].error, rows["post_drafter"].cost_usd) == ("LLMError: boom", None)
    assert ledger.pending() == []


@requires_db
async def test_a_job_s_model_calls_carry_its_job_id(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(
            owner_phone=SENDER,
            name="Katei",
            onboarding_state="generating_brand",
            onboarding_data={"brand": {}, "preferences": {}},
        )
        db.add(business)
        await db.flush()
        job = enqueue(db, "generate_brand", business.id, {})
        await db.commit()
    ledger, background = open_ledger(), BackgroundWork()
    model = MeteredStructured(SequenceModel([brand_brain()]), CHAT_MODEL, ledger)
    jobs = JobRunner(
        sessions,
        {"generate_brand": generate_brand},
        FakeStorage(),
        FakeChannel(),
        model,  # type: ignore[arg-type]
        EventLog(),
        NOTIFY_ON_FAILURE,
        REQUEUE_IF_INTERRUPTED,
        UNDO,
        background=background,
    )

    assert await jobs.run_due() == 1
    await background.join()

    [run] = ledger.pending()
    assert run.agent == "brand_strategist"
    assert run.scope == Scope(business_id=business.id, job_id=job.id)


@requires_db
async def test_a_niche_report_run_has_no_business(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    ledger = open_ledger()
    model = MeteredGrounded(ReportingModel(FLASH_USAGE), CHAT_MODEL, ledger)

    await model.grounded("niche_analyst", "", [], Answer, "high", [])
    await ledger.write(sessions)

    async with sessions() as db:
        row = await db.scalar(select(AgentRun))
    assert row and (row.agent, row.business_id) == ("niche_analyst", None)


@requires_db
async def test_the_ledger_writes_until_stopped_then_once_more(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    ledger = open_ledger()
    ledger.record(run_of("orchestrator", Scope()))
    ledger.stop()

    await ledger.run(sessions)

    async with sessions() as db:
        assert len((await db.scalars(select(AgentRun))).all()) == 1


# Views


@requires_db
async def test_the_cost_views_add_up_per_business_agent_and_cache(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        montevideo = Business(owner_phone="59899000001", timezone="America/Montevideo")
        madrid = Business(owner_phone="34600000001", timezone="Europe/Madrid")
        db.add_all([montevideo, madrid])
        await db.commit()
    ledger = open_ledger()
    flash = Usage(input_tokens=1_000_000, cached_tokens=500_000)
    # 01:00 UTC on Nov 1 is still Oct 31 in Montevideo (UTC-3), already Nov 1 in Madrid
    late = datetime(2026, 11, 1, 1, tzinfo=UTC)
    early = datetime(2026, 10, 31, 12, tzinfo=UTC)
    for business, at in ((montevideo, late), (montevideo, early), (madrid, late)):
        ledger.record(run_of("orchestrator", Scope(business_id=business.id), flash, at=at))
    image = Usage(input_tokens=1_000, image_size="2K", image_count=1)
    ledger.record(
        run_of("image_gen", Scope(business_id=montevideo.id), image, model=IMAGE_MODEL, at=early)
    )
    ledger.record(run_of("niche_analyst", Scope(), flash, at=early))
    ledger.record(run_of("orchestrator", Scope(business_id=madrid.id), at=late, error="boom"))
    await ledger.write(sessions)

    async with sessions() as db:
        daily = (
            await db.execute(
                text(
                    "select business_id, day, runs, failed_runs, cost_usd"
                    " from agent_run_costs_daily order by cost_usd"
                )
            )
        ).all()
        monthly = (
            await db.execute(
                text("select business_id, month, cost_usd from agent_run_costs_monthly")
            )
        ).all()
        by_agent = (
            await db.execute(
                text("select agent, runs, failed_runs, cost_usd from agent_run_costs_by_agent")
            )
        ).all()
        cache = (
            await db.execute(text("select agent, model, cache_hit_rate from agent_run_cache_hits"))
        ).all()

    # A Flash run: 500K uncached at 0.75 and 500K cached at 0.075 per 1M = 0.4125
    # The image: 1K input tokens at 1.50 per 1M plus a 2K image at 0.0504 = 0.0519
    assert {
        (row.business_id, row.day, row.runs, row.failed_runs, row.cost_usd) for row in daily
    } == {
        (montevideo.id, date(2026, 10, 31), 3, 0, Decimal("0.876900")),
        (madrid.id, date(2026, 11, 1), 2, 1, Decimal("0.412500")),
    }
    assert {(row.business_id, row.month, row.cost_usd) for row in monthly} == {
        (montevideo.id, date(2026, 10, 1), Decimal("0.876900")),
        (madrid.id, date(2026, 11, 1), Decimal("0.412500")),
    }
    agents = {row.agent: (row.runs, row.failed_runs, row.cost_usd) for row in by_agent}
    assert agents["image_gen"] == (1, 0, Decimal("0.051900"))
    assert agents["niche_analyst"] == (1, 0, Decimal("0.412500"))
    hit_rates = {(row.agent, row.model): row.cache_hit_rate for row in cache}
    assert hit_rates[("orchestrator", CHAT_MODEL)] == Decimal("0.5000")
    assert hit_rates[("image_gen", IMAGE_MODEL)] == Decimal("0.0000")
