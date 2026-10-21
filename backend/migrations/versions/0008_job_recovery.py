"""Recover interrupted jobs: jobs.attempts and jobs.retry_offered_at (#178)

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-20
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = Path(__file__).with_suffix(".sql")


def upgrade() -> None:
    for statement in re.split(r";\s*$", SCHEMA.read_text(), flags=re.MULTILINE):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("alter table jobs drop constraint if exists ck_jobs_attempts_not_negative")
    op.execute("alter table jobs drop column if exists retry_offered_at")
    op.execute("alter table jobs drop column if exists attempts")
