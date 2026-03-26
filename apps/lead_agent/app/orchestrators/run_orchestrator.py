"""
RunOrchestrator: coordinates the full pipeline for one geography + lead type.

Steps:
  1. Create scrape_run record (PENDING)
  2. Generate Zillow URL
  3. Fetch pages via ScrapingBee + store raw artifacts
  4. Parse HTML → List[PropertyRaw]
  5. Normalize → List[NormalizedProperty]
  6. Dedup + upsert canonical properties
  7. Create observation rows
  8. Upsert lead_list_definition + add membership rows
  9. Apply property tags (lead_type tag + system tags: multi_list, recurring)
 10. Mark run COMPLETED (or FAILED)
 11. Emit structured log metrics
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.db import PropertyTag, PropertyTagMap
from app.models.domain import (
    GeographyRecord,
    LeadTypeRecord,
    NormalizedProperty,
    RunResult,
    RunStatus,
    TriggerType,
)
from app.parsers.zillow_parser import RESULTS_PER_PAGE, extract_total_results, parse_listings
from app.repositories.geography_repo import GeographyRepo
from app.repositories.scrape_run_repo import ScrapeRunRepo
from app.services.dedup_service import DedupService
from app.services.normalizer import normalize_property_raw
from app.services.scrape_service import ScrapeService
from app.services.url_generator import build_paginated_url, generate_url

logger = logging.getLogger(__name__)

# Must match the sources table seed (slug='zillow', id=1 after seed_job runs)
ZILLOW_SOURCE_ID = 1


class RunOrchestrator:
    def __init__(self, db: Session):
        self._db = db
        self._settings = get_settings()
        self._scrape = ScrapeService()
        self._run_repo = ScrapeRunRepo(db)
        self._dedup = DedupService(db)

    def execute(
        self,
        geo: GeographyRecord,
        lead_type: LeadTypeRecord,
        trigger_type: TriggerType = TriggerType.SCHEDULED,
        triggered_by: Optional[str] = None,
    ) -> RunResult:
        start = time.monotonic()
        settings = self._settings
        run_month = settings.run_month()
        zillow_url = generate_url(geo.zillow_slug, lead_type.url_template)

        run = self._run_repo.create_run(
            geography_id=geo.id,
            lead_type_id=lead_type.id,
            source_id=ZILLOW_SOURCE_ID,
            trigger_type=trigger_type,
            run_month=run_month,
            zillow_url=zillow_url,
            triggered_by=triggered_by,
        )
        run_id = run.id
        run_uuid = run.run_uuid

        logger.info(
            "scrape_run_started run_uuid=%s geo=%s lead_type=%s month=%s",
            run_uuid, geo.zillow_slug, lead_type.slug, run_month,
        )

        try:
            self._run_repo.mark_running(run_id)

            all_normalized, pages_fetched, raw_count, blob_path = self._scrape_and_normalize(
                zillow_url, run_uuid, settings.scrape_max_pages
            )

            if not all_normalized:
                self._run_repo.mark_completed(run_id, pages_fetched, raw_count, 0, 0, 0, blob_path)
                return RunResult(
                    run_uuid=run_uuid, status=RunStatus.COMPLETED,
                    geography_slug=geo.zillow_slug, lead_type_slug=lead_type.slug,
                    run_month=run_month, pages_fetched=pages_fetched,
                    raw_count=raw_count, new_count=0, updated_count=0, duplicate_count=0,
                    duration_seconds=time.monotonic() - start,
                )

            dedup_stats = self._dedup.process_batch(all_normalized, geography_id=geo.id)

            # Observations
            observation_map: dict[int, int] = {}
            for prop, prop_id in zip(all_normalized, dedup_stats.property_ids):
                obs = self._run_repo.create_observation(
                    property_id=prop_id, run_id=run_id, run_month=run_month,
                    price=prop.price, listing_status=prop.listing_status,
                    days_on_market=prop.days_on_market,
                    zillow_url=prop.detail_url, raw_json=prop.raw_json,
                )
                if obs:
                    observation_map[prop_id] = obs.id

            # Lead list
            ttl = {1: settings.cache_ttl_days_tier1, 2: settings.cache_ttl_days_tier2}.get(
                geo.priority_tier, settings.cache_ttl_days_tier3
            )
            lead_list = self._run_repo.upsert_lead_list(
                geography_id=geo.id, lead_type_id=lead_type.id,
                list_month=run_month, run_id=run_id,
                property_count=len(dedup_stats.property_ids),
                expires_at=datetime.now(timezone.utc) + timedelta(days=ttl),
            )
            entries = [(pid, observation_map.get(pid)) for pid in dedup_stats.property_ids]
            self._run_repo.add_list_memberships(lead_list.id, entries)

            # Step 9: tag every property with its lead type + system tags
            self._apply_tags(dedup_stats.property_ids, lead_type.slug)

            self._run_repo.mark_completed(
                run_id, pages=pages_fetched, raw=raw_count,
                new=dedup_stats.new_count, updated=dedup_stats.updated_count,
                dupes=dedup_stats.duplicate_count, blob_path=blob_path,
            )

            duration = time.monotonic() - start
            result = RunResult(
                run_uuid=run_uuid, status=RunStatus.COMPLETED,
                geography_slug=geo.zillow_slug, lead_type_slug=lead_type.slug,
                run_month=run_month, pages_fetched=pages_fetched,
                raw_count=raw_count, new_count=dedup_stats.new_count,
                updated_count=dedup_stats.updated_count,
                duplicate_count=dedup_stats.duplicate_count,
                duration_seconds=duration,
            )
            logger.info(
                "scrape_run_completed run_uuid=%s geo=%s lead_type=%s "
                "pages=%d raw=%d new=%d updated=%d dupes=%d duration=%.1fs",
                run_uuid, geo.zillow_slug, lead_type.slug,
                pages_fetched, raw_count, dedup_stats.new_count,
                dedup_stats.updated_count, dedup_stats.duplicate_count, duration,
            )
            return result

        except Exception as exc:
            self._run_repo.mark_failed(run_id, str(exc))
            logger.error(
                "scrape_run_failed run_uuid=%s geo=%s lead_type=%s error=%s",
                run_uuid, geo.zillow_slug, lead_type.slug, exc,
            )
            return RunResult(
                run_uuid=run_uuid, status=RunStatus.FAILED,
                geography_slug=geo.zillow_slug, lead_type_slug=lead_type.slug,
                run_month=run_month, pages_fetched=0, raw_count=0,
                new_count=0, updated_count=0, duplicate_count=0,
                error_message=str(exc), duration_seconds=time.monotonic() - start,
            )

    def _apply_tags(self, property_ids: list[int], lead_type_slug: str) -> None:
        """Upsert property_tag_map rows for every property in this run.

        Tags applied:
        - <lead_type_slug>  — e.g. 'pre_foreclosure' (category: lead_type)
        - 'multi_list'      — if the property already has a *different* lead_type tag
        - 'recurring'       — if the property was tagged with this same lead_type before
                              (i.e. it appeared in a prior month's run)
        """
        if not property_ids:
            return

        db = self._db

        # Build slug → id lookup for the tags we need
        slugs_needed = {lead_type_slug, "multi_list", "recurring"}
        tag_rows = db.execute(
            select(PropertyTag.slug, PropertyTag.id).where(PropertyTag.slug.in_(slugs_needed))
        ).all()
        tag_id: dict[str, int] = {row.slug: row.id for row in tag_rows}

        lead_type_tag_id = tag_id.get(lead_type_slug)
        multi_list_tag_id = tag_id.get("multi_list")
        recurring_tag_id = tag_id.get("recurring")

        if not lead_type_tag_id:
            logger.warning("tag_missing slug=%s — skipping tagging", lead_type_slug)
            return

        # Which properties already have this lead_type tag? → recurring
        already_tagged = set(
            db.execute(
                select(PropertyTagMap.property_id).where(
                    PropertyTagMap.property_id.in_(property_ids),
                    PropertyTagMap.tag_id == lead_type_tag_id,
                )
            ).scalars()
        )

        # Which properties already have *any* lead_type tag (different from this one)? → multi_list
        all_lead_type_tag_ids = list(
            db.execute(
                select(PropertyTag.id).where(PropertyTag.tag_category == "lead_type")
            ).scalars()
        )
        has_other_lead_tag = set(
            db.execute(
                select(PropertyTagMap.property_id).where(
                    PropertyTagMap.property_id.in_(property_ids),
                    PropertyTagMap.tag_id.in_(all_lead_type_tag_ids),
                    PropertyTagMap.tag_id != lead_type_tag_id,
                )
            ).scalars()
        )

        rows_to_upsert: list[dict] = []
        for pid in property_ids:
            rows_to_upsert.append({"property_id": pid, "tag_id": lead_type_tag_id, "tagged_by": "scrape"})
            if recurring_tag_id and pid in already_tagged:
                rows_to_upsert.append({"property_id": pid, "tag_id": recurring_tag_id, "tagged_by": "system"})
            if multi_list_tag_id and pid in has_other_lead_tag:
                rows_to_upsert.append({"property_id": pid, "tag_id": multi_list_tag_id, "tagged_by": "system"})

        if rows_to_upsert:
            stmt = pg_insert(PropertyTagMap).values(rows_to_upsert)
            stmt = stmt.on_conflict_do_nothing(index_elements=["property_id", "tag_id"])
            db.execute(stmt)
            db.commit()

        logger.info(
            "tags_applied lead_type=%s properties=%d recurring=%d multi_list=%d",
            lead_type_slug, len(property_ids), len(already_tagged), len(has_other_lead_tag),
        )

    def _scrape_and_normalize(
        self, zillow_url: str, run_uuid: str, max_pages: int
    ) -> tuple[list[NormalizedProperty], int, int, Optional[str]]:
        scrape = self._scrape
        all_raw = []
        pages_fetched = 0
        blob_path = None

        content = scrape.fetch_page(zillow_url)
        if content:
            blob_path = scrape.store_raw_artifact(run_uuid, 1, content)
            all_raw.extend(parse_listings(content))
            pages_fetched = 1

            total = extract_total_results(content)
            needed = min(math.ceil(total / RESULTS_PER_PAGE), max_pages) if total > 0 else 1

            for page in range(2, needed + 1):
                page_url = build_paginated_url(zillow_url, page)
                page_content = scrape.fetch_page(page_url)
                if page_content:
                    scrape.store_raw_artifact(run_uuid, page, page_content)
                    all_raw.extend(parse_listings(page_content))
                    pages_fetched += 1

        raw_count = len(all_raw)
        normalized = [normalize_property_raw(r) for r in all_raw]
        normalized = [n for n in normalized if n is not None]
        return normalized, pages_fetched, raw_count, blob_path
