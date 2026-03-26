"""
Property deduplication service.

Strategy (v1 — exact match only):
1. Compute canonical_hash from normalized address
2. Lookup properties table by canonical_hash
3. Secondary lookup by zillow_zpid if hash miss (handles Zillow address reformatting)
4. Found → update last_seen_at + mutable attrs, return existing id
5. Not found → insert new canonical property row

Fuzzy matching is NOT in v1. Add in v2 as a consolidation sweep.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.db import Property
from app.models.domain import NormalizedProperty

logger = logging.getLogger(__name__)


@dataclass
class DedupResult:
    property_id: int
    is_new: bool
    is_updated: bool
    canonical_hash: str


@dataclass
class BatchDedupStats:
    new_count: int = 0
    updated_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0
    property_ids: list[int] = field(default_factory=list)


class DedupService:
    def __init__(self, db: Session):
        self._db = db

    def upsert_property(
        self, prop: NormalizedProperty, geography_id: Optional[int] = None
    ) -> DedupResult:
        now = datetime.now(timezone.utc)

        # Primary: canonical hash lookup
        existing = (
            self._db.query(Property)
            .filter(Property.canonical_hash == prop.canonical_hash)
            .first()
        )

        # Secondary: zpid lookup (Zillow sometimes reformats addresses)
        if existing is None and prop.zillow_zpid:
            existing = (
                self._db.query(Property)
                .filter(Property.zillow_zpid == prop.zillow_zpid)
                .first()
            )

        if existing:
            is_updated = self._apply_updates(existing, prop, now)
            return DedupResult(
                property_id=existing.id,
                is_new=False,
                is_updated=is_updated,
                canonical_hash=existing.canonical_hash,
            )

        new_prop = Property(
            canonical_hash=prop.canonical_hash,
            address_line1=prop.address_line1,
            address_city=prop.address_city,
            address_state=prop.address_state,
            address_zip=prop.address_zip,
            geography_id=geography_id,
            beds=prop.beds,
            baths=prop.baths,
            sqft=prop.sqft,
            lot_area_value=prop.lot_area_value,
            lot_area_unit=prop.lot_area_unit,
            zillow_zpid=prop.zillow_zpid,
            latitude=prop.latitude,
            longitude=prop.longitude,
            first_seen_at=now,
            last_seen_at=now,
            is_active=True,
        )
        self._db.add(new_prop)
        self._db.flush()

        return DedupResult(
            property_id=new_prop.id,
            is_new=True,
            is_updated=False,
            canonical_hash=new_prop.canonical_hash,
        )

    def _apply_updates(self, existing: Property, prop: NormalizedProperty, now: datetime) -> bool:
        """Update mutable fields on an existing property. Returns True if data changed."""
        changed = False

        existing.last_seen_at = now
        existing.is_active = True

        # Enrich with data we now have if we didn't before
        if prop.latitude and not existing.latitude:
            existing.latitude = prop.latitude
            changed = True
        if prop.longitude and not existing.longitude:
            existing.longitude = prop.longitude
            changed = True
        if prop.zillow_zpid and not existing.zillow_zpid:
            existing.zillow_zpid = prop.zillow_zpid
            changed = True
        if prop.beds is not None and existing.beds != prop.beds:
            existing.beds = prop.beds
            changed = True
        if prop.baths is not None and existing.baths != prop.baths:
            existing.baths = prop.baths
            changed = True
        if prop.sqft is not None and existing.sqft != prop.sqft:
            existing.sqft = prop.sqft
            changed = True

        return changed

    def process_batch(
        self,
        properties: list[NormalizedProperty],
        geography_id: Optional[int],
    ) -> BatchDedupStats:
        """Process a batch. Tracks within-batch duplicates."""
        stats = BatchDedupStats()
        seen_this_batch: set[str] = set()

        for prop in properties:
            if prop.canonical_hash in seen_this_batch:
                stats.duplicate_count += 1
                continue
            seen_this_batch.add(prop.canonical_hash)

            try:
                result = self.upsert_property(prop, geography_id)
                stats.property_ids.append(result.property_id)
                if result.is_new:
                    stats.new_count += 1
                elif result.is_updated:
                    stats.updated_count += 1
            except Exception as exc:
                logger.error("Dedup failed for %s: %s", prop.canonical_hash[:12], exc)
                stats.failed_count += 1

        return stats
