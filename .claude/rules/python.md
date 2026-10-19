---
paths:
  - "**/*.py"
  - "**/pyproject.toml"
---

> Adapted from [guidodinello/claude-dotfiles `rules/python.md`](https://github.com/guidodinello/claude-dotfiles/blob/main/.claude/rules/python.md) (MIT, see [THIRD_PARTY_NOTICES](../THIRD_PARTY_NOTICES.md)).

# Python Project — Agent Code Guidelines

General-purpose guidelines for Python projects where AI agents assist with
development. As a path-scoped rule it self-loads on `.py` / `pyproject.toml`
— never copy it into a project's `AGENTS.md`. build101 values are in
"Project-specific notes" at the bottom.

---

## Philosophy

Python has an explicit design philosophy. When in doubt, run `import this`. The
most load-bearing principles for daily work:

- **Explicit is better than implicit** — no magic, no hidden state, no
  surprising side-effects. If a function does something non-obvious, a name or
  comment should say so.
- **Simple is better than complex** — the right solution is usually the least
  code that correctly solves the problem, not the most flexible abstraction.
- **Readability counts** — code is read far more often than it is written.
  Optimise for the reader.
- **Errors should never pass silently** — fail loudly and early. Don't swallow
  exceptions or return `None` where an error is the right answer.
- **If the implementation is hard to explain, it's a bad idea** — complexity is
  a warning sign, not a badge of honour.

---

## Software engineering principles

### YAGNI — You Aren't Gonna Need It

Don't add features, abstractions, or configurability for hypothetical future
requirements. Build what the task actually needs. If the requirement arrives
later, add it then.

```python
# Bad — parameterised "for future flexibility"
def send_reply(text, channel="default", retries=0, template=None, locale=None, ...):
    ...

# Good — add parameters when there's an actual reason to vary them
def send_reply(text: str, channel: str) -> None:
    ...
```

### DRY — Don't Repeat Yourself (but don't over-apply it)

Duplicate code is a maintenance hazard. Extract shared logic — but only once you
see the same thing repeated at least three times and are confident the
repetition isn't coincidental. Premature abstraction is worse than duplication.

### SSOT — Single Source of Truth

Every piece of knowledge — a constant, a schema, a business rule — should have
exactly one authoritative definition. Everything else derives from or references
that definition; nothing duplicates it.

Violations manifest as drift: two places that *should* agree but don't, because
one was updated and the other wasn't.

```python
# Bad — the valid states are defined twice; the list and the Enum can drift
VALID_STATES = ["pending", "active", "closed"]

class Status(Enum):
    PENDING = "pending"
    ACTIVE  = "active"
    CLOSED  = "closed"

def is_valid(state: str) -> bool:
    return state in VALID_STATES  # duplicates knowledge already in Status

# Good — one definition; the validation derives from it
class Status(Enum):
    PENDING = "pending"
    ACTIVE  = "active"
    CLOSED  = "closed"

def is_valid(state: str) -> bool:
    return state in {s.value for s in Status}
```

Apply SSOT to schemas too — don't define the same shape in a dataclass *and* a
serialisation dict and a validation function. Define the dataclass; let the
others derive:

```python
# Bad — field names duplicated in the dataclass and the serialiser
@dataclass
class Config:
    reply_timeout_s: float
    max_reply_chars: int

def to_dict(cfg: Config) -> dict:
    return {"reply_timeout_s": cfg.reply_timeout_s, "max_reply_chars": cfg.max_reply_chars}  # will drift on rename

# Good — derive the dict automatically
import dataclasses

def to_dict(cfg: Config) -> dict:
    return dataclasses.asdict(cfg)
```

The test: if renaming or removing one thing requires finding and updating a
second place, you have two sources of truth.

### KISS — Keep It Simple

Prefer a flat structure over a deep hierarchy. Prefer a function over a class.
Prefer a class over a framework. Each layer of indirection has a cost; make sure
it earns it.

Jack Diederich's rule: *if you can't explain what the class does without using
the word "manager", "handler", or "helper" — it probably shouldn't be a class.*

### Single responsibility

Functions and classes should do one thing. If a function's docstring needs the
word "and", consider splitting it. If a class has methods that don't share any
state, consider splitting it into free functions.

The naming test: if you can't find a single, precise name that covers everything
a function does, it's doing too much. A function is a set of semantically
related actions — finding the name is how you verify they belong together.

```python
# Bad — the name has to say "and", revealing two responsibilities
def validate_and_save_user(user: User) -> None: ...

# Good — each function has one job and a name that fits it exactly
def validate_user(user: User) -> None: ...
def save_user(user: User) -> None: ...
```

### Locality of Behavior

Code that changes together should live together. A reader should be able to
understand a behavior by reading one place, not by chasing references across
files.

- Define constants near the code that uses them — not in a shared `constants.py`
  that becomes a catch-all.
- Keep validators next to the data structures they validate.
- Keep a helper function adjacent to its only caller rather than hoisting it to
  a utilities module it doesn't belong in.
- Subsystem configuration belongs in the subsystem, not scattered across a
  top-level config file.

The test: if understanding one behavior requires opening more than two files,
the behavior has too much distance.

```python
# Bad — MAX_RETRIES lives far from where it's used; reader has to go find it
# constants.py
MAX_RETRIES = 3

# network.py
from mypackage.constants import MAX_RETRIES

def fetch(url: str) -> bytes: ...

# Good — constant lives next to its only user
# network.py
_MAX_RETRIES = 3

def fetch(url: str) -> bytes: ...
```

### Fail fast

Validate inputs at the boundary (user input, external APIs, file I/O). Inside
the system, trust your own invariants and let unexpected states raise
immediately rather than propagating silently.

```python
# Bad — silently returns wrong results
def divide(a, b):
    if b == 0:
        return 0

# Good — caller learns about the problem immediately
def divide(a: float, b: float) -> float:
    if b == 0:
        raise ValueError(f"divide: b must be non-zero, got {b}")
    return a / b
```

---

## Running the project

The uv project lives in `backend/`; run these commands from there. Exception:
`pre-commit install` and `.pre-commit-config.yaml` belong at the repo root,
since git hooks are repository-wide.

```bash
uv pip install -e .          # editable install — do this once on a fresh clone
uv run ruff check .          # lint (must be clean before committing)
uv run ruff check --fix .    # auto-fix what ruff can
uv run pyright               # type check, standard mode (must report 0 errors before committing)
uv run pytest tests/ -v      # run test suite (must be green before committing)
pre-commit install           # install git hooks (once per clone)
```

**Never invoke `python3` directly.** Always use `uv run python`, or
`uv run <script>`, so the uv-managed virtual environment and pinned
dependencies are used.

```bash
# Good
uv run python scripts/load_demo_data.py
uv run python -c "import mypackage; print(mypackage.__file__)"

# Bad — bypasses the venv
python3 scripts/load_demo_data.py
```

---

## Imports

**Never use `sys.path.insert` or `sys.path.append`.** Install the project as an
editable package (`uv pip install -e .`) and use a proper build backend
(`hatchling`, `setuptools`, etc.) so all packages are importable without path
manipulation.

```python
# Good
from mypackage.core import MyClass

# Bad
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import MyClass
```

Import order (enforced by ruff/isort): stdlib → third-party → first-party. Use
**relative imports** inside a package, **absolute imports** across packages.

Don't use `from module import *`. It pollutes the namespace and makes it
impossible to tell where a name came from without reading the source.

---

## Logging

**Never use `print()` for status, progress, or diagnostic output.** Use the
stdlib `logging` module with a two-handler setup (stdout + rotating file).

```python
import logging
import sys
from pathlib import Path

def get_logger(name: str, log_file: Path | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s %(levelname)-8s %(name)s — %(message)s")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    logger.setLevel(logging.INFO)
    return logger
```

Use `%`-style formatting in logger calls — it defers string construction until
the message is actually emitted:

```python
logger.info("processed %d items in %.2fs", count, elapsed)  # good
logger.info(f"processed {count} items in {elapsed:.2f}s")   # bad — always evaluated
```

`print()` is acceptable only for structured output that is the *primary product*
of a script (e.g. a formatted report or table).

---

## Type annotations

Annotate all public functions with parameter types and return types.

```python
# Good
def format_reply(text: str, max_chars: int, locale: str) -> str: ...
def load_settings(path: Path, env: str = "dev") -> Settings: ...

# Bad
def format_reply(text, max_chars, locale): ...
```

pyright runs in CI (standard mode, `app/` and `migrations/`; config in `pyproject.toml`). When a
library's stubs are wrong, suppress with a scoped ignore and say why on the line or the line above;
never a bare `# type: ignore`. `reportUnnecessaryTypeIgnoreComment` is on, so an ignore that stops
being needed fails the check.

```python
# Pillow stubs: `getextrema()` is `float | tuple[int, int]`; a single band gives ints.
low = alpha.getextrema()[0]  # pyright: ignore[reportOperatorIssue]
```

Use modern Python 3.10+ syntax — never `Optional`, `List`, `Dict`, `Union`, or
`Tuple` from `typing`:

```python
# Good
def process(items: list[int], mapping: dict[str, int]) -> tuple[int, ...]: ...
def find(value: int | None = None) -> str | None: ...

# Bad
from typing import Optional, List, Dict
def process(items: List[int], mapping: Dict[str, int]) -> Optional[str]: ...
```

---

## Dataclasses and immutability

Use `@dataclass(slots=True)` for all new dataclasses — it catches attribute
typos at class definition time and reduces memory footprint.

Use `@dataclass(frozen=True, slots=True)` for data that is set once and never
mutated.

```python
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Config:              # immutable — set once and passed around
    reply_timeout_s: float
    max_reply_chars: int

@dataclass(slots=True)
class ConversationState:   # mutable — updated on every message
    turn: int
    last_intent: str
```

Prefer `tuple` over `list` for fields that are never mutated after construction.
Always write full container type hints — never bare `list` or `dict`:

```python
# Good
attachments: list[Path]
intent_scores: dict[str, float]

# Bad
attachments: list
intent_scores: dict
```

---

## Protocols instead of ABCs

Use `typing.Protocol` with `@runtime_checkable` to define structural interfaces.
Concrete classes satisfy the protocol structurally — they do **not** inherit
from it.

```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class ChannelAdapter(Protocol):
    def send(self, chat_id: str, text: str) -> None: ...
    def close(self) -> None: ...
```

```python
class ConsoleAdapter:       # no inheritance — satisfies ChannelAdapter structurally
    def send(self, chat_id: str, text: str) -> None:
        logger.info("[%s] %s", chat_id, text)
    def close(self) -> None:
        pass

assert isinstance(ConsoleAdapter(), ChannelAdapter)  # True at runtime
```

Use ABCs only when concrete classes genuinely share implementation, not just an
interface.

---

## Named constants

Never embed raw magic numbers or strings in logic. Define named constants at
module level, near the code that uses them.

```python
# Good
MAX_RETRIES = 3
MAX_REPLY_CHARS = 4_096
REPLY_TIMEOUT_S = 10.0

reply = truncate(text, max_chars=MAX_REPLY_CHARS)

# Bad
reply = truncate(text, max_chars=4096)
```

Use `Enum` for values that belong to a fixed, named set:

```python
from enum import IntEnum, auto

class ConversationPhase(IntEnum):
    GREETING = auto()
    HANDLING = auto()
    DONE = auto()
```

---

## Path handling

**Always use `pathlib.Path` — never bare strings for file paths.**

```python
from pathlib import Path

# Good
ROOT = Path(__file__).resolve().parent.parent
EXPORT_DIR = ROOT / "exports"
report.write(str(EXPORT_DIR / f"report_{day}.csv"))  # str() only at the API boundary

# Bad
export_dir = "/home/user/project/exports"
path = export_dir + "/" + f"report_{day}.csv"
```

Use `/` for joining, `.parent` for navigation, `.stem`/`.suffix`/`.name` for
introspection. Convert to `str` only when a third-party API requires it.

---

## Prefer the standard library

**Before writing a utility, check if the stdlib already has it.** Custom
implementations are harder to read, harder to test, and don't benefit from
CPython optimisation. The rule: **stdlib first, third-party second, in-house
last.**

### functools — caching and higher-order functions

Never write a manual cache dict when `@cache` works:

```python
# Bad
_cache: dict = {}
def expensive(x: int) -> int:
    if x not in _cache:
        _cache[x] = _compute(x)
    return _cache[x]

# Good
from functools import cache

@cache
def expensive(x: int) -> int:
    return _compute(x)
```

Other tools worth knowing: `partial` (fix some arguments of a function), `wraps`
(preserve metadata in decorators), `reduce` (fold a sequence).

### itertools — iteration without manual loops

```python
from itertools import chain, combinations, takewhile, groupby

# Flatten a list of lists
all_items = list(chain.from_iterable(nested))

# All pairs from a collection
pairs = list(combinations(items, 2))

# Take while condition holds
prefix = list(takewhile(lambda x: x > 0, values))
```

### contextlib — context managers without boilerplate

Use `@contextmanager` instead of a class with `__enter__`/`__exit__` for simple
cases:

```python
from contextlib import contextmanager, suppress
import time

@contextmanager
def timed(label: str):
    t0 = time.perf_counter()
    yield
    logger.info("%s: %.3fs", label, time.perf_counter() - t0)

with timed("data loading"):
    data = load(path)

# Suppress a specific exception cleanly
with suppress(FileNotFoundError):
    cache_path.unlink()
```

### timeit — micro-benchmarks

Use `timeit` for measuring small snippets rather than wrapping them in manual
`perf_counter` loops:

```python
import timeit

t = timeit.timeit("my_function(x)", setup="from mymodule import my_function; x = 42", number=10_000)
print(f"{t / 10_000 * 1e6:.2f} µs per call")
```

For whole-script profiling: `uv run python -m cProfile -s cumtime script.py`.

---

## Configuration

When a function takes more than ~4 settings parameters, bundle them into a typed
dataclass config object:

```python
@dataclass(slots=True)
class MessageHandlingConfig:
    reply_timeout_s: float = 10.0
    max_reply_chars: int = 4_096
    max_history_turns: int = 20
    default_locale: str = "en"
    transcript_dir: Path = Path("transcripts")

def handle_message(text: str, cfg: MessageHandlingConfig) -> str:
    logger.info("timeout=%s max_chars=%d locale=%s", cfg.reply_timeout_s, cfg.max_reply_chars, cfg.default_locale)
    ...
```

Argparse stays at the CLI boundary and populates the config:

```python
def main() -> None:
    args = parser.parse_args()
    cfg = MessageHandlingConfig(reply_timeout_s=args.timeout, max_reply_chars=args.max_chars)
    run(cfg)
```

Reach for `pydantic-settings` only when you need config from multiple sources
(env vars + YAML + CLI) with merge priority and validation error messages. For
scripts and small tools, a plain dataclass is simpler and sufficient.

---

## Python idioms

### Underscore conventions

Python uses underscores as a communication tool — use them consistently:

```python
# Throwaway variable — signals "I don't care about this value"
_, important = some_tuple()
for _ in range(3):
    retry()

# Star-unpacking with throwaway — grab first and last, ignore middle
first, *_, last = my_long_tuple

# Numeric literals — use underscores for readability in large numbers
MAX_UPLOAD_BYTES = 25_000_000
REPLY_TIMEOUT_S = 10.0
MAX_QUEUE_SIZE = 1_000

# _single_leading: protected by convention (not enforced), signals "internal use"
self._client = None

# __double_leading: triggers name mangling — use only when you explicitly need
# to prevent subclass accidental override. Not a general privacy mechanism.
```

### @property, @staticmethod, @classmethod

Use each for the right reason:

```python
class Conversation:
    # @property — attribute-style access for cheap, derived values
    # Never do heavy computation or I/O inside a property
    @property
    def is_open(self) -> bool:
        return self._closed_at is None      # fast, pure

    # @staticmethod — logically belongs to the class but needs no instance or class state
    @staticmethod
    def max_history_turns() -> int:
        return MAX_HISTORY_TURNS

    # @classmethod — alternative constructors or factory methods that need the class itself
    @classmethod
    def from_transcript(cls, path: Path) -> "Conversation":
        conversation = cls()
        conversation._messages = load(path)
        return conversation

    # Plain method — needs instance state (self)
    def last_message(self) -> str:
        return self._messages[-1]
```

If a method doesn't use `self` or `cls`, it should be `@staticmethod` (or a free
function if it doesn't conceptually belong to the class).

### Custom decorators

When writing a decorator, always use `functools.wraps` to preserve the wrapped
function's name and docstring:

```python
from functools import wraps
import time

def timed(fn):
    @wraps(fn)          # without this, fn.__name__ becomes "wrapper"
    def wrapper(*args, **kwargs):
        t0 = time.perf_counter()
        result = fn(*args, **kwargs)
        logger.info("%s took %.3fs", fn.__name__, time.perf_counter() - t0)
        return result
    return wrapper

@timed
def summarize_day(day: date) -> dict: ...
```

---

## Code smells to avoid

These patterns are warning signs that the design needs rethinking:

- **Mutable default arguments** — Python evaluates defaults once at import time:

  ```python
  def append(item, lst=[]):  # Bad — lst is shared across all calls
      lst.append(item)
      return lst

  def append(item, lst=None):  # Good
      if lst is None:
          lst = []
      lst.append(item)
      return lst
  ```

- **Boolean flags that select behaviour** — split into two functions instead:

  ```python
  def process(data, verbose=True):  # Bad — two functions in a trenchcoat
      ...

  def process(data): ...        # Good
  def process_verbose(data): ... # Good
  ```

- **Catching generic exceptions** — always catch the specific exception you
  expect:

  ```python
  try:                          # Bad
      result = load(path)
  except Exception:
      result = None

  try:                          # Good
      result = load(path)
  except FileNotFoundError:
      result = None
  ```

- **Heavy logic in properties** — properties should feel like attribute access;
  if computation is expensive, use an explicit method instead.

- **Deeply nested comprehensions** — if a list comprehension needs more than one
  `for` clause or a non-trivial condition, a regular loop is clearer.

- **Classes with no shared state** — if every method could be a free function,
  it probably should be. (See: Jack Diederich, *Stop Writing Classes*.)

- **Redundant temp variables** — avoid assigning a variable only to pass it as a
  named argument with the same name, or when the variable name adds nothing over
  the expression itself:

  ```python
  # Bad — variable mirrors the parameter name, adds no information
  s = await reports.compute_summary(business, day)
  return DailySummaryResponse(summary=s)

  # Good — inline it
  return DailySummaryResponse(
      summary=await reports.compute_summary(business, day)
  )

  # Fine — name adds meaning beyond what the expression communicates
  active_users = [u for u in users if u.is_active and u.confirmed_email]
  notify_all(active_users)
  ```

- **Mutable module-level state** — module globals that get mutated are hidden
  shared state. They break encapsulation, make testing hard, and cause subtle
  bugs across imports. Constants (`ALL_CAPS`) are fine; mutable dicts and lists
  at module scope are not.

- **`assert` for input validation** — `assert` is disabled with `python -O` and
  must never be used for validation. Use `ValueError` or `TypeError` at
  boundaries:

  ```python
  # Bad — silently skipped in optimised builds
  assert user_id > 0, "user_id must be positive"

  # Good
  if user_id <= 0:
      raise ValueError(f"user_id must be positive, got {user_id}")
  ```

---

## Exception handling

### Raise low, catch high

Lower-level functions should raise specific, descriptive exceptions and let them
propagate. Only catch at system edges — CLI entry points, request handlers,
event loop callbacks — where you have enough context to decide what to do.

```python
# Bad — swallows the error mid-stack, caller can't recover
def load_user(user_id: int) -> User:
    try:
        return db.get(user_id)
    except Exception:
        return None  # caller has no idea what went wrong

# Good — raise specifically, catch at the handler boundary
def load_user(user_id: int) -> User:
    return db.get(user_id)  # let DBError propagate

async def handle_request(user_id: int) -> Response:
    try:
        user = load_user(user_id)
    except DBError as e:
        logger.exception("DB lookup failed for user %d", user_id)
        return Response(500)
```

### Custom domain exceptions

Define a base exception per package so callers can catch your errors
specifically without catching everything:

```python
class AppError(Exception):
    """Base for all application errors."""

class AuthError(AppError):
    """Session expired or token invalid."""

class NotFoundError(AppError):
    """Requested resource does not exist."""
```

Prefer built-in exceptions (`ValueError`, `TypeError`, `FileNotFoundError`) for
generic programming errors. Use custom exceptions for domain concepts.

---

## Async

### Never block the event loop

`time.sleep()`, synchronous HTTP calls, and CPU-bound work stall every other
coroutine. Use async-native alternatives or offload to a thread:

```python
# Bad — blocks the entire event loop
import time
async def wait():
    time.sleep(5)

# Good
import asyncio
async def wait():
    await asyncio.sleep(5)

# Good — offload blocking I/O to a thread pool
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, blocking_function, arg)
```

### Store `asyncio.create_task()` results

Tasks not referenced by a variable can be garbage-collected and silently
canceled before they finish. Always keep a reference:

```python
# Bad — task may be GC'd before completion
asyncio.create_task(background_job())

# Good
task = asyncio.create_task(background_job())
# keep `task` alive (store on self, in a set, etc.)
```

### Prefer `asyncio.Queue` for producer-consumer patterns

`asyncio.Queue` decouples producers from consumers cleanly and handles
backpressure without manual coordination:

```python
queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)

async def producer() -> None:
    async for item in source:
        await queue.put(item)

async def consumer() -> None:
    while True:
        item = await queue.get()
        await process(item)
        queue.task_done()
```

---

## Generators

### Generator expressions over list comprehensions

When the caller only iterates the result, pass a generator expression instead of
building a full list in memory:

```python
# Bad — materialises the whole list
total = sum([x * x for x in range(1_000_000)])

# Good — streams one element at a time
total = sum(x * x for x in range(1_000_000))
```

### `yield from` for delegation

Replace manual loops that re-yield from a sub-iterator with `yield from`:

```python
# Bad
def flatten(nested):
    for sublist in nested:
        for item in sublist:
            yield item

# Good
def flatten(nested):
    for sublist in nested:
        yield from sublist
```

---

## Tests

Every non-trivial module needs tests. Minimum coverage:

- **Happy path** — does the function return the right thing for normal input?
- **Edge cases** — empty collections, zero, `None`, boundary values.
- **Invariants** — properties that must always hold (e.g. output shape, value
  bounds).

```bash
uv run pytest tests/ -v   # from backend/
```

Structure (under `backend/`):

```text
tests/
  test_core.py       # unit tests for core logic
  test_integration.py  # end-to-end or multi-module tests
```

---

## Linting

ruff is the single linter and formatter. Suggested configuration for
`pyproject.toml`:

```toml
[tool.ruff]
target-version = "py313"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]
ignore = ["SIM108"]  # ternary not always clearer

[tool.ruff.lint.isort]
known-first-party = []  # set to the backend package name once chosen
```

Pre-commit hook:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.11.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
```

Run `uv run ruff check --fix .` before every commit. Inline `# noqa` is a last
resort — prefer `per-file-ignores` in `pyproject.toml` with a comment explaining
why.

---

## Project-specific notes

| Item | Value |
| ------ | ------- |
| Python version | 3.13 |
| Package manager | uv |
| Framework | FastAPI |
| Source root | `backend/` |
| Build backend | TBD |
| Test runner | pytest |
| Linter/formatter | ruff |
| Type checker | pyright, standard mode (`[tool.pyright]` in `backend/pyproject.toml`) |
| Database / ORM | PostgreSQL (Supabase) + SQLAlchemy 2 async + Alembic — see [ADR 0003](../../docs/decisions/0003-database-supabase-sqlalchemy.md) |

FastAPI-specific conventions are not yet defined; record them as an ADR in
[`docs/decisions/`](../../docs/decisions/README.md) when decided.
