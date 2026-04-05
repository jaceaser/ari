"""
Admin reporting queries for metering data.

All functions query usage_events and return plain dicts — no ORM objects
cross the boundary. Each function wraps its DB call in try/except and
returns an empty result on failure so reporting endpoints degrade
gracefully when the metering DB is unavailable.
"""
import logging
from datetime import date, datetime, timezone
from typing import Any

logger = logging.getLogger("ari.billing.reporting")


# ── Date helpers ───────────────────────────────────────────────────────────────


def _start_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _end_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=timezone.utc)


# ── Query functions ────────────────────────────────────────────────────────────


async def get_usage_summary(start_date: date, end_date: date) -> dict[str, Any]:
    """Overall stats for a date range: event count, cost, tokens, unique users."""
    try:
        from billing.database import get_db_session
        from billing.models import UsageEvent
        from sqlalchemy import func, select

        async with get_db_session() as session:
            row = (await session.execute(
                select(
                    func.count(UsageEvent.id).label("total_events"),
                    func.coalesce(func.sum(UsageEvent.total_cost_estimate), 0).label("total_cost"),
                    func.coalesce(func.sum(UsageEvent.input_tokens), 0).label("total_input_tokens"),
                    func.coalesce(func.sum(UsageEvent.output_tokens), 0).label("total_output_tokens"),
                    func.count(func.distinct(UsageEvent.user_id)).label("unique_users"),
                ).where(
                    UsageEvent.created_at >= _start_dt(start_date),
                    UsageEvent.created_at <= _end_dt(end_date),
                    UsageEvent.status == "completed",
                )
            )).one()

        return {
            "total_events": row.total_events,
            "total_cost_usd": float(row.total_cost),
            "total_input_tokens": row.total_input_tokens,
            "total_output_tokens": row.total_output_tokens,
            "unique_users": row.unique_users,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    except Exception as exc:
        logger.error("get_usage_summary failed: %s", exc, exc_info=True)
        return {
            "total_events": 0, "total_cost_usd": 0.0,
            "total_input_tokens": 0, "total_output_tokens": 0, "unique_users": 0,
            "start_date": start_date.isoformat(), "end_date": end_date.isoformat(),
        }


async def get_spend_by_user(
    start_date: date, end_date: date, limit: int = 100
) -> list[dict[str, Any]]:
    """Total cost per user, descending. Used for both by-user and top-users."""
    try:
        from billing.database import get_db_session
        from billing.models import UsageEvent
        from sqlalchemy import func, select

        async with get_db_session() as session:
            rows = (await session.execute(
                select(
                    UsageEvent.user_id,
                    func.count(UsageEvent.id).label("event_count"),
                    func.coalesce(func.sum(UsageEvent.total_cost_estimate), 0).label("total_cost"),
                    func.coalesce(func.sum(UsageEvent.input_tokens), 0).label("total_input_tokens"),
                    func.coalesce(func.sum(UsageEvent.output_tokens), 0).label("total_output_tokens"),
                ).where(
                    UsageEvent.created_at >= _start_dt(start_date),
                    UsageEvent.created_at <= _end_dt(end_date),
                    UsageEvent.status == "completed",
                ).group_by(UsageEvent.user_id)
                .order_by(func.sum(UsageEvent.total_cost_estimate).desc())
                .limit(limit)
            )).all()

        return [
            {
                "user_id": r.user_id,
                "event_count": r.event_count,
                "total_cost_usd": float(r.total_cost),
                "total_input_tokens": r.total_input_tokens,
                "total_output_tokens": r.total_output_tokens,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error("get_spend_by_user failed: %s", exc, exc_info=True)
        return []


async def get_spend_by_action_type(
    start_date: date, end_date: date
) -> list[dict[str, Any]]:
    """Cost breakdown by action_type (chat, tool, etc.)."""
    try:
        from billing.database import get_db_session
        from billing.models import UsageEvent
        from sqlalchemy import func, select

        async with get_db_session() as session:
            rows = (await session.execute(
                select(
                    UsageEvent.action_type,
                    func.count(UsageEvent.id).label("event_count"),
                    func.coalesce(func.sum(UsageEvent.total_cost_estimate), 0).label("total_cost"),
                ).where(
                    UsageEvent.created_at >= _start_dt(start_date),
                    UsageEvent.created_at <= _end_dt(end_date),
                    UsageEvent.status == "completed",
                ).group_by(UsageEvent.action_type)
                .order_by(func.sum(UsageEvent.total_cost_estimate).desc())
            )).all()

        return [
            {
                "action_type": r.action_type,
                "event_count": r.event_count,
                "total_cost_usd": float(r.total_cost),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error("get_spend_by_action_type failed: %s", exc, exc_info=True)
        return []


async def get_spend_by_action_name(
    start_date: date, end_date: date
) -> list[dict[str, Any]]:
    """Cost breakdown by specific action_name (e.g. 'gpt-5.2-chat', 'mcp_leads_context')."""
    try:
        from billing.database import get_db_session
        from billing.models import UsageEvent
        from sqlalchemy import func, select

        async with get_db_session() as session:
            rows = (await session.execute(
                select(
                    UsageEvent.action_name,
                    UsageEvent.action_type,
                    func.count(UsageEvent.id).label("event_count"),
                    func.coalesce(func.sum(UsageEvent.total_cost_estimate), 0).label("total_cost"),
                ).where(
                    UsageEvent.created_at >= _start_dt(start_date),
                    UsageEvent.created_at <= _end_dt(end_date),
                    UsageEvent.status == "completed",
                ).group_by(UsageEvent.action_name, UsageEvent.action_type)
                .order_by(func.sum(UsageEvent.total_cost_estimate).desc())
            )).all()

        return [
            {
                "action_name": r.action_name,
                "action_type": r.action_type,
                "event_count": r.event_count,
                "total_cost_usd": float(r.total_cost),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error("get_spend_by_action_name failed: %s", exc, exc_info=True)
        return []


async def get_spend_by_model(
    start_date: date, end_date: date
) -> list[dict[str, Any]]:
    """Cost and token breakdown by LLM model name."""
    try:
        from billing.database import get_db_session
        from billing.models import UsageEvent
        from sqlalchemy import func, select

        async with get_db_session() as session:
            rows = (await session.execute(
                select(
                    UsageEvent.model_name,
                    func.count(UsageEvent.id).label("event_count"),
                    func.coalesce(func.sum(UsageEvent.input_tokens), 0).label("total_input_tokens"),
                    func.coalesce(func.sum(UsageEvent.output_tokens), 0).label("total_output_tokens"),
                    func.coalesce(func.sum(UsageEvent.token_cost_estimate), 0).label("total_cost"),
                ).where(
                    UsageEvent.created_at >= _start_dt(start_date),
                    UsageEvent.created_at <= _end_dt(end_date),
                    UsageEvent.status == "completed",
                    UsageEvent.model_name.isnot(None),
                ).group_by(UsageEvent.model_name)
                .order_by(func.sum(UsageEvent.token_cost_estimate).desc())
            )).all()

        return [
            {
                "model_name": r.model_name,
                "event_count": r.event_count,
                "total_input_tokens": r.total_input_tokens,
                "total_output_tokens": r.total_output_tokens,
                "total_cost_usd": float(r.total_cost),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error("get_spend_by_model failed: %s", exc, exc_info=True)
        return []


async def get_spend_by_tool(
    start_date: date, end_date: date
) -> list[dict[str, Any]]:
    """Invocation count and cost breakdown by tool name."""
    try:
        from billing.database import get_db_session
        from billing.models import UsageEvent
        from sqlalchemy import func, select

        async with get_db_session() as session:
            rows = (await session.execute(
                select(
                    UsageEvent.tool_name,
                    func.count(UsageEvent.id).label("invocation_count"),
                    func.coalesce(func.sum(UsageEvent.tool_cost_estimate), 0).label("total_cost"),
                ).where(
                    UsageEvent.created_at >= _start_dt(start_date),
                    UsageEvent.created_at <= _end_dt(end_date),
                    UsageEvent.status == "completed",
                    UsageEvent.tool_name.isnot(None),
                ).group_by(UsageEvent.tool_name)
                .order_by(func.sum(UsageEvent.tool_cost_estimate).desc())
            )).all()

        return [
            {
                "tool_name": r.tool_name,
                "invocation_count": r.invocation_count,
                "total_cost_usd": float(r.total_cost),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error("get_spend_by_tool failed: %s", exc, exc_info=True)
        return []


async def get_top_users(
    start_date: date, end_date: date, limit: int = 10
) -> list[dict[str, Any]]:
    """Top N users by spend."""
    return await get_spend_by_user(start_date, end_date, limit=limit)


async def get_top_actions(
    start_date: date, end_date: date, limit: int = 10
) -> list[dict[str, Any]]:
    """Top N action names by spend."""
    return (await get_spend_by_action_name(start_date, end_date))[:limit]


async def get_usage_timeseries(
    start_date: date,
    end_date: date,
    granularity: str = "daily",
) -> list[dict[str, Any]]:
    """
    Event count and cost aggregated by time period.
    granularity: "daily" | "weekly" | "monthly"
    """
    trunc_map = {"daily": "day", "weekly": "week", "monthly": "month"}
    trunc = trunc_map.get(granularity, "day")

    try:
        from billing.database import get_db_session
        from billing.models import UsageEvent
        from sqlalchemy import func, select

        async with get_db_session() as session:
            period_expr = func.date_trunc(trunc, UsageEvent.created_at)
            rows = (await session.execute(
                select(
                    period_expr.label("period"),
                    func.count(UsageEvent.id).label("event_count"),
                    func.coalesce(func.sum(UsageEvent.total_cost_estimate), 0).label("total_cost"),
                    func.count(func.distinct(UsageEvent.user_id)).label("unique_users"),
                ).where(
                    UsageEvent.created_at >= _start_dt(start_date),
                    UsageEvent.created_at <= _end_dt(end_date),
                    UsageEvent.status == "completed",
                ).group_by(period_expr)
                .order_by(period_expr)
            )).all()

        return [
            {
                "period": r.period.isoformat() if r.period else None,
                "event_count": r.event_count,
                "total_cost_usd": float(r.total_cost),
                "unique_users": r.unique_users,
            }
            for r in rows
        ]
    except Exception as exc:
        logger.error("get_usage_timeseries failed: %s", exc, exc_info=True)
        return []
