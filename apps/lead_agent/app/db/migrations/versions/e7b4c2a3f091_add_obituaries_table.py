"""add obituaries table

Revision ID: e7b4c2a3f091
Revises: 018fba6ca502
Create Date: 2026-03-31 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "e7b4c2a3f091"
down_revision: Union[str, None] = "018fba6ca502"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "obituaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=2), nullable=True),
        sa.Column("published_date", sa.Date(), nullable=True),
        sa.Column("source_site", sa.Text(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "full_name", "city", "state", "source_site", "source_url",
            name="uq_obituary",
        ),
    )
    op.create_index("ix_obituaries_state", "obituaries", ["state"])
    op.create_index("ix_obituaries_published_date", "obituaries", ["published_date"])
    op.create_index("ix_obituaries_scraped_at", "obituaries", ["scraped_at"])

    op.create_table(
        "obituary_backfill_state",
        sa.Column("date_filter", sa.Integer(), nullable=False),
        sa.Column("last_completed_page", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("date_filter"),
    )


def downgrade() -> None:
    op.drop_table("obituary_backfill_state")
    op.drop_index("ix_obituaries_scraped_at", table_name="obituaries")
    op.drop_index("ix_obituaries_published_date", table_name="obituaries")
    op.drop_index("ix_obituaries_state", table_name="obituaries")
    op.drop_table("obituaries")
