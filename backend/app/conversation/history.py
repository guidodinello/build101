import asyncio
import json
import logging
import uuid
from collections import defaultdict
from functools import cache
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.channels.inbound import mask
from app.db.models import ConversationStep
from app.knowledge.db import business_of
from app.llm.client import ChatModel, LLMError, Step, text_content, user_step
from app.prompts import load_prompt

logger = logging.getLogger(__name__)

# Gemini Flash reads far more, and the stable prefix caches; this keeps each turn fast and cheap.
MAX_HISTORY_TOKENS = 40_000
# What a compaction keeps word for word; the turns before it become the summary.
KEEP_TOKENS = 20_000
# Past this, steps are dropped without a summary: compaction keeps failing (the LLM is down).
HARD_LIMIT_TOKENS = 3 * MAX_HISTORY_TOKENS
CHARS_PER_TOKEN = 4  # a rough estimate, good enough for a budget
SUMMARY_AGENT = "conversation_summarizer"
SUMMARY_PROMPT_PATH = Path(__file__).parent / "prompts" / "summary.md"


class History(Protocol):
    """The orchestrator's history per sender, and the summary of what was compacted out of it."""

    def lock(self, sender: str) -> asyncio.Lock:
        """Hold it for a whole turn: one sender's messages are answered one at a time."""
        ...

    async def get(self, sender: str) -> list[Step]: ...

    async def extend(self, sender: str, steps: list[Step]) -> None: ...

    async def summary(self, sender: str) -> str | None: ...

    async def compact(self, sender: str, drop: int, summary: str | None) -> None:
        """Drop the first `drop` steps and, unless None, replace the summary."""
        ...


class InMemoryHistory:
    """History without a database (local runs, tests). Lost on restart."""

    def __init__(self) -> None:
        self._steps: defaultdict[str, list[Step]] = defaultdict(list)
        self._summaries: dict[str, str] = {}
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def lock(self, sender: str) -> asyncio.Lock:
        return self._locks[sender]

    async def get(self, sender: str) -> list[Step]:
        return list(self._steps[sender])

    async def extend(self, sender: str, steps: list[Step]) -> None:
        self._steps[sender].extend(steps)

    async def summary(self, sender: str) -> str | None:
        return self._summaries.get(sender)

    async def compact(self, sender: str, drop: int, summary: str | None) -> None:
        del self._steps[sender][:drop]
        if summary is not None:
            self._summaries[sender] = summary


class DbHistory:
    """History in `conversation_steps`, so a deploy or a crash doesn't erase it (ADR 0030).

    Keyed by the Owner's phone: the onboarding gate creates the Business before the chat runs.
    The locks stay in memory: one backend instance (ADR 0005).
    """

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._business_ids: dict[str, uuid.UUID] = {}

    def lock(self, sender: str) -> asyncio.Lock:
        return self._locks[sender]

    async def get(self, sender: str) -> list[Step]:
        async with self._sessions() as db:
            business_id = await self._business_id(db, sender)
            if business_id is None:
                return []
            steps = await db.scalars(
                select(ConversationStep.step)
                .where(ConversationStep.business_id == business_id)
                .order_by(ConversationStep.id)
            )
            return list(steps)

    async def extend(self, sender: str, steps: list[Step]) -> None:
        async with self._sessions() as db:
            business_id = await self._business_id(db, sender)
            if business_id is None:
                logger.warning("no Business for %s: %d steps not stored", mask(sender), len(steps))
                return
            db.add_all(ConversationStep(business_id=business_id, step=step) for step in steps)
            await db.commit()

    async def summary(self, sender: str) -> str | None:
        async with self._sessions() as db:
            business = await business_of(db, sender)
            return business.conversation_summary if business else None

    async def compact(self, sender: str, drop: int, summary: str | None) -> None:
        async with self._sessions() as db:
            business = await business_of(db, sender)
            if business is None:
                return
            oldest = (
                select(ConversationStep.id)
                .where(ConversationStep.business_id == business.id)
                .order_by(ConversationStep.id)
                .limit(drop)
            )
            await db.execute(delete(ConversationStep).where(ConversationStep.id.in_(oldest)))
            if summary is not None:
                business.conversation_summary = summary
            await db.commit()

    async def _business_id(self, db: AsyncSession, sender: str) -> uuid.UUID | None:
        if sender not in self._business_ids:
            business = await business_of(db, sender)
            if business is None:
                return None
            self._business_ids[sender] = business.id
        return self._business_ids[sender]


async def record_note(
    sessions: async_sessionmaker[AsyncSession], business_id: uuid.UUID, note: str
) -> None:
    """Add a system note to a Business's history from outside the chat (a job's message)."""
    async with sessions() as db:
        db.add(ConversationStep(business_id=business_id, step=user_step(note)))
        await db.commit()


class ConversationSummary(BaseModel):
    summary: str


class Compactor:
    """Keeps a history under its token budget by folding the oldest turns into the summary."""

    def __init__(
        self,
        history: History,
        model: ChatModel,
        max_tokens: int = MAX_HISTORY_TOKENS,
        keep_tokens: int = KEEP_TOKENS,
        hard_limit_tokens: int = HARD_LIMIT_TOKENS,
    ) -> None:
        self._history = history
        self._model = model
        self._max_tokens = max_tokens
        self._keep_tokens = keep_tokens
        self._hard_limit_tokens = hard_limit_tokens

    def needed(self, past: list[Step], new: list[Step]) -> bool:
        return sum(tokens(step) for step in [*past, *new]) > self._max_tokens

    async def compact(self, sender: str) -> None:
        """The caller holds the sender's lock."""
        steps = await self._history.get(sender)
        total = sum(tokens(step) for step in steps)
        if total <= self._max_tokens:
            return
        drop = cut_point(steps, self._keep_tokens)
        if drop == 0:
            return
        try:
            summary = await self._summarize(await self._history.summary(sender), steps[:drop])
        except LLMError:
            if total <= self._hard_limit_tokens:
                logger.warning("summary failed for %s; retried next turn", mask(sender))
                return
            logger.warning("summary failed for %s; dropping %d steps", mask(sender), drop)
            summary = None
        await self._history.compact(sender, drop, summary)
        logger.info("compacted %d steps for %s", drop, mask(sender))

    async def _summarize(self, previous: str | None, steps: list[Step]) -> str:
        parts = [f"<previous_summary>\n{previous or 'none'}\n</previous_summary>"]
        parts.append(f"<conversation>\n{transcript(steps)}\n</conversation>")
        result = await self._model.structured(
            SUMMARY_AGENT,
            summary_prompt(),
            [text_content("\n".join(parts))],
            ConversationSummary,
            "low",
        )
        return result.summary.strip()


@cache
def summary_prompt() -> str:
    return load_prompt(SUMMARY_PROMPT_PATH)


def tokens(step: Step) -> int:
    return len(json.dumps(step, ensure_ascii=False)) // CHARS_PER_TOKEN


def cut_point(steps: list[Step], keep_tokens: int) -> int:
    """How many leading steps to drop: the rest starts with a user turn and fits `keep_tokens`.

    The last user turn is always kept, however long it is.
    """
    starts = [n for n, step in enumerate(steps) if step.get("type") == "user_input"]
    if not starts:
        return 0
    cut, kept, counted_from = starts[-1], 0, len(steps)
    for start in reversed(starts):
        kept += sum(tokens(step) for step in steps[start:counted_from])
        counted_from = start
        if kept > keep_tokens:
            break
        cut = start
    return cut


def transcript(steps: list[Step]) -> str:
    """The steps as plain lines for the summarizer; thought steps carry nothing it needs."""
    lines: list[str] = []
    for step in steps:
        match step.get("type"):
            case "user_input":
                text = " ".join(
                    block.get("text", "")
                    for block in step.get("content", [])
                    if block.get("type") == "text"
                )
                lines.append(f"Owner or system: {text}")
            case "model_output":
                text = " ".join(
                    block.get("text", "")
                    for block in step.get("content", [])
                    if block.get("type") == "text"
                )
                lines.append(f"Assistant: {text}")
            case "function_call":
                arguments = json.dumps(step.get("arguments") or {}, ensure_ascii=False)
                lines.append(f"Assistant called {step.get('name')}: {arguments}")
            case "function_result":
                lines.append(f"{step.get('name')} returned: {step.get('result')}")
    return "\n".join(lines)
