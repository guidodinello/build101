"""The agent run ledger (T10, #205): one `agent_runs` row for every model call.

The metered ports below wrap the text, image and video ports where they are built, so each call
leaves a row whatever adapter answers it. Who a call is for (the Business, job and Post) comes
from `scoped`, set where a turn, a job or a Post starts; asyncio tasks inherit it, so no
signature changes. Text adapters hand what the provider says a call used to `report_usage`.

Rows are kept in memory and written in batches by `Ledger.run`, so an Owner's turn pays no
database time. A failed write is logged and dropped: the ledger never breaks a turn or a job.
"""

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from functools import cache
from typing import Any

from pydantic import BaseModel
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import get_settings
from app.db.models import AgentRun, Business
from app.imagegen.base import GeneratedImage, ImageGenPort
from app.videogen.base import GeneratedVideo, VideoGenPort

from .client import (
    ChatModel,
    Content,
    Grounded,
    GroundedModel,
    Reply,
    Step,
    StructuredModel,
    ThinkingLevel,
    Tool,
)
from .prices import cost_usd
from .usage import Usage, collecting

logger = logging.getLogger(__name__)

IMAGE_AGENT = "image_gen"
VIDEO_AGENT = "video_gen"
FLUSH_EVERY_S = 5.0
# About 40 minutes of a busy pilot between two writes; past it, rows are dropped, not memory
MAX_PENDING = 5_000
MAX_ERROR_CHARS = 1_000


@dataclass(frozen=True, slots=True)
class Scope:
    """Who the calls in this context are for. A turn knows only the sender; the writer looks
    their Business up, so the phone number never reaches the ledger."""

    sender: str | None = None
    business_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    post_id: str | None = None


NO_SCOPE = Scope()
_scope: ContextVar[Scope | None] = ContextVar("agent_run_scope", default=None)


def current_scope() -> Scope:
    return _scope.get() or NO_SCOPE


@contextmanager
def scoped(
    *,
    sender: str | None = None,
    business_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    post_id: str | None = None,
) -> Iterator[None]:
    """Attribute the calls made inside to these ids, on top of the enclosing scope."""
    changes = {
        "sender": sender,
        "business_id": business_id,
        "job_id": job_id,
        "post_id": post_id,
    }
    current = current_scope()
    token = _scope.set(replace(current, **{k: v for k, v in changes.items() if v is not None}))
    try:
        yield
    finally:
        _scope.reset(token)


@dataclass(frozen=True, slots=True)
class Run:
    scope: Scope
    agent: str
    model: str
    effort: str | None
    usage: Usage
    latency_ms: int
    error: str | None
    at: datetime
    input: dict[str, Any] | None = None
    output: dict[str, Any] | None = None


class Ledger:
    """The runs not yet written. Closed until `open`: without a database nothing is kept."""

    def __init__(self, keep_content: bool = False) -> None:
        self.keep_content = keep_content  # AGENT_RUNS_CONTENT: debug only, it copies Owner text
        self._pending: list[Run] = []
        self._open = False
        self._dropped = 0
        self._stopped = False
        self._stopping: asyncio.Event | None = None

    def open(self) -> None:
        self._open = True
        self._stopped = False

    def record(self, run: Run) -> None:
        if not self._open:
            return
        if len(self._pending) >= MAX_PENDING:
            self._dropped += 1
            return
        self._pending.append(run)

    def pending(self) -> list[Run]:
        return list(self._pending)

    async def metered[T](
        self,
        agent: str,
        model: str,
        effort: str | None,
        work: Awaitable[T],
        used: Callable[[T], Usage] | None = None,
        content: dict[str, Any] | None = None,
        output: Callable[[T], dict[str, Any]] | None = None,
    ) -> T:
        """Await `work` and record it: latency, error and usage, from `used(result)` when the
        result carries it, else from what the adapter reported."""
        started = time.monotonic()
        with collecting() as reported:
            try:
                result = await work
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_CHARS]
                usage = reported[-1] if reported else Usage()
                self._record(agent, model, effort, started, usage, error=error, content=content)
                raise
        usage = used(result) if used else reported[-1] if reported else Usage()
        kept = output(result) if output and self.keep_content else None
        self._record(agent, model, effort, started, usage, content=content, output=kept)
        return result

    def _record(
        self,
        agent: str,
        model: str,
        effort: str | None,
        started: float,
        usage: Usage,
        *,
        error: str | None = None,
        content: dict[str, Any] | None = None,
        output: dict[str, Any] | None = None,
    ) -> None:
        latency_ms = round((time.monotonic() - started) * 1000)
        kept = content if self.keep_content else None
        run = Run(
            current_scope(),
            agent,
            model,
            effort,
            usage,
            latency_ms,
            error,
            datetime.now(UTC),
            kept,
            output,
        )
        self.record(run)

    async def write(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        """Write what is pending in one transaction; on failure, log and drop it."""
        batch, self._pending = self._pending, []
        if self._dropped:
            logger.warning("agent run ledger full: dropped %d runs", self._dropped)
            self._dropped = 0
        if not batch:
            return
        try:
            async with sessions() as db, db.begin():
                await db.execute(insert(AgentRun), await _rows(db, batch))
        except Exception:
            # The ledger's boundary: a lost batch must never reach a turn or a job.
            logger.exception("could not write %d agent runs, dropped", len(batch))

    async def run(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        """Write every `FLUSH_EVERY_S` until `stop`, then once more."""
        # Made here, on the loop that runs it: the ledger outlives a test's event loop
        stopping = self._stopping = asyncio.Event()
        if self._stopped:
            stopping.set()
        while True:
            with suppress(TimeoutError):
                await asyncio.wait_for(stopping.wait(), FLUSH_EVERY_S)
            await self.write(sessions)
            if stopping.is_set():
                return

    def stop(self) -> None:
        self._stopped = True
        if self._stopping is not None:
            self._stopping.set()


async def _rows(db: AsyncSession, batch: list[Run]) -> list[dict[str, Any]]:
    senders = {run.scope.sender for run in batch if run.scope.sender and not run.scope.business_id}
    businesses: dict[str, uuid.UUID] = {}
    if senders:
        found = await db.execute(
            select(Business.owner_phone, Business.id).where(Business.owner_phone.in_(senders))
        )
        businesses = {phone: business_id for phone, business_id in found}
    return [_row(run, businesses) for run in batch]


def _row(run: Run, businesses: dict[str, uuid.UUID]) -> dict[str, Any]:
    scope, usage = run.scope, run.usage
    business_id = scope.business_id or (businesses.get(scope.sender) if scope.sender else None)
    return {
        "id": uuid.uuid4(),
        "business_id": business_id,
        "job_id": scope.job_id,
        "post_id": scope.post_id,
        "agent": run.agent,
        "model": run.model,
        "effort": run.effort,
        "service_tier": usage.service_tier,
        "input": run.input,
        "output": run.output,
        "stop_reason": usage.stop_reason,
        "input_tokens": usage.input_tokens,
        "cache_read_tokens": usage.cached_tokens,
        "thought_tokens": usage.thought_tokens,
        "output_tokens": usage.output_tokens,
        "image_size": usage.image_size,
        "image_count": usage.image_count,
        "video_seconds": usage.video_seconds,
        "latency_ms": run.latency_ms,
        "error": run.error,
        "cost_usd": None if run.error else cost_usd(run.model, usage, run.at.date()),
        "created_at": run.at,
    }


@cache
def get_ledger() -> Ledger:
    """The process's one ledger, opened by the app's lifespan when there is a database."""
    return Ledger(keep_content=get_settings().agent_runs_content)


def _texts(content: list[Content]) -> dict[str, Any]:
    return {
        "text": [block["text"] for block in content if block["type"] == "text"],
        "images": sum(block["type"] == "image" for block in content),
    }


def _last_input(history: list[Step]) -> dict[str, Any]:
    for step in reversed(history):
        if step["type"] == "user_input":
            return _texts(list(step.get("content", [])))
    return {}


def _structured_output(result: BaseModel) -> dict[str, Any]:
    return result.model_dump(mode="json")


class MeteredStructured:
    """A `StructuredModel` whose calls each leave an agent run."""

    def __init__(self, inner: StructuredModel, model: str, ledger: Ledger) -> None:
        self.inner = inner
        self._model = model
        self._ledger = ledger

    async def structured[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: ThinkingLevel,
    ) -> T:
        return await self._ledger.metered(
            agent,
            self._model,
            thinking_level,
            self.inner.structured(agent, system, content, schema, thinking_level),
            content=_texts(content),
            output=_structured_output,
        )


class MeteredChat(MeteredStructured):
    """A `ChatModel` whose calls each leave an agent run."""

    def __init__(self, inner: ChatModel, model: str, ledger: Ledger) -> None:
        super().__init__(inner, model, ledger)
        self._chat = inner

    async def reply(
        self,
        agent: str,
        system: str,
        history: list[Step],
        thinking_level: ThinkingLevel,
        tools: list[Tool] | None = None,
    ) -> Reply:
        return await self._ledger.metered(
            agent,
            self._model,
            thinking_level,
            self._chat.reply(agent, system, history, thinking_level, tools),
            content=_last_input(history),
            output=lambda reply: {
                "text": reply.text,
                "calls": [call.name for call in reply.function_calls],
            },
        )


class MeteredGrounded:
    """A `GroundedModel` whose calls each leave an agent run."""

    def __init__(self, inner: GroundedModel, model: str, ledger: Ledger) -> None:
        self.inner = inner
        self._model = model
        self._ledger = ledger

    async def grounded[T: BaseModel](
        self,
        agent: str,
        system: str,
        content: list[Content],
        schema: type[T],
        thinking_level: ThinkingLevel,
        tools: list[Tool],
    ) -> Grounded[T]:
        return await self._ledger.metered(
            agent,
            self._model,
            thinking_level,
            self.inner.grounded(agent, system, content, schema, thinking_level, tools),
            content=_texts(content),
            output=lambda grounded: _structured_output(grounded.output),
        )


class MeteredImageGen:
    """An `ImageGenPort` whose calls each leave an agent run, costed per image and size."""

    def __init__(
        self, inner: ImageGenPort, model: str, effort: str, image_size: str, ledger: Ledger
    ) -> None:
        self.inner = inner
        self._model = model
        self._effort = effort
        self._image_size = image_size
        self._ledger = ledger

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        style_image: bytes | None = None,
        *,
        aspect_ratio: str | None = None,
        image_size: str | None = None,
    ) -> GeneratedImage:
        size = image_size or self._image_size
        return await self._ledger.metered(
            IMAGE_AGENT,
            self._model,
            self._effort,
            self.inner.generate(
                prompt,
                reference_images,
                style_image,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
            ),
            used=lambda image: image_usage(image.usage, size),
            content={"text": [prompt], "images": len(reference_images) + bool(style_image)},
        )


def image_usage(counts: dict[str, int], image_size: str) -> Usage:
    """`GeneratedImage.usage` (imagegen/gemini.py `usage_counts`) as a ledger `Usage`. The image
    itself is billed per image, so only the text part of the output counts as tokens."""
    return Usage(
        input_tokens=counts.get("prompt_tokens"),
        cached_tokens=counts.get("cached_tokens"),
        thought_tokens=counts.get("thoughts_tokens"),
        output_tokens=counts.get("output_text_tokens"),
        image_size=image_size,
        image_count=1,
    )


class MeteredVideoGen:
    """A `VideoGenPort` whose clips each leave an agent run with their length (Veo bills per
    second)."""

    def __init__(self, inner: VideoGenPort, model: str, ledger: Ledger) -> None:
        self.inner = inner
        self._model = model
        self._ledger = ledger

    async def generate(
        self,
        prompt: str,
        reference_images: list[bytes],
        *,
        aspect_ratio: str = "9:16",
        duration_seconds: int = 8,
    ) -> GeneratedVideo:
        return await self._ledger.metered(
            VIDEO_AGENT,
            self._model,
            None,
            self.inner.generate(
                prompt,
                reference_images,
                aspect_ratio=aspect_ratio,
                duration_seconds=duration_seconds,
            ),
            used=lambda video: Usage(video_seconds=video.duration_seconds),
            content={"text": [prompt], "images": len(reference_images)},
        )
