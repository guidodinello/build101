"""The whole schema from docs/architecture/data-model.md (ADR 0003, ADR 0016)

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = Path(__file__).with_suffix(".sql")

TABLES = [
    "businesses",
    "magic_links",
    "products",
    "brand_assets",
    "asset_products",
    "offers",
    "offer_products",
    "brand_brains",
    "social_accounts",
    "content_plans",
    "posts",
    "post_revisions",
    "post_variations",
    "post_slides",
    "messages",
    "jobs",
    "agent_runs",
]


def upgrade() -> None:
    # asyncpg runs one statement per call, so the file is split on the `;` that ends a line.
    for statement in re.split(r";\s*$", SCHEMA.read_text(), flags=re.MULTILINE):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.execute(f"drop table if exists {table} cascade")
