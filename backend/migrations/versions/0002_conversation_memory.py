"""The orchestrator's memory: conversation_steps, the conversation summary, owner_notes (ADR 0028)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-18
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = Path(__file__).with_suffix(".sql")


def upgrade() -> None:
    for statement in re.split(r";\s*$", SCHEMA.read_text(), flags=re.MULTILINE):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("drop table if exists owner_notes")
    op.execute("alter table businesses drop column if exists conversation_summary")
    op.execute("drop table if exists conversation_steps")
