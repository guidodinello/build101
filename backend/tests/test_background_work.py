"""`BackgroundWork` (ADR 0005): the one place that starts, joins, stops and logs background tasks.

The scan at the bottom keeps it the only one: no other module under `app/` calls
`asyncio.create_task`.
"""

import ast
import asyncio
import logging
from pathlib import Path

import pytest

from app.background import BackgroundWork

APP = Path(__file__).resolve().parent.parent / "app"
SUPERVISOR = APP / "background.py"


async def test_join_waits_for_the_work_and_what_it_starts_meanwhile() -> None:
    background, done = BackgroundWork(), []

    async def second() -> None:
        await asyncio.sleep(0)
        done.append("second")

    async def first() -> None:
        background.start(second(), "second")
        done.append("first")

    background.start(first(), "first")
    await background.join()

    assert done == ["first", "second"]


async def test_a_failure_is_logged_with_the_name_and_never_escapes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    background = BackgroundWork()

    async def boom() -> None:
        raise ValueError("kaput")

    with caplog.at_level(logging.ERROR, logger="app.background"):
        task = background.start(boom(), "post abc12345 for ***1234")
        await background.join()

    assert task.exception() is None
    assert "post abc12345 for ***1234" in caplog.text
    assert "kaput" in caplog.text


async def test_join_does_not_wait_for_a_service_and_stop_cancels_it() -> None:
    background, ticks = BackgroundWork(), []

    async def poller() -> None:
        while True:
            ticks.append(1)
            await asyncio.sleep(0.01)

    service = background.start_service(poller(), "poller")
    await asyncio.sleep(0.03)
    await asyncio.wait_for(background.join(), timeout=1)

    assert not service.done()

    await background.stop()

    assert service.cancelled()
    assert ticks


async def test_stop_cancels_the_work_in_flight() -> None:
    background, finished = BackgroundWork(), []

    async def slow() -> None:
        await asyncio.sleep(10)
        finished.append(1)

    task = background.start(slow(), "slow")
    await asyncio.sleep(0)
    await background.stop()

    assert task.cancelled()
    assert finished == []


def test_only_the_supervisor_starts_tasks() -> None:
    offenders = [
        f"{path.relative_to(APP)}:{node.lineno}"
        for path in sorted(APP.rglob("*.py"))
        if path != SUPERVISOR
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"create_task", "ensure_future"}
    ]

    assert offenders == [], f"background work must start in app/background.py: {offenders}"
