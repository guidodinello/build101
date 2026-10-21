"""The closed pilot: the pilot_senders table (#186)

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-20
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = Path(__file__).with_suffix(".sql")


def upgrade() -> None:
    for statement in re.split(r";\s*$", SCHEMA.read_text(), flags=re.MULTILINE):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("drop table pilot_senders")
