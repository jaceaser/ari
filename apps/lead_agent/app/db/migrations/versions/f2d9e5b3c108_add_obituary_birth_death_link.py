"""add date_of_birth, date_of_death, obituary_link to obituaries

Revision ID: f2d9e5b3c108
Revises: e7b4c2a3f091
Create Date: 2026-03-31 01:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f2d9e5b3c108"
down_revision: Union[str, None] = "e7b4c2a3f091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("obituaries", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("obituaries", sa.Column("date_of_death", sa.Date(), nullable=True))
    op.add_column("obituaries", sa.Column("obituary_link", sa.Text(), nullable=True))

    # Partial unique index: one row per individual obituary page link.
    # Partial (WHERE NOT NULL) because NULL is not equal to NULL in PG unique indexes
    # and old rows scraped before this change may have no link.
    op.create_index(
        "uq_obituary_link",
        "obituaries",
        ["obituary_link"],
        unique=True,
        postgresql_where=sa.text("obituary_link IS NOT NULL"),
    )

    op.create_index("ix_obituaries_date_of_death", "obituaries", ["date_of_death"])


def downgrade() -> None:
    op.drop_index("ix_obituaries_date_of_death", table_name="obituaries")
    op.drop_index("uq_obituary_link", table_name="obituaries")
    op.drop_column("obituaries", "obituary_link")
    op.drop_column("obituaries", "date_of_death")
    op.drop_column("obituaries", "date_of_birth")
