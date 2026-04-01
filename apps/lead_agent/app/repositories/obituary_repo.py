"""
Obituary database repository — bulk upsert with deduplication.

Dedup strategy (two layers):
  1. uq_obituary_link  — partial unique index on obituary_link (per-person page URL).
                         This is the primary dedup key when a link is available.
  2. uq_obituary       — composite unique constraint on (full_name, city, state,
                         source_site, source_url).  Catches records without a link.

Both are handled transparently by ON CONFLICT DO NOTHING (no target specified),
which suppresses ANY unique constraint violation.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.db import Obituary, ObituaryBackfillState
from app.parsers.obituary_parser import ObituaryRow

logger = logging.getLogger(__name__)


@dataclass
class InsertStats:
    inserted: int = 0
    deduped: int = 0


class ObituaryRepo:
    def __init__(self, db: Session):
        self._db = db

    def upsert_many(
        self,
        rows: list[ObituaryRow],
        source_url: str,
        scraped_at: Optional[datetime] = None,
    ) -> InsertStats:
        """
        Bulk insert rows using INSERT … ON CONFLICT DO NOTHING.

        ON CONFLICT without a target suppresses any unique violation —
        the obituary_link partial unique index fires first for linked records,
        the composite uq_obituary constraint fires for the rest.
        """
        if not rows:
            return InsertStats()

        now = scraped_at or datetime.now(timezone.utc)

        records = [
            {
                "id": uuid.uuid4(),
                "full_name": row.full_name,
                "city": row.city,
                "state": row.state,
                "date_of_birth": row.date_of_birth,
                "date_of_death": row.date_of_death,
                "obituary_link": row.obituary_link,
                "published_date": row.date_of_death,   # mirror for backward compat
                "source_site": "dignity_memorial",
                "source_url": source_url,
                "scraped_at": now,
            }
            for row in rows
        ]

        stmt = insert(Obituary).values(records).on_conflict_do_nothing()
        result = self._db.execute(stmt)
        self._db.commit()

        inserted = result.rowcount if result.rowcount >= 0 else len(rows)
        deduped = max(0, len(rows) - inserted)
        return InsertStats(inserted=inserted, deduped=deduped)

    # ── Backfill progress checkpoint ──────────────────────────────────────────

    def get_last_completed_page(self, date_filter: int, state: str = "") -> int:
        """Return the highest page successfully completed for (date_filter, state), or 0."""
        row = self._db.get(ObituaryBackfillState, {"date_filter": date_filter, "state": state})
        return row.last_completed_page if row else 0

    def save_backfill_progress(
        self, date_filter: int, last_completed_page: int, state: str = ""
    ) -> None:
        """Upsert the backfill checkpoint (only advances, never goes backwards)."""
        existing = self._db.get(ObituaryBackfillState, {"date_filter": date_filter, "state": state})
        if existing:
            if last_completed_page > existing.last_completed_page:
                existing.last_completed_page = last_completed_page
        else:
            self._db.add(
                ObituaryBackfillState(
                    date_filter=date_filter,
                    state=state,
                    last_completed_page=last_completed_page,
                )
            )
        self._db.commit()
