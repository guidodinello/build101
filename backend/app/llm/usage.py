"""What one model call used, as the provider reported it, on its way to the ledger (#205)."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Usage:
    """`input_tokens` includes the cached ones; `output_tokens` excludes thinking, which is
    `thought_tokens`."""

    input_tokens: int | None = None
    cached_tokens: int | None = None
    thought_tokens: int | None = None
    output_tokens: int | None = None
    image_size: str | None = None
    image_count: int | None = None
    video_seconds: int | None = None
    service_tier: str | None = None
    stop_reason: str | None = None


_reported: ContextVar[list[Usage] | None] = ContextVar("reported_usage", default=None)


def report_usage(usage: Usage) -> None:
    """Called by a text adapter: what the metered call in progress used. Outside one, nothing."""
    slot = _reported.get()
    if slot is not None:
        slot.append(usage)


@contextmanager
def collecting() -> Iterator[list[Usage]]:
    """What `report_usage` receives inside, in order."""
    reported: list[Usage] = []
    token = _reported.set(reported)
    try:
        yield reported
    finally:
        _reported.reset(token)
