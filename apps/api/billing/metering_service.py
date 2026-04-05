"""
Core metering pipeline for ARI.

All billable actions (LLM calls, tool calls) flow through this module.

CRITICAL SAFETY RULE: metering failures must NEVER propagate to callers.
Every public function wraps all DB operations in try/except and logs on
failure. The caller's work always continues regardless of metering state.

Usage — explicit lifecycle:

    event_id = await metering.start_event(
        user_id=user_id,
        action_type="chat",
        action_name="gpt-5.2-chat",
        session_id=session_id,
    )
    try:
        result = await do_llm_call()
        await metering.complete_event(
            event_id,
            input_tokens=result.usage.prompt_tokens,
            output_tokens=result.usage.completion_tokens,
            model_name="gpt-5.2-chat",
            duration_ms=elapsed_ms,
        )
    except Exception as exc:
        await metering.fail_event(event_id, error=str(exc), duration_ms=elapsed_ms)
        raise  # always re-raise — metering never swallows errors

Usage — context manager (handles start/complete/fail automatically):

    async with metering.track(user_id, "chat", "gpt-5.2-chat", session_id=sid) as t:
        result = await do_llm_call()
        t.record_tokens(result.usage.prompt_tokens, result.usage.completion_tokens, "gpt-5.2-chat")
    # complete_event called automatically on clean exit
    # fail_event called automatically if an exception is raised (then re-raised)
"""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncGenerator

logger = logging.getLogger("ari.billing.metering")


# ── EventTracker dataclass (used by context manager) ──────────────────────────


@dataclass
class EventTracker:
    """
    Mutable accumulator passed to callers inside the `track()` context manager.

    Call record_tokens() after an LLM call or record_tool() after a tool call
    to attach usage data before the context manager calls complete_event().
    """

    event_id: uuid.UUID | None

    # Fields populated by the caller before context exit
    _model_name: str | None = field(default=None, init=False)
    _input_tokens: int | None = field(default=None, init=False)
    _output_tokens: int | None = field(default=None, init=False)
    _tool_name: str | None = field(default=None, init=False)
    _extra_metadata: dict[str, Any] = field(default_factory=dict, init=False)
    _error: str | None = field(default=None, init=False)

    def record_tokens(
        self,
        input_tokens: int,
        output_tokens: int,
        model_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record token counts from an LLM response."""
        self._input_tokens = input_tokens
        self._output_tokens = output_tokens
        self._model_name = model_name
        if metadata:
            self._extra_metadata.update(metadata)

    def record_tool(self, tool_name: str, metadata: dict[str, Any] | None = None) -> None:
        """Record the tool name from a tool invocation."""
        self._tool_name = tool_name
        if metadata:
            self._extra_metadata.update(metadata)

    def add_metadata(self, **kwargs: Any) -> None:
        """Add arbitrary key/value pairs to the event's metadata_json."""
        self._extra_metadata.update(kwargs)


# ── Public API ─────────────────────────────────────────────────────────────────


async def start_event(
    user_id: str,
    action_type: str,
    action_name: str,
    *,
    session_id: str | None = None,
    execution_id: str | None = None,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> uuid.UUID | None:
    """
    Persist a usage event with status='started' and return its UUID.

    Returns None if:
      - METERING_DATABASE_URL is not configured
      - The DB write fails for any reason

    Callers must treat None as a valid return — pass it to complete_event /
    fail_event which are both no-ops when event_id is None.
    """
    event_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    try:
        from billing.database import get_db_session
        from billing.models import UsageEvent

        async with get_db_session() as session:
            event = UsageEvent(
                id=event_id,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id or str(uuid.uuid4()),
                execution_id=execution_id,
                action_type=action_type,
                action_name=action_name,
                status="started",
                metadata_json=metadata or {},
                created_at=now,
                updated_at=now,
            )
            session.add(event)
        return event_id

    except Exception as exc:
        logger.error(
            "metering.start_event failed — user=%s action=%s/%s: %s",
            user_id, action_type, action_name, exc,
            exc_info=True,
        )
        return None


async def complete_event(
    event_id: uuid.UUID | None,
    *,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    model_name: str | None = None,
    tool_name: str | None = None,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Mark a usage event as 'completed' and compute cost estimates.

    Safe to call with event_id=None (start_event failed) — no-op.

    Idempotency: if the event is already 'completed', logs a warning and
    returns without overwriting. This protects against double-billing on
    retries that share an execution_id.
    """
    if event_id is None:
        return

    try:
        from billing.database import get_db_session
        from billing.model_pricing import calculate_token_cost
        from billing.models import UsageEvent
        from billing.tool_pricing import get_tool_cost
        from sqlalchemy import select

        async with get_db_session() as session:
            result = await session.execute(
                select(UsageEvent).where(UsageEvent.id == event_id)
            )
            event = result.scalar_one_or_none()

            if event is None:
                logger.warning("metering.complete_event: event %s not found", event_id)
                return

            # Idempotency guard — never overwrite a completed event
            if event.status == "completed":
                logger.info(
                    "metering.complete_event: event %s already completed — "
                    "skipping (idempotency guard)",
                    event_id,
                )
                return

            # Compute costs
            token_cost = Decimal("0")
            if model_name and input_tokens is not None and output_tokens is not None:
                token_cost = calculate_token_cost(model_name, input_tokens, output_tokens)

            tool_cost = Decimal("0")
            if tool_name:
                tool_cost = get_tool_cost(tool_name)

            total_cost = token_cost + tool_cost

            # Persist
            event.status = "completed"
            event.model_name = model_name
            event.input_tokens = input_tokens
            event.output_tokens = output_tokens
            event.token_cost_estimate = float(token_cost) if token_cost else None
            event.tool_name = tool_name
            event.tool_cost_estimate = float(tool_cost) if tool_cost else None
            event.total_cost_estimate = float(total_cost)
            event.duration_ms = duration_ms
            event.updated_at = datetime.now(timezone.utc)

            if metadata:
                existing = event.metadata_json or {}
                event.metadata_json = {**existing, **metadata}

    except Exception as exc:
        logger.error(
            "metering.complete_event failed — event_id=%s: %s",
            event_id, exc,
            exc_info=True,
        )


async def fail_event(
    event_id: uuid.UUID | None,
    *,
    error: str | None = None,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """
    Mark a usage event as 'failed'.

    Safe to call with event_id=None — no-op.
    Always re-raise the original exception after calling this — metering
    must never swallow errors from the primary call path.
    """
    if event_id is None:
        return

    try:
        from billing.database import get_db_session
        from billing.models import UsageEvent
        from sqlalchemy import select

        async with get_db_session() as session:
            result = await session.execute(
                select(UsageEvent).where(UsageEvent.id == event_id)
            )
            event = result.scalar_one_or_none()

            if event is None:
                return

            event.status = "failed"
            event.duration_ms = duration_ms
            event.updated_at = datetime.now(timezone.utc)

            fail_meta: dict[str, Any] = {}
            if error:
                fail_meta["error"] = error
            if metadata:
                fail_meta.update(metadata)
            if fail_meta:
                existing = event.metadata_json or {}
                event.metadata_json = {**existing, **fail_meta}

    except Exception as exc:
        logger.error(
            "metering.fail_event failed — event_id=%s: %s",
            event_id, exc,
            exc_info=True,
        )


@asynccontextmanager
async def track(
    user_id: str,
    action_type: str,
    action_name: str,
    *,
    session_id: str | None = None,
    execution_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AsyncGenerator[EventTracker, None]:
    """
    Context manager that wraps a billable operation with automatic lifecycle
    management (start → complete on success, start → fail on exception).

    The yielded EventTracker lets callers attach token counts or tool names
    before the context exits.

    On exception: calls fail_event then re-raises — metering never swallows
    errors from the primary call path.

    Example:
        async with metering.track(user_id, "chat", "gpt-5.2-chat", session_id=sid) as t:
            result = await do_llm_call()
            t.record_tokens(result.usage.prompt_tokens, result.usage.completion_tokens, "gpt-5.2-chat")
    """
    t0 = time.monotonic()
    event_id = await start_event(
        user_id=user_id,
        action_type=action_type,
        action_name=action_name,
        session_id=session_id,
        execution_id=execution_id,
        metadata=metadata,
    )
    tracker = EventTracker(event_id=event_id)

    try:
        yield tracker
    except Exception as exc:
        duration_ms = int((time.monotonic() - t0) * 1000)
        try:
            await fail_event(
                event_id,
                error=str(exc),
                duration_ms=duration_ms,
                metadata=tracker._extra_metadata or None,
            )
        except Exception:
            # fail_event itself errored — log and continue so the original
            # exception is always what propagates to the caller.
            logger.error(
                "metering.track: fail_event raised during cleanup — original error will propagate",
                exc_info=True,
            )
        raise  # always re-raise the original exception
    else:
        duration_ms = int((time.monotonic() - t0) * 1000)
        await complete_event(
            event_id,
            input_tokens=tracker._input_tokens,
            output_tokens=tracker._output_tokens,
            model_name=tracker._model_name,
            tool_name=tracker._tool_name,
            duration_ms=duration_ms,
            metadata=tracker._extra_metadata or None,
        )
