"""
SQLAlchemy ORM models for the metering database (ari_metering).

The usage_events table is the central fact table for all billable actions.
Its primary key (id) is designed to be referenceable from future
wallet_transactions.reference_event_id (Phase 2).
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class UsageEvent(Base):
    """
    Records one billable action: LLM call, tool call, or workflow step.

    Lifecycle: status transitions from 'started' → 'completed' or 'failed'.
    Use metering_service.start_event / complete_event / fail_event — never
    write to this table directly from application code.
    """

    __tablename__ = "usage_events"

    # Primary key — server-generated UUID so the record can be referenced
    # by wallet_transactions in Phase 2 before the row is fully populated.
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Who triggered this action (maps to Cosmos DB userId — not a FK).
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)

    # Optional grouping fields for tracing
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    execution_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # What happened
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # Enum-like: "chat", "tool", "skill", "workflow", "agent"
    action_name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Specific identifier, e.g. "gpt-5.2-chat", "mcp_leads_context", "generate_document"

    # LLM-specific (null for pure tool calls)
    model_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    token_cost_estimate: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Tool-specific (null for pure LLM calls)
    tool_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tool_cost_estimate: Mapped[float | None] = mapped_column(Numeric(12, 6), nullable=True)

    # Rolled-up cost = token_cost_estimate + tool_cost_estimate
    total_cost_estimate: Mapped[float] = mapped_column(
        Numeric(12, 6), nullable=False, server_default="0"
    )

    # Status + timing
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Flexible context bag.
    # Stores: session context, finish_reason, error messages, etc.
    # Designed to carry future Phase 2 fields: plan_id, tier, affiliate_id.
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        # User history — most common reporting query
        Index("ix_usage_events_user_id_created_at", "user_id", "created_at"),
        # Reporting breakdown by action type
        Index("ix_usage_events_action_type_created_at", "action_type", "created_at"),
        # Idempotency lookups (retry deduplication via execution_id)
        Index("ix_usage_events_execution_id", "execution_id"),
        # Time-range scans for admin reporting
        Index("ix_usage_events_created_at", "created_at"),
        # Filtering in-flight or failed events
        Index("ix_usage_events_status", "status"),
    )
