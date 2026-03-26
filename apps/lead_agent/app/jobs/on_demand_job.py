"""
On-demand job — triggered by REST or Service Bus message.

JOB_PAYLOAD env var (JSON):
  {"geography_slug": "harris-county-tx", "lead_type_slug": "pre_foreclosure",
   "user_id": "user_abc", "force_refresh": false}

Cache-first: if a non-expired lead list already exists for this geo+lead_type
in the current month, returns the cached list without re-scraping.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from app.config import get_settings
from app.db.session import get_db
from app.models.db import LeadListDefinition
from app.models.domain import RunResult, RunStatus, TriggerType
from app.orchestrators.run_orchestrator import RunOrchestrator
from app.repositories.geography_repo import GeographyRepo

logger = logging.getLogger(__name__)


def handle_request(
    geography_slug: str,
    lead_type_slug: str,
    user_id: Optional[str] = None,
    force_refresh: bool = False,
) -> RunResult:
    settings = get_settings()
    run_month = settings.run_month()

    with get_db() as db:
        geo_repo = GeographyRepo(db)

        geo = geo_repo.get_by_slug(geography_slug)
        if not geo:
            raise ValueError(f"Unknown geography: {geography_slug}")

        lead_types = geo_repo.get_active_lead_types()
        lead_type = next((lt for lt in lead_types if lt.slug == lead_type_slug), None)
        if not lead_type:
            raise ValueError(f"Unknown lead type: {lead_type_slug}")

        if not force_refresh:
            cached = _find_valid_cache(db, geo.id, lead_type.id, run_month)
            if cached:
                logger.info(
                    "on_demand_cache_hit geo=%s lead_type=%s list_id=%d user=%s",
                    geography_slug, lead_type_slug, cached.id, user_id,
                )
                return RunResult(
                    run_uuid="cache",
                    status=RunStatus.COMPLETED,
                    geography_slug=geography_slug,
                    lead_type_slug=lead_type_slug,
                    run_month=run_month,
                    pages_fetched=0,
                    raw_count=cached.property_count,
                    new_count=0,
                    updated_count=0,
                    duplicate_count=0,
                )

        return RunOrchestrator(db).execute(
            geo=geo,
            lead_type=lead_type,
            trigger_type=TriggerType.ON_DEMAND,
            triggered_by=user_id or "system:on_demand",
        )


def _find_valid_cache(
    db, geography_id: int, lead_type_id: int, run_month: str
) -> Optional[LeadListDefinition]:
    now = datetime.now(timezone.utc)
    return (
        db.query(LeadListDefinition)
        .filter(
            LeadListDefinition.geography_id == geography_id,
            LeadListDefinition.lead_type_id == lead_type_id,
            LeadListDefinition.list_month == run_month,
            LeadListDefinition.is_current == True,
            LeadListDefinition.expires_at > now,
        )
        .first()
    )


def main() -> int:
    import os
    payload_str = os.environ.get("JOB_PAYLOAD", "{}")
    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        logger.error("Invalid JOB_PAYLOAD: %s", payload_str)
        return 1

    geo_slug = payload.get("geography_slug")
    lt_slug = payload.get("lead_type_slug")
    user_id = payload.get("user_id")
    force = payload.get("force_refresh", False)

    if not geo_slug or not lt_slug:
        logger.error("JOB_PAYLOAD missing geography_slug or lead_type_slug")
        return 1

    try:
        result = handle_request(geo_slug, lt_slug, user_id, force)
        logger.info("on_demand_completed status=%s run_uuid=%s", result.status, result.run_uuid)
        return 0
    except Exception as exc:
        logger.error("on_demand_failed error=%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
