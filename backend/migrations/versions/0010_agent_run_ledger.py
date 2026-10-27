"""The agent run ledger: usage and cost columns on agent_runs, and its cost views (#205)

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-27
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
VIEWS = (
    "agent_run_cache_hits",
    "agent_run_costs_by_agent",
    "agent_run_costs_monthly",
    "agent_run_costs_daily",
)
COLUMNS = (
    "cost_usd",
    "video_seconds",
    "image_count",
    "image_size",
    "thought_tokens",
    "service_tier",
    "post_id",
)


def upgrade() -> None:
    for statement in re.split(r";\s*$", SCHEMA.read_text(), flags=re.MULTILINE):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for view in VIEWS:
        op.execute(f"drop view if exists {view}")
    op.execute("drop index if exists ix_agent_runs_created_at")
    for column in COLUMNS:
        op.execute(f"alter table agent_runs drop column if exists {column}")
