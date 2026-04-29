"""ScrapeRun repository — manages run lifecycle and observation writes."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import update, select
from sqlalchemy.orm import Session

from app.models.db import (
    LeadListDefinition,
    LeadListMembership,
    Property,
    PropertyObservation,
    PropertyTag,
    PropertyTagMap,
    ScrapeRun,
)
from app.models.domain import RunStatus, TriggerType


class ScrapeRunRepo:
    def __init__(self, db: Session):
        self._db = db

    def create_run(
        self,
        geography_id: int,
        lead_type_id: int,
        source_id: int,
        trigger_type: TriggerType,
        run_month: str,
        zillow_url: str,
        triggered_by: Optional[str] = None,
    ) -> ScrapeRun:
        run = ScrapeRun(
            run_uuid=str(uuid.uuid4()),
            geography_id=geography_id,
            lead_type_id=lead_type_id,
            source_id=source_id,
            trigger_type=trigger_type.value,
            triggered_by=triggered_by,
            status=RunStatus.PENDING.value,
            run_month=run_month,
            zillow_url=zillow_url,
        )
        self._db.add(run)
        self._db.commit()
        self._db.refresh(run)
        return run

    def mark_running(self, run_id: int) -> None:
        run = self._db.get(ScrapeRun, run_id)
        if run:
            run.status = RunStatus.RUNNING.value
            run.started_at = datetime.now(timezone.utc)
            self._db.commit()

    def mark_completed(
        self,
        run_id: int,
        pages: int,
        raw: int,
        new: int,
        updated: int,
        dupes: int,
        blob_path: Optional[str] = None,
    ) -> None:
        run = self._db.get(ScrapeRun, run_id)
        if run:
            run.status = RunStatus.COMPLETED.value
            run.completed_at = datetime.now(timezone.utc)
            run.pages_fetched = pages
            run.raw_count = raw
            run.new_count = new
            run.updated_count = updated
            run.duplicate_count = dupes
            run.raw_blob_path = blob_path
            self._db.commit()

    def mark_failed(self, run_id: int, error: str) -> None:
        run = self._db.get(ScrapeRun, run_id)
        if run:
            run.status = RunStatus.FAILED.value
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = error[:2000]
            self._db.commit()

    def create_observation(
        self,
        property_id: int,
        run_id: int,
        run_month: str,
        price: Optional[float],
        listing_status: Optional[str],
        days_on_market: Optional[int],
        zillow_url: Optional[str],
        raw_json: Optional[str],
    ) -> Optional[PropertyObservation]:
        """Insert observation. Returns None silently on unique constraint violation."""
        try:
            obs = PropertyObservation(
                property_id=property_id,
                scrape_run_id=run_id,
                run_month=run_month,
                price=price,
                listing_status=listing_status,
                days_on_market=days_on_market,
                zillow_url=zillow_url,
                raw_json=raw_json,
            )
            self._db.add(obs)
            self._db.flush()
            return obs
        except Exception:
            self._db.rollback()
            return None

    def upsert_lead_list(
        self,
        geography_id: int,
        lead_type_id: int,
        list_month: str,
        run_id: int,
        property_count: int,
        expires_at: datetime,
    ) -> LeadListDefinition:
        existing = (
            self._db.query(LeadListDefinition)
            .filter(
                LeadListDefinition.geography_id == geography_id,
                LeadListDefinition.lead_type_id == lead_type_id,
                LeadListDefinition.list_month == list_month,
            )
            .first()
        )
        now = datetime.now(timezone.utc)
        if existing:
            existing.scrape_run_id = run_id
            existing.property_count = property_count
            existing.generated_at = now
            existing.expires_at = expires_at
            existing.is_current = True
            self._db.commit()
            return existing

        lst = LeadListDefinition(
            geography_id=geography_id,
            lead_type_id=lead_type_id,
            list_month=list_month,
            scrape_run_id=run_id,
            property_count=property_count,
            generated_at=now,
            expires_at=expires_at,
            is_current=True,
        )
        self._db.add(lst)
        self._db.commit()
        self._db.refresh(lst)
        return lst

    def add_list_memberships(
        self,
        lead_list_id: int,
        entries: list[tuple[int, Optional[int]]],
    ) -> int:
        """Bulk-insert (property_id, observation_id) pairs. Returns inserted count."""
        inserted = 0
        for position, (property_id, observation_id) in enumerate(entries):
            try:
                self._db.add(LeadListMembership(
                    lead_list_id=lead_list_id,
                    property_id=property_id,
                    observation_id=observation_id,
                    position=position,
                ))
                self._db.flush()
                inserted += 1
            except Exception:
                self._db.rollback()
        self._db.commit()
        return inserted

    def expire_stale_properties(
        self,
        geography_id: int,
        lead_type_slug: str,
        refresh_interval_days: int,
        active_property_ids: list[int],
    ) -> int:
        """
        After a completed scrape, mark is_active=False on properties in this
        geography that carry the given lead_type tag but were not seen in the
        current run and haven't been seen within refresh_interval_days.

        Guards against false-expiry on empty runs: if active_property_ids is
        empty we skip — an empty scrape result most likely means a fetch error,
        not that all properties have gone off Zillow.

        Returns the number of properties expired.
        """
        if not active_property_ids:
            return 0

        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=refresh_interval_days)

        tagged_subq = (
            select(PropertyTagMap.property_id)
            .join(PropertyTag, PropertyTagMap.tag_id == PropertyTag.id)
            .where(PropertyTag.slug == lead_type_slug)
            .scalar_subquery()
        )

        stmt = (
            update(Property)
            .where(
                Property.geography_id == geography_id,
                Property.is_active == True,
                Property.last_seen_at < stale_cutoff,
                Property.id.in_(tagged_subq),
                Property.id.notin_(active_property_ids),
            )
            .values(is_active=False)
        )
        result = self._db.execute(stmt)
        self._db.commit()
        return result.rowcount
