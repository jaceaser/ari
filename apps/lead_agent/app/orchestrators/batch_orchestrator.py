"""
BatchOrchestrator: fans RunOrchestrator out across geographies and lead types.
Used by the monthly refresh job.
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

from app.config import get_settings
from app.db.session import get_db
from app.models.domain import GeographyRecord, LeadTypeRecord, RunResult, TriggerType
from app.orchestrators.run_orchestrator import RunOrchestrator
from app.repositories.geography_repo import GeographyRepo

logger = logging.getLogger(__name__)


def run_batch(
    max_tier: int = 1,
    min_tier: int = 1,
    lead_type_slugs: Optional[list[str]] = None,
    trigger_type: TriggerType = TriggerType.SCHEDULED,
    triggered_by: Optional[str] = None,
) -> list[RunResult]:
    settings = get_settings()
    max_workers = settings.max_concurrent_scrapes
    results: list[RunResult] = []

    with get_db() as db:
        geo_repo = GeographyRepo(db)
        geographies = geo_repo.get_active_by_tier(max_tier=max_tier, min_tier=min_tier)
        lead_types = geo_repo.get_active_lead_types()

    if lead_type_slugs:
        lead_types = [lt for lt in lead_types if lt.slug in lead_type_slugs]

    tasks: list[tuple[GeographyRecord, LeadTypeRecord]] = [
        (geo, lt) for geo in geographies for lt in lead_types
    ]

    logger.info(
        "batch_started geos=%d lead_types=%d tasks=%d workers=%d tier=%d-%d",
        len(geographies), len(lead_types), len(tasks), max_workers, min_tier, max_tier,
    )

    def _run_one(geo: GeographyRecord, lt: LeadTypeRecord) -> RunResult:
        with get_db() as db:
            return RunOrchestrator(db).execute(geo, lt, trigger_type, triggered_by)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_run_one, geo, lt): (geo, lt) for geo, lt in tasks}
        for future in as_completed(futures):
            geo, lt = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                logger.error(
                    "batch_task_exception geo=%s lead_type=%s error=%s",
                    geo.zillow_slug, lt.slug, exc,
                )

    completed = sum(1 for r in results if r.status.value == "completed")
    failed = sum(1 for r in results if r.status.value == "failed")
    logger.info("batch_completed total=%d completed=%d failed=%d", len(results), completed, failed)
    return results
