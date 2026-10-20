"""Close the public schema to Supabase's Data API: RLS on every table, no anon grants (audit SEC-1)

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-20
"""

import re
from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = Path(__file__).with_suffix(".sql")

# Every table that had RLS off before this revision: social_accounts (0002) and inbound_deliveries
# (0006) have had it on since they were created
TABLES_WITHOUT_RLS = (
    "alembic_version",
    "businesses",
    "magic_links",
    "products",
    "brand_assets",
    "asset_products",
    "offers",
    "offer_products",
    "brand_brains",
    "content_plans",
    "posts",
    "post_revisions",
    "post_variations",
    "post_slides",
    "messages",
    "jobs",
    "agent_runs",
    "conversation_steps",
    "owner_notes",
    "niche_reports",
)


def upgrade() -> None:
    for statement in re.split(r";\s*$", SCHEMA.read_text(), flags=re.MULTILINE):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    # Revoked grants and default privileges stay revoked: reopening the Data API is never wanted.
    for table in TABLES_WITHOUT_RLS:
        op.execute(f"alter table if exists public.{table} disable row level security")
