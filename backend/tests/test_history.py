import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.conversation.history import (
    Compactor,
    ConversationSummary,
    DbHistory,
    InMemoryHistory,
    cut_point,
    record_note,
    tokens,
    transcript,
)
from app.db.models import Business
from app.llm.client import Step, user_step
from tests.conftest import requires_db
from tests.fakes import ScriptedModel, call_reply, text_reply

PHONE = "59899123456"


def turn(text: str, reply: str = "ok") -> list[Step]:
    return [user_step(text), *text_reply(reply).steps]


def test_cut_point_keeps_whole_turns_within_the_budget() -> None:
    steps = [*turn("uno"), *turn("dos"), *turn("tres")]
    per_turn = sum(tokens(step) for step in turn("dos"))

    assert cut_point(steps, keep_tokens=2 * per_turn) == 3
    assert steps[3]["type"] == "user_input"


def test_cut_point_always_keeps_the_last_turn() -> None:
    steps = [*turn("uno"), *turn("dos " * 500)]

    assert cut_point(steps, keep_tokens=1) == 3


def test_cut_point_without_a_user_turn_drops_nothing() -> None:
    assert cut_point(text_reply("hola").steps, keep_tokens=1) == 0


def test_transcript_names_who_said_what_and_skips_thoughts() -> None:
    steps = [*turn("hola", "¡Hola!"), *call_reply("list_posts").steps]
    steps.append({"type": "function_result", "name": "list_posts", "result": '{"posts": []}'})

    assert transcript(steps).splitlines() == [
        "Owner or system: hola",
        "Assistant: ¡Hola!",
        "Assistant called list_posts: {}",
        'list_posts returned: {"posts": []}',
    ]


async def test_a_short_history_is_left_alone() -> None:
    history, model = InMemoryHistory(), ScriptedModel()
    await history.extend(PHONE, turn("hola"))

    await Compactor(history, model, max_tokens=10_000).compact(PHONE)

    assert len(await history.get(PHONE)) == 3
    assert model.structured_calls == []


async def test_compaction_merges_the_previous_summary() -> None:
    history = InMemoryHistory()
    model = ScriptedModel(drafts={ConversationSummary: ConversationSummary(summary=" nuevo ")})
    await history.compact(PHONE, 0, "viejo")
    await history.extend(PHONE, [*turn("uno"), *turn("dos"), *turn("tres")])

    await Compactor(history, model, max_tokens=10, keep_tokens=10).compact(PHONE)

    assert await history.summary(PHONE) == "nuevo"
    assert [step["content"][0]["text"] for step in (await history.get(PHONE))[:1]] == ["tres"]
    assert "<previous_summary>\nviejo\n</previous_summary>" in (
        model.structured_calls[0][0]["text"]
    )


async def test_past_the_hard_limit_a_failed_summary_still_drops_old_turns() -> None:
    history, model = InMemoryHistory(), ScriptedModel()  # no summary draft: it fails
    await history.extend(PHONE, [*turn("uno"), *turn("dos")])

    await Compactor(history, model, max_tokens=10, keep_tokens=10, hard_limit_tokens=10).compact(
        PHONE
    )

    assert len(await history.get(PHONE)) == 3
    assert await history.summary(PHONE) is None


@requires_db
async def test_the_history_survives_a_restart(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        db.add(Business(owner_phone=PHONE))
        await db.commit()
    await DbHistory(sessions).extend(PHONE, [*turn("uno"), *turn("dos")])

    after_restart = DbHistory(sessions)

    assert await after_restart.get(PHONE) == [*turn("uno"), *turn("dos")]
    assert await after_restart.summary(PHONE) is None


@requires_db
async def test_compaction_deletes_the_oldest_steps_and_saves_the_summary(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        db.add(Business(owner_phone=PHONE))
        await db.commit()
    history = DbHistory(sessions)
    await history.extend(PHONE, [*turn("uno"), *turn("dos")])

    await history.compact(PHONE, 3, "Vende mesas.")

    assert await history.get(PHONE) == turn("dos")
    assert await history.summary(PHONE) == "Vende mesas."


@requires_db
async def test_without_a_business_nothing_is_stored(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    history = DbHistory(sessions)

    await history.extend(PHONE, turn("hola"))

    assert await history.get(PHONE) == []


@requires_db
async def test_a_job_can_add_a_note_to_the_history(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        business = Business(owner_phone=PHONE)
        db.add(business)
        await db.commit()
    history = DbHistory(sessions)
    await history.extend(PHONE, turn("hola"))

    await record_note(sessions, business.id, "[brand summary sent]")

    assert (await history.get(PHONE))[-1] == user_step("[brand summary sent]")


@pytest.mark.parametrize("drop", [0, 99])
async def test_in_memory_compaction_drops_up_to_what_there_is(drop: int) -> None:
    history = InMemoryHistory()
    await history.extend(PHONE, turn("hola"))

    await history.compact(PHONE, drop, None)

    assert len(await history.get(PHONE)) == (3 if drop == 0 else 0)
