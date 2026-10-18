import re
from pathlib import Path

# A line that is only `{{include <path>}}`; the path is relative to the including file.
INCLUDE = re.compile(r"^\{\{include (?P<path>[^}]+)\}\}$")


def load_prompt(path: Path) -> str:
    """The prompt at `path`, with every `{{include <path>}}` line replaced by that file.

    Includes nest. A missing file raises `FileNotFoundError` and a cycle raises `ValueError`.
    Resolve includes before `str.format`: the fragments hold no braces except placeholders.
    """
    return _compose(path.resolve(), ())


def _compose(path: Path, including: tuple[Path, ...]) -> str:
    if path in including:
        chain = " -> ".join(p.name for p in (*including, path))
        raise ValueError(f"include cycle: {chain}")
    lines: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = INCLUDE.match(line.strip())
        if match:
            target = (path.parent / match["path"].strip()).resolve()
            lines.append(_compose(target, (*including, path)))
        else:
            lines.append(line)
    return "\n".join(lines)
