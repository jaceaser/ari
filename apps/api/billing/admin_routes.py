"""
Admin-only API endpoints for usage reporting.

All routes are protected by @require_admin which checks the X-Admin-Key
request header against the ADMIN_API_KEY environment variable.

TODO: Replace @require_admin with proper role-based auth when a user-role
system is built. The decorator is designed for easy replacement — just
swap the implementation without changing any route code.

Endpoints:
    GET /admin/usage/summary        — overall stats
    GET /admin/usage/by-user        — spend per user
    GET /admin/usage/by-action-type — spend by action type
    GET /admin/usage/by-action-name — spend by specific action
    GET /admin/usage/by-model       — spend by LLM model
    GET /admin/usage/by-tool        — spend by tool
    GET /admin/usage/timeseries     — time-series aggregation
"""
import logging
import os
from datetime import date, timedelta
from functools import wraps

from quart import Blueprint, jsonify, request

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")

logger = logging.getLogger("ari.billing.admin")


# ── Auth ───────────────────────────────────────────────────────────────────────


def require_admin(f):
    """
    Decorator that enforces admin-only access via a shared secret header.

    Checks X-Admin-Key header (or Bearer token in Authorization) against
    the ADMIN_API_KEY environment variable.

    If ADMIN_API_KEY is not set, all admin endpoints return 503 — this
    prevents accidental open access in environments that haven't configured
    the key yet.

    TODO: Replace with proper role-based auth when user roles are implemented.
    """
    @wraps(f)
    async def decorated(*args, **kwargs):
        admin_key = os.getenv("ADMIN_API_KEY", "").strip()
        if not admin_key:
            return jsonify({"error": "Admin access not configured on this server"}), 503

        provided = (
            request.headers.get("X-Admin-Key")
            or request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        )
        if not provided or provided != admin_key:
            return jsonify({"error": "Unauthorized"}), 401

        return await f(*args, **kwargs)

    return decorated


# ── Helpers ────────────────────────────────────────────────────────────────────


def _parse_date_range() -> tuple[date, date] | tuple[None, None]:
    """
    Parse start_date / end_date query params (YYYY-MM-DD).
    Defaults: end_date = today, start_date = 30 days prior.
    Returns (None, None) on parse error.
    """
    try:
        end_date = date.fromisoformat(
            request.args.get("end_date") or date.today().isoformat()
        )
    except ValueError:
        return None, None

    try:
        start_date = date.fromisoformat(
            request.args.get("start_date")
            or (end_date - timedelta(days=30)).isoformat()
        )
    except ValueError:
        return None, None

    return start_date, end_date


def _bad_date():
    return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400


def _bad_granularity():
    return jsonify({"error": "granularity must be daily, weekly, or monthly"}), 400


# ── Endpoints ─────────────────────────────────────────────────────────────────


@admin_bp.get("/usage/summary")
@require_admin
async def usage_summary():
    """Overall usage and cost summary for a date range."""
    start_date, end_date = _parse_date_range()
    if start_date is None:
        return _bad_date()

    from billing import reporting_service
    data = await reporting_service.get_usage_summary(start_date, end_date)
    return jsonify(data)


@admin_bp.get("/usage/by-user")
@require_admin
async def usage_by_user():
    """Cost breakdown per user, descending."""
    start_date, end_date = _parse_date_range()
    if start_date is None:
        return _bad_date()

    try:
        limit = max(1, min(int(request.args.get("limit", 100)), 1000))
    except ValueError:
        limit = 100

    from billing import reporting_service
    data = await reporting_service.get_spend_by_user(start_date, end_date, limit=limit)
    return jsonify({
        "users": data,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })


@admin_bp.get("/usage/by-action-type")
@require_admin
async def usage_by_action_type():
    """Cost breakdown by action type (chat, tool, etc.)."""
    start_date, end_date = _parse_date_range()
    if start_date is None:
        return _bad_date()

    from billing import reporting_service
    data = await reporting_service.get_spend_by_action_type(start_date, end_date)
    return jsonify({
        "action_types": data,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })


@admin_bp.get("/usage/by-action-name")
@require_admin
async def usage_by_action_name():
    """Cost breakdown by specific action name."""
    start_date, end_date = _parse_date_range()
    if start_date is None:
        return _bad_date()

    from billing import reporting_service
    data = await reporting_service.get_spend_by_action_name(start_date, end_date)
    return jsonify({
        "actions": data,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })


@admin_bp.get("/usage/by-model")
@require_admin
async def usage_by_model():
    """Cost and token breakdown by LLM model."""
    start_date, end_date = _parse_date_range()
    if start_date is None:
        return _bad_date()

    from billing import reporting_service
    data = await reporting_service.get_spend_by_model(start_date, end_date)
    return jsonify({
        "models": data,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })


@admin_bp.get("/usage/by-tool")
@require_admin
async def usage_by_tool():
    """Invocation count and cost breakdown by tool name."""
    start_date, end_date = _parse_date_range()
    if start_date is None:
        return _bad_date()

    from billing import reporting_service
    data = await reporting_service.get_spend_by_tool(start_date, end_date)
    return jsonify({
        "tools": data,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })


@admin_bp.get("/usage/timeseries")
@require_admin
async def usage_timeseries():
    """Time-series aggregation of events and cost."""
    start_date, end_date = _parse_date_range()
    if start_date is None:
        return _bad_date()

    granularity = request.args.get("granularity", "daily")
    if granularity not in ("daily", "weekly", "monthly"):
        return _bad_granularity()

    from billing import reporting_service
    data = await reporting_service.get_usage_timeseries(start_date, end_date, granularity=granularity)
    return jsonify({
        "timeseries": data,
        "granularity": granularity,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    })
