import asyncio
import uuid

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.channels.base import ChannelError
from app.conversation.events import (
    BrandGenerating,
    BrandSummaryReady,
    JobFailed,
    PostSent,
    PublishFailed,
    StaleButton,
    VideoSent,
)
from app.conversation.history import InMemoryHistory
from app.conversation.outbound import (
    BRAND_QUESTION,
    POINTS_UP,
    WHATSAPP_BODY_MAX,
    FixedReplies,
    send,
)
from app.copy import messages_es
from app.llm.client import Step, user_step
from tests.fakes import FakeChannel

PHONE = "59899000001"
JOB_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")


class DownChannel(FakeChannel):
    async def send_text(self, to: str, text: str) -> str:
        raise ChannelError("boom")


async def test_an_event_with_no_buttons_goes_as_plain_text() -> None:
    channel = FakeChannel()

    await send(channel, PHONE, "Hola", StaleButton())

    assert channel.sent == [(PHONE, "Hola")]
    assert channel.buttons == []


async def test_the_events_buttons_go_under_its_text() -> None:
    channel = FakeChannel()

    await send(channel, PHONE, "¿Lo subo?", PublishFailed("p1"))

    assert channel.buttons == [(PHONE, "¿Lo subo?", ["post_retry:p1"])]


async def test_a_text_over_the_limit_goes_first_and_the_buttons_follow_with_a_pointer() -> None:
    channel, text = FakeChannel(), "x" * (WHATSAPP_BODY_MAX + 1)

    await send(channel, PHONE, text, PublishFailed("p1"))

    assert channel.sent == [(PHONE, text), (PHONE, POINTS_UP)]
    assert channel.buttons == [(PHONE, POINTS_UP, ["post_retry:p1"])]


async def test_a_text_at_the_limit_is_not_split() -> None:
    channel = FakeChannel()

    await send(channel, PHONE, "x" * WHATSAPP_BODY_MAX, PublishFailed("p1"))

    assert len(channel.sent) == 1


async def test_a_brand_summary_over_the_limit_keeps_its_question_under_the_buttons() -> None:
    channel = FakeChannel()
    event = BrandSummaryReady("Katei", "x" * WHATSAPP_BODY_MAX)
    body = messages_es.brand_summary(event.business_name, event.summary)
    assert body.endswith(BRAND_QUESTION)

    await send(channel, PHONE, body, event)

    assert channel.sent == [
        (PHONE, body.removesuffix(BRAND_QUESTION).rstrip()),
        (PHONE, BRAND_QUESTION),
    ]
    assert channel.buttons == [(PHONE, BRAND_QUESTION, ["brand_ok", "brand_fix"])]


async def test_a_video_rides_as_the_header_of_the_buttons_message() -> None:
    channel = FakeChannel()
    event = VideoSent("p1", "https://backend.test/v/abc.mp4", 6, "Texto")

    await send(channel, PHONE, "¿Te gusta?", event)

    assert channel.video_headers == ["https://backend.test/v/abc.mp4"]
    assert [button for _, _, button in channel.buttons] == [
        ["post_approve:p1", "post_change:p1", "post_discard:p1"]
    ]


async def test_fixed_replies_send_the_fixed_text_and_record_the_note() -> None:
    channel, history = FakeChannel(), InMemoryHistory()
    event = BrandSummaryReady("Katei", "• cálidos")

    await FixedReplies(history)(PHONE, event, channel)

    assert channel.buttons == [
        (PHONE, messages_es.brand_summary("Katei", "• cálidos"), ["brand_ok", "brand_fix"])
    ]
    assert await history.get(PHONE) == [user_step(event.note())]


async def test_fixed_replies_for_a_failed_job_offer_the_retry() -> None:
    channel = FakeChannel()

    await FixedReplies(InMemoryHistory())(PHONE, JobFailed(JOB_ID, "generate_brand"), channel)

    assert channel.buttons == [(PHONE, messages_es.JOB_FAILED, [f"retry:{JOB_ID}"])]


async def test_fixed_replies_wait_for_the_senders_turn_in_progress() -> None:
    channel, history = FakeChannel(), InMemoryHistory()

    async with history.lock(PHONE):
        task = asyncio.create_task(FixedReplies(history)(PHONE, BrandGenerating(), channel))
        await asyncio.sleep(0.01)
        assert channel.sent == []
    await task

    assert channel.sent == [(PHONE, messages_es.BRAND_GENERATING)]


async def test_fixed_replies_let_a_verbatim_events_delivery_failure_reach_the_caller() -> None:
    history = InMemoryHistory()

    with pytest.raises(ChannelError):
        await FixedReplies(history)(PHONE, BrandGenerating(), DownChannel())

    assert await history.get(PHONE) == []  # nothing reached the Owner, so no note


async def test_fixed_replies_swallow_the_failure_of_any_other_event() -> None:
    await FixedReplies(InMemoryHistory())(PHONE, StaleButton(), DownChannel())


async def test_an_event_with_no_fallback_records_only_its_note() -> None:
    channel, history = FakeChannel(), InMemoryHistory()
    event = PostSent("p1", 1, "photos", ("f1",), (), "Texto")

    await FixedReplies(history)(PHONE, event, channel)

    # `PostSent` has buttons through its fallback `post_actions`; the note goes in after.
    assert channel.buttons[0][2] == ["post_approve:p1", "post_change:p1", "post_discard:p1"]
    assert await history.get(PHONE) == [user_step(event.note())]


class BrokenHistory(InMemoryHistory):
    async def extend(self, sender: str, steps: list[Step]) -> None:
        raise SQLAlchemyError("boom")


async def test_fixed_replies_let_a_verbatim_events_history_failure_reach_the_caller() -> None:
    with pytest.raises(SQLAlchemyError):
        await FixedReplies(BrokenHistory())(PHONE, BrandGenerating(), FakeChannel())


async def test_fixed_replies_swallow_the_history_failure_of_any_other_event() -> None:
    await FixedReplies(BrokenHistory())(PHONE, StaleButton(), FakeChannel())
