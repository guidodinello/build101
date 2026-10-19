"""ADR 0007 in one place: only `posts/lifecycle.py` assigns a Post's status.

The scan is scoped to Post by directory, not by name: it reads every module under `app/posts` and
`app/conversation` (where Posts are made, approved and published) and flags an assignment to any
`<expr>.status` outside the lifecycle module. Other models' `status` (assets, Instagram accounts,
jobs) live under `api/`, `jobs/` and `instagram/`, which are not scanned. A scanned module with a
non-Post `.status` write would have to be named in `NOT_A_POST` below (empty today). A `status=`
keyword in a constructor call (`Post(..., status=...)`) is a call, not an assignment, and passes.
"""

import ast
from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
SCANNED = ("posts", "conversation")
LIFECYCLE = APP / "posts" / "lifecycle.py"
NOT_A_POST: frozenset[tuple[str, int]] = frozenset()  # (path relative to app/, line)


def status_writes(path: Path) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(ast.parse(path.read_text())):
        match node:
            case ast.Assign(targets=targets):
                targets_written = targets
            case ast.AugAssign(target=target) | ast.AnnAssign(target=target):
                targets_written = [target]
            case _:
                continue
        lines += [
            node.lineno
            for target in targets_written
            if isinstance(target, ast.Attribute) and target.attr == "status"
        ]
    return lines


def test_no_module_but_the_lifecycle_assigns_a_posts_status() -> None:
    offenders = [
        f"{path.relative_to(APP)}:{line}"
        for directory in SCANNED
        for path in sorted((APP / directory).rglob("*.py"))
        if path != LIFECYCLE
        for line in status_writes(path)
        if (str(path.relative_to(APP)), line) not in NOT_A_POST
    ]

    assert offenders == [], f"Post.status is assigned outside posts/lifecycle.py: {offenders}"


def test_the_scan_sees_the_lifecycles_own_writes() -> None:
    assert status_writes(LIFECYCLE), "the scan would pass on any module if it saw no writes"
