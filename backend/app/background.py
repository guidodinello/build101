"""In-process background work (ADR 0005): the one place that starts it, waits for it and stops it.

Nobody awaits a background task, so a failure that escapes its coroutine is logged here, once.
Work that turns a failure into something else (a `PostFailed` event, a failed `jobs` row) keeps
its own `except`: that outcome is its own, and this boundary is only the last resort.
"""

import asyncio
import logging
from collections.abc import Coroutine
from functools import cache
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundWork:
    """Starts coroutines as tasks, keeps them alive, and waits for or cancels them together.

    `start` is finite work (a post, a publish, a job, a debounce timer). `start_service` is a loop
    that runs until `stop` (the job poller): `join` doesn't wait for it, or it would never return.
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()
        self._services: set[asyncio.Task[None]] = set()

    def start(self, work: Coroutine[Any, Any, None], name: str) -> asyncio.Task[None]:
        return self._spawn(work, name, self._tasks)

    def start_service(self, loop: Coroutine[Any, Any, None], name: str) -> asyncio.Task[None]:
        return self._spawn(loop, name, self._services)

    async def join(self) -> None:
        """Wait for the finite work, including what it starts meanwhile (tests)."""
        # `done()` and not just membership: a finished task leaves the set one loop turn later, and
        # gathering only finished tasks returns without yielding, which would spin forever.
        while pending := [task for task in self._tasks if not task.done()]:
            await asyncio.gather(*pending, return_exceptions=True)

    async def stop(self) -> None:
        """Cancel everything, services included, and wait for it to end (shutdown)."""
        # Again until nothing is left: a task cancelled in the middle of its work may start more.
        while running := [task for task in (*self._tasks, *self._services) if not task.done()]:
            for task in running:
                task.cancel()
            await asyncio.gather(*running, return_exceptions=True)

    def _spawn(
        self, work: Coroutine[Any, Any, None], name: str, group: set[asyncio.Task[None]]
    ) -> asyncio.Task[None]:
        task = asyncio.create_task(_guarded(work, name), name=name)
        group.add(task)
        task.add_done_callback(group.discard)
        # Cancelled before its first step, the guard never awaits `work`: close it, or Python warns.
        task.add_done_callback(lambda _: work.close())
        return task


async def _guarded(work: Coroutine[Any, Any, None], name: str) -> None:
    try:
        await work
    except Exception:
        logger.exception("background work %s failed", name)


@cache
def get_background_work() -> BackgroundWork:
    """The process's one instance, shared by the webhook handler and the job runner."""
    return BackgroundWork()
