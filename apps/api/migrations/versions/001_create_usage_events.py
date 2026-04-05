"""Create usage_events table

Revision ID: 001_create_usage_events
Revises:
Create Date: 2026-04-05

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001_create_usage_events"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "usage_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column("request_id", sa.String(255), nullable=True),
        sa.Column("execution_id", sa.String(255), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("action_name", sa.String(255), nullable=False),
        sa.Column("model_name", sa.String(255), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("token_cost_estimate", sa.Numeric(12, 6), nullable=True),
        sa.Column("tool_name", sa.String(255), nullable=True),
        sa.Column("tool_cost_estimate", sa.Numeric(12, 6), nullable=True),
        sa.Column(
            "total_cost_estimate",
            sa.Numeric(12, 6),
            nullable=False,
            server_default="0",
        ),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.UniqueConstraint("request_id"),
    )

    # Indexes — see billing/models.py for rationale
    op.create_index(
        "ix_usage_events_user_id_created_at",
        "usage_events",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_usage_events_action_type_created_at",
        "usage_events",
        ["action_type", "created_at"],
    )
    op.create_index(
        "ix_usage_events_execution_id",
        "usage_events",
        ["execution_id"],
    )
    op.create_index(
        "ix_usage_events_created_at",
        "usage_events",
        ["created_at"],
    )
    op.create_index(
        "ix_usage_events_status",
        "usage_events",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_usage_events_status", table_name="usage_events")
    op.drop_index("ix_usage_events_created_at", table_name="usage_events")
    op.drop_index("ix_usage_events_execution_id", table_name="usage_events")
    op.drop_index("ix_usage_events_action_type_created_at", table_name="usage_events")
    op.drop_index("ix_usage_events_user_id_created_at", table_name="usage_events")
    op.drop_table("usage_events")
