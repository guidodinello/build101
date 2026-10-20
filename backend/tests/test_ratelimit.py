import asyncio
from dataclasses import dataclass, field

import pytest

from app.channels.base import ChannelError, ChannelPort, InboundMessage
from app.channels.inbound import EchoHandler, RateLimitedHandler
from app.channels.router import get_conversation, get_inbound_handler
from app.config import Settings
from app.copy import messages_es
from app.pilot import PilotGate
from app.ratelimit import KeyedLocks, RateLimiter, TtlMap
from tests.fakes import FakeChannel

NOTICE = "too many"


@dataclass
class Clock:
    now: float = 1000.0

    def __call__(self) -> float:
        return self.now


def text(sender: str = "59899000001", message_id: str = "wamid.1") -> InboundMessage:
    return InboundMessage(
        kind="text", message_id=message_id, sender=sender, phone_number_id="1", text="hola", raw={}
    )


def album(sender: str = "59899000001") -> InboundMessage:
    return InboundMessage(
        kind="album", message_id="wamid.album", sender=sender, phone_number_id="1", raw={}
    )


def test_a_bucket_allows_its_burst_and_then_refuses() -> None:
    limiter = RateLimiter(burst=3, per_minute=60, clock=Clock())

    assert [limiter.take("a") for _ in range(4)] == [True, True, True, False]
    assert limiter.take("b") is True  # another key has a bucket of its own


def test_a_bucket_refills_with_time_up_to_the_burst() -> None:
    clock = Clock()
    limiter = RateLimiter(burst=2, per_minute=60, clock=clock)  # one token a second
    assert [limiter.take("a") for _ in range(3)] == [True, True, False]

    clock.now += 1
    assert [limiter.take("a") for _ in range(2)] == [True, False]

    clock.now += 3600  # an hour later is still only the burst
    assert [limiter.take("a") for _ in range(3)] == [True, True, False]


def test_the_limiter_never_tracks_more_keys_than_max_keys() -> None:
    limiter = RateLimiter(burst=1, per_minute=1, max_keys=3, clock=Clock())

    for sender in range(50):
        limiter.take(f"sender-{sender}")

    assert len(limiter) == 3


def test_ttl_map_entries_expire() -> None:
    clock = Clock()
    seen = TtlMap[float](ttl_s=10, clock=clock)
    seen.set("a", 1.0)

    clock.now += 9
    assert seen.get("a") == 1.0
    clock.now += 1
    assert seen.get("a") is None
    assert len(seen) == 0


def test_ttl_map_drops_expired_entries_when_it_is_written_and_never_exceeds_max_keys() -> None:
    clock = Clock()
    seen = TtlMap[float](ttl_s=10, max_keys=3, clock=clock)
    seen.set("a", 1.0)
    seen.set("b", 2.0)
    clock.now += 10
    seen.set("c", 3.0)
    assert len(seen) == 1  # a and b expired and were swept

    for key in "defgh":
        seen.set(key, 0.0)
    assert len(seen) == 3
    assert seen.get("c") is None  # the oldest went first


async def test_keyed_locks_serialize_a_key_and_forget_it_afterwards() -> None:
    locks = KeyedLocks()
    inside = 0
    overlap = 0

    async def work(key: str) -> None:
        nonlocal inside, overlap
        async with locks.hold(key):
            inside += 1
            overlap = max(overlap, inside)
            await asyncio.sleep(0)
            inside -= 1

    await asyncio.gather(*(work("a") for _ in range(5)))
    assert overlap == 1
    assert len(locks) == 0


async def test_keyed_locks_forget_a_key_whose_holder_failed() -> None:
    locks = KeyedLocks()

    with pytest.raises(RuntimeError):
        async with locks.hold("a"):
            raise RuntimeError

    assert len(locks) == 0


@dataclass
class RecordingHandler:
    handled: list[InboundMessage] = field(default_factory=list)

    async def handle(self, message: InboundMessage, channel: ChannelPort) -> None:
        self.handled.append(message)


def limited(
    burst: int = 2, clock: Clock | None = None
) -> tuple[RateLimitedHandler, RecordingHandler]:
    inner = RecordingHandler()
    limiter = RateLimiter(burst=burst, per_minute=60, clock=clock or Clock())
    return RateLimitedHandler(inner, limiter, NOTICE), inner


async def test_a_turn_over_the_limit_gets_a_short_reply_and_never_reaches_the_handler() -> None:
    handler, inner = limited(burst=2)
    channel = FakeChannel()

    for number in range(3):
        await handler.handle(text(message_id=f"wamid.{number}"), channel)

    assert [m.message_id for m in inner.handled] == ["wamid.0", "wamid.1"]
    assert channel.sent == [("59899000001", NOTICE)]


async def test_the_notice_is_sent_once_per_throttled_stretch() -> None:
    clock = Clock()
    handler, inner = limited(burst=1, clock=clock)
    channel = FakeChannel()

    for number in range(5):
        await handler.handle(text(message_id=f"wamid.{number}"), channel)
    assert len(channel.sent) == 1

    clock.now += 60  # a token is back: the stretch is over
    await handler.handle(text(message_id="wamid.back"), channel)
    await handler.handle(text(message_id="wamid.again"), channel)

    assert [m.message_id for m in inner.handled] == ["wamid.0", "wamid.back"]
    assert len(channel.sent) == 2


async def test_senders_are_limited_one_by_one() -> None:
    handler, inner = limited(burst=1)
    channel = FakeChannel()

    await handler.handle(text("59899000001"), channel)
    await handler.handle(text("59899000001"), channel)
    await handler.handle(text("59899000002"), channel)

    assert [m.sender for m in inner.handled] == ["59899000001", "59899000002"]


async def test_an_album_announcement_is_free() -> None:
    handler, inner = limited(burst=1)
    channel = FakeChannel()

    for _ in range(3):
        await handler.handle(album(), channel)
    await handler.handle(text(), channel)

    assert len(inner.handled) == 4
    assert channel.sent == []


async def test_an_album_announcement_does_not_end_a_throttled_stretch() -> None:
    handler, inner = limited(burst=1)
    channel = FakeChannel()
    await handler.handle(text(message_id="wamid.ok"), channel)

    for number in range(4):  # a throttled sender alternating albums and texts
        await handler.handle(album(), channel)
        await handler.handle(text(message_id=f"wamid.over{number}"), channel)

    assert channel.sent == [("59899000001", NOTICE)]  # one notice, not one per album


async def test_an_album_flood_stops_reaching_the_handler_and_gets_no_notice() -> None:
    clock = Clock()
    inner = RecordingHandler()
    handler = RateLimitedHandler(
        inner,
        RateLimiter(burst=30, per_minute=10, clock=clock),
        NOTICE,
        albums=RateLimiter(burst=5, per_minute=2, clock=clock),
    )
    channel = FakeChannel()

    for _ in range(20):
        await handler.handle(album(), channel)
    assert len(inner.handled) == 5
    assert channel.sent == []  # dropped silently

    clock.now += 31  # two a minute: one token is back
    for _ in range(3):
        await handler.handle(album(), channel)
    assert len(inner.handled) == 6

    await handler.handle(text(), channel)  # albums don't touch the turn bucket
    assert len(inner.handled) == 7


async def test_a_failing_notice_does_not_break_the_webhook_task() -> None:
    class BrokenChannel(FakeChannel):
        async def send_text(self, to: str, text: str) -> str:
            raise ChannelError("kapso 500")

    handler, inner = limited(burst=1)

    await handler.handle(text(), BrokenChannel())
    await handler.handle(text(), BrokenChannel())

    assert len(inner.handled) == 1


def test_the_real_inbound_handler_is_wrapped_in_the_sender_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Router tests override get_inbound_handler, so only this one sees the production wiring
    # (`get_conversation` wraps the handler, behind the pilot list).
    get_conversation.cache_clear()
    monkeypatch.setattr(
        "app.channels.router.get_settings", lambda: Settings(inbound_handler="echo")
    )
    try:
        gate = get_inbound_handler()
        assert isinstance(gate, PilotGate)
        handler = gate._inner
        assert isinstance(handler, RateLimitedHandler)
        assert isinstance(handler._inner, EchoHandler)
        assert handler._notice == messages_es.RATE_LIMITED
    finally:
        get_conversation.cache_clear()
