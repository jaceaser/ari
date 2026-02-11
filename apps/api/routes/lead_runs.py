"""Lead run endpoints: GET /lead-runs, GET /lead-runs/<id>."""

import logging

from quart import jsonify, request

from . import lead_runs_bp

logger = logging.getLogger("api.lead_runs")


@lead_runs_bp.get("/lead-runs")
async def list_lead_runs():
    """List lead runs for the authenticated user."""
    from cosmos import SessionsCosmosClient

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503

    runs = await cosmos.get_lead_runs(user_id)
    return jsonify([
        {
            "id": r["id"],
            "summary": r.get("summary", ""),
            "location": r.get("location", ""),
            "strategy": r.get("strategy", ""),
            "result_count": r.get("resultCount", 0),
            "created_at": r.get("createdAt", ""),
        }
        for r in runs
    ])


@lead_runs_bp.get("/lead-runs/<lead_run_id>")
async def get_lead_run(lead_run_id: str):
    """Get lead run detail including file_url."""
    from cosmos import SessionsCosmosClient

    user_id = getattr(request, "user_id", None)
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    cosmos = SessionsCosmosClient.get_instance()
    if not cosmos:
        return jsonify({"error": "Persistence not configured"}), 503

    run = await cosmos.get_lead_run(user_id, lead_run_id)
    if not run:
        return jsonify({"error": "Not found"}), 404

    return jsonify({
        "id": run["id"],
        "summary": run.get("summary", ""),
        "location": run.get("location", ""),
        "strategy": run.get("strategy", ""),
        "result_count": run.get("resultCount", 0),
        "file_url": run.get("fileUrl", ""),
        "filters": run.get("filters"),
        "created_at": run.get("createdAt", ""),
    })
