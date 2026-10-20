"""Abuse limits for the single instance (ADR 0005): in-process, stdlib only, bounded in memory.

Nothing here survives a restart or is shared between workers, which is fine for `--workers 1`.
"""

import asyncio
import time
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from app.api.errors import ApiError
from app.onboarding.links import hash_token

MAX_TRACKED_KEYS = 10_000

# WhatsApp turns per sender: a full album of photos fits in the burst, a human typing never
# reaches the refill.
TURNS_BURST = 30
TURNS_PER_MINUTE = 10
# An album announcement costs no turn, but a sender can't send them without end either.
ALBUM_BURST = 5
ALBUM_PER_MINUTE = 2

# Wizard API calls per link token: the wizard polls every 3 s while photos are analyzed, and
# uploads cost two calls per photo.
ONBOARDING_BURST = 120
ONBOARDING_PER_MINUTE = 120
TOO_MANY_REQUESTS = "Vas muy rápido 🙈 Esperá un minuto y probá de nuevo."


class RateLimiter:
    """A token bucket per key: `burst` tokens at most, `per_minute` refilled each minute.

    Past `max_keys` the least recently used bucket is forgotten and comes back full, so eviction
    can only loosen the limit for one key, never grow memory.
    """

    def __init__(
        self,
        burst: int,
        per_minute: float,
        max_keys: int = MAX_TRACKED_KEYS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._burst = float(burst)
        self._refill_per_s = per_minute / 60
        self._max_keys = max_keys
        self._clock = clock
        self._buckets: OrderedDict[str, tuple[float, float]] = OrderedDict()

    def take(self, key: str) -> bool:
        """Spend one token; False (and nothing spent) when the bucket is empty."""
        now = self._clock()
        tokens, updated = self._buckets.pop(key, (self._burst, now))
        tokens = min(self._burst, tokens + (now - updated) * self._refill_per_s)
        allowed = tokens >= 1
        self._buckets[key] = (tokens - 1 if allowed else tokens, now)
        if len(self._buckets) > self._max_keys:
            self._buckets.popitem(last=False)
        return allowed

    def __len__(self) -> int:
        return len(self._buckets)


class TtlMap[V]:
    """A dict whose entries expire after `ttl_s` and that never holds more than `max_keys`."""

    def __init__(
        self,
        ttl_s: float,
        max_keys: int = MAX_TRACKED_KEYS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_s = ttl_s
        self._max_keys = max_keys
        self._clock = clock
        # Insertion order is expiry order: a set moves the key to the end with a fresh deadline.
        self._items: OrderedDict[str, tuple[V, float]] = OrderedDict()

    def set(self, key: str, value: V) -> None:
        now = self._clock()
        self._items.pop(key, None)
        self._items[key] = (value, now + self._ttl_s)
        while self._items and (
            len(self._items) > self._max_keys or next(iter(self._items.values()))[1] <= now
        ):
            self._items.popitem(last=False)

    def get(self, key: str) -> V | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry[1] <= self._clock():
            del self._items[key]
            return None
        return entry[0]

    def __len__(self) -> int:
        return len(self._items)


@dataclass(slots=True)
class _KeyedLock:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0  # holders plus waiters


class KeyedLocks:
    """One `asyncio.Lock` per key, dropped as soon as nobody holds or waits for it."""

    def __init__(self) -> None:
        self._entries: dict[str, _KeyedLock] = {}

    @asynccontextmanager
    async def hold(self, key: str) -> AsyncIterator[None]:
        entry = self._entries.setdefault(key, _KeyedLock())
        entry.users += 1
        try:
            async with entry.lock:
                yield
        finally:
            entry.users -= 1
            if entry.users == 0:
                del self._entries[key]

    def __len__(self) -> int:
        return len(self._entries)


onboarding_limiter = RateLimiter(ONBOARDING_BURST, ONBOARDING_PER_MINUTE)


async def limit_onboarding_token(token: str) -> None:
    """Dependency of every `/api/o/{token}/...` route; keyed on the token's hash."""
    if not onboarding_limiter.take(hash_token(token)):
        raise ApiError(429, "rate_limited", TOO_MANY_REQUESTS)
