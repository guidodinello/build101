"""`BackgroundWork` (ADR 0005): the one place that starts, joins, drains, stops and logs background
tasks.

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


async def test_drain_waits_for_the_work_what_it_starts_and_a_service_told_to_end() -> None:
    background, done, stopping = BackgroundWork(), [], asyncio.Event()

    async def poller() -> None:
        while not stopping.is_set():
            await asyncio.sleep(0.01)

    async def publish() -> None:
        await asyncio.sleep(0.05)
        done.append("publish")

    async def turn() -> None:
        await asyncio.sleep(0.05)
        background.start(publish(), "publish")
        done.append("turn")

    service = background.start_service(poller(), "poller")
    background.start(turn(), "turn")
    stopping.set()
    await background.drain(timeout_s=5)

    assert done == ["turn", "publish"]
    assert service.done() and not service.cancelled()


async def test_drain_cancels_and_logs_by_name_what_is_still_running_at_the_deadline(
    caplog: pytest.LogCaptureFixture,
) -> None:
    background = BackgroundWork()

    async def stuck() -> None:
        await asyncio.sleep(60)

    async def quick() -> None:
        await asyncio.sleep(0)

    late = background.start(stuck(), "post abc12345 for ***1234")
    background.start(quick(), "publish def67890 for ***1234")
    with caplog.at_level(logging.WARNING, logger="app.background"):
        await asyncio.wait_for(background.drain(timeout_s=0.05), timeout=1)

    assert late.cancelled()
    assert "cancelling 1 background tasks: post abc12345 for ***1234" in caplog.text
    assert "def67890" not in caplog.text


SPAWNERS = {"create_task", "ensure_future"}


def spawns(source: str) -> list[int]:
    """Lines calling `create_task` or `ensure_future`, as `asyncio.x(...)` or a bare name."""
    return [
        node.lineno
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and (
            (isinstance(node.func, ast.Attribute) and node.func.attr in SPAWNERS)
            or (isinstance(node.func, ast.Name) and node.func.id in SPAWNERS)
        )
    ]


def test_the_scan_sees_a_spawn_however_it_is_written() -> None:
    assert spawns("import asyncio\nasyncio.create_task(work())") == [2]
    assert spawns("from asyncio import create_task\ncreate_task(work())") == [2]
    assert spawns("from asyncio import ensure_future\nensure_future(work())") == [2]
    assert spawns("import asyncio\nawait asyncio.sleep(0)") == []


def test_only_the_supervisor_starts_tasks() -> None:
    offenders = [
        f"{path.relative_to(APP)}:{line}"
        for path in sorted(APP.rglob("*.py"))
        if path != SUPERVISOR
        for line in spawns(path.read_text())
    ]

    assert offenders == [], f"background work must start in app/background.py: {offenders}"
