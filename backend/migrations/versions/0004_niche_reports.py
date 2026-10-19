"""Weekly Niche Reports per niche: niche_reports and the generate_niche_report job kind (ADR 0025)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-19
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = Path(__file__).with_suffix(".sql")


def upgrade() -> None:
    for statement in re.split(r";\s*$", SCHEMA.read_text(), flags=re.MULTILINE):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("delete from jobs where kind = 'generate_niche_report'")
    op.execute("alter table jobs drop constraint ck_jobs_kind")
    op.execute(
        "alter table jobs add constraint ck_jobs_kind check (kind in ('analyze_asset',"
        "'generate_brand','generate_plan','generate_post','revise_post','redo_slides',"
        "'publish_post','import_instagram'))"
    )
    op.execute("drop table if exists niche_reports")
