"""The brand summary and WhatsApp's 24 h window (#204)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-28
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = Path(__file__).with_suffix(".sql")


def upgrade() -> None:
    for statement in re.split(r";\s*$", SCHEMA.read_text(), flags=re.MULTILINE):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("alter table brand_brains drop column if exists summary_sent_at")
    op.execute("alter table businesses drop column if exists last_inbound_at")
