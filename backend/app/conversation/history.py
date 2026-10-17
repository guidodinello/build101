import asyncio
from collections import defaultdict

from app.llm.client import Step

MAX_HISTORY_STEPS = 40  # keeps prompts small; older turns are dropped


class InMemoryHistory:
    """LLM history per sender until T02 stores it in `messages`. Lost on restart (ADR 0005)."""

    def __init__(self, max_steps: int = MAX_HISTORY_STEPS) -> None:
        self._max_steps = max_steps
        self._steps: defaultdict[str, list[Step]] = defaultdict(list)
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def lock(self, sender: str) -> asyncio.Lock:
        """Hold it for a whole turn: one sender's messages are answered one at a time."""
        return self._locks[sender]

    def get(self, sender: str) -> list[Step]:
        return list(self._steps[sender])

    def extend(self, sender: str, steps: list[Step]) -> None:
        history = self._steps[sender]
        history.extend(steps)
        del history[: -self._max_steps]
        # A trimmed history must still start with a user turn.
        while history and history[0].get("type") != "user_input":
            history.pop(0)
