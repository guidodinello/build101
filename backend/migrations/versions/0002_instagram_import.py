"""Instagram import: tokens on social_accounts, external_id on brand_assets (ADR 0028)

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
    op.execute("delete from jobs where kind = 'import_instagram'")
    op.execute("alter table jobs drop constraint ck_jobs_kind")
    op.execute(
        "alter table jobs add constraint ck_jobs_kind check (kind in ('analyze_asset',"
        "'generate_brand','generate_plan','generate_post','revise_post','redo_slides',"
        "'publish_post'))"
    )
    op.execute("drop index if exists uq_brand_assets_business_id_source_external_id")
    op.execute("alter table brand_assets drop column if exists external_id")
    op.execute("alter table social_accounts disable row level security")
    op.execute(
        "alter table social_accounts "
        "drop constraint if exists uq_social_accounts_business_id_platform_provider"
    )
    op.execute(
        "alter table social_accounts add constraint uq_social_accounts_business_id_platform "
        "unique (business_id, platform)"
    )
    op.execute("alter table social_accounts drop column if exists token_expires_at")
    op.execute("alter table social_accounts drop column if exists access_token")
