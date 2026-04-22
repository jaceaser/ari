"""
Monthly refresh job — entry point for the scheduled Container Apps Job.
Scrapes all active tier-1 geographies × all active lead types.
"""
from __future__ import annotations

import logging
import sys

from app.models.domain import TriggerType
from app.orchestrators.batch_orchestrator import run_batch

logger = logging.getLogger(__name__)


def main(lead_type_slugs: list[str] | None = None, max_tier: int = 1, min_tier: int = 1) -> int:
    label = ",".join(lead_type_slugs) if lead_type_slugs else "all"
    logger.info("monthly_refresh_job_started lead_types=%s tier=%d-%d", label, min_tier, max_tier)

    results = run_batch(
        max_tier=max_tier,
        min_tier=min_tier,
        lead_type_slugs=lead_type_slugs,
        trigger_type=TriggerType.SCHEDULED,
        triggered_by=f"system:scheduled:{label}",
    )

    failed = [r for r in results if r.status.value == "failed"]
    for r in failed:
        logger.error(
            "run_failed geo=%s lead_type=%s error=%s",
            r.geography_slug, r.lead_type_slug, r.error_message,
        )

    logger.info(
        "monthly_refresh_job_completed total=%d failed=%d",
        len(results), len(failed),
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
