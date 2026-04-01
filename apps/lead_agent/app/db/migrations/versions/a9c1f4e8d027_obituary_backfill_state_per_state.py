"""update obituary_backfill_state to track progress per state

The search API caps results at 200 pages (10k records) per query.
By adding a state dimension we can iterate state-by-state and capture
all 234k+ obituaries across 54 US states / territories.

Revision ID: a9c1f4e8d027
Revises: f2d9e5b3c108
Create Date: 2026-04-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a9c1f4e8d027"
down_revision: Union[str, None] = "f2d9e5b3c108"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Delete old rows (prior format had only date_filter as PK, no state)
    op.execute("DELETE FROM obituary_backfill_state")

    op.add_column(
        "obituary_backfill_state",
        sa.Column("state", sa.String(length=2), nullable=False, server_default=""),
    )
    op.drop_constraint("obituary_backfill_state_pkey", "obituary_backfill_state", type_="primary")
    op.create_primary_key("obituary_backfill_state_pkey", "obituary_backfill_state", ["date_filter", "state"])


def downgrade() -> None:
    op.execute("DELETE FROM obituary_backfill_state")
    op.drop_constraint("obituary_backfill_state_pkey", "obituary_backfill_state", type_="primary")
    op.drop_column("obituary_backfill_state", "state")
    op.create_primary_key("obituary_backfill_state_pkey", "obituary_backfill_state", ["date_filter"])
