"""Clear stored Instagram access tokens: the import job deletes them after use (#102)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = Path(__file__).with_suffix(".sql")


def upgrade() -> None:
    for statement in re.split(r";\s*$", SCHEMA.read_text(), flags=re.MULTILINE):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    # The cleared tokens can't be restored, and nothing needs them: the import read each one once.
    pass
