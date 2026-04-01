"""
Daily sync job — pulls recent Dignity Memorial obituaries.

Default: last 1 day (creationDateFilter=1).
Overlap mode: last 3 days (creationDateFilter=3) to catch delayed postings.

Safe to run more than once — duplicates are silently ignored via ON CONFLICT DO NOTHING.
"""
from __future__ import annotations

import logging
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from app.config import get_settings
from app.db.session import get_db
from app.parsers.obituary_parser import parse_response
from app.repositories.obituary_repo import ObituaryRepo
from app.services.obituary_scraper import ObituaryScraper

logger = logging.getLogger(__name__)

_MAX_PAGES = 500  # safety cap for the daily sync


@dataclass
class SyncStats:
    pages_processed: int = 0
    rows_inserted: int = 0
    rows_deduped: int = 0
    rows_malformed: int = 0
    pages_failed: int = 0


def run_sync(
    overlap_days: int = 1,
    concurrency: Optional[int] = None,
) -> int:
    """
    Run the daily sync.  Returns 0 on success, 1 if any pages failed.

    Args:
        overlap_days: creationDateFilter value.  Use 1 for strict daily,
                      3 for a 3-day overlap to catch delayed postings.
        concurrency:  Worker count. Defaults to OBITUARY_CONCURRENCY (5).
    """
    settings = get_settings()
    workers = concurrency if concurrency is not None else settings.obituary_concurrency
    delay_min = settings.obituary_request_delay_ms_min
    delay_max = settings.obituary_request_delay_ms_max

    logger.info(
        "sync_start date_filter=%d concurrency=%d", overlap_days, workers
    )

    scraper = ObituaryScraper(settings.scrapingbee_api_key, settings.scrape_timeout_seconds)
    total = SyncStats()

    page = 1
    stop = False

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while not stop and page < _MAX_PAGES:
            batch = list(range(page, min(page + workers, _MAX_PAGES + 1)))

            futures = {
                pool.submit(_fetch_and_insert, scraper, overlap_days, p, delay_min, delay_max): p
                for p in batch
            }

            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    rows_parsed, inserted, deduped, malformed, error = fut.result()
                except Exception as exc:
                    logger.error("page_exception page=%d err=%s", p, exc)
                    total.pages_failed += 1
                    continue

                if error:
                    logger.error("page_failed page=%d err=%s", p, error)
                    total.pages_failed += 1
                    continue

                total.pages_processed += 1
                total.rows_inserted += inserted
                total.rows_deduped += deduped
                total.rows_malformed += malformed

                if rows_parsed == 0:
                    logger.info("page_empty page=%d — pagination exhausted", p)
                    stop = True
                else:
                    logger.info(
                        "page_done page=%d rows=%d inserted=%d deduped=%d malformed=%d",
                        p, rows_parsed, inserted, deduped, malformed,
                    )

            page += len(batch)

    logger.info(
        "sync_complete date_filter=%d pages=%d inserted=%d deduped=%d malformed=%d failed=%d",
        overlap_days,
        total.pages_processed,
        total.rows_inserted,
        total.rows_deduped,
        total.rows_malformed,
        total.pages_failed,
    )
    return 1 if total.pages_failed > 0 else 0


def _fetch_and_insert(
    scraper: ObituaryScraper,
    date_filter: int,
    page: int,
    delay_ms_min: int,
    delay_ms_max: int,
) -> tuple[int, int, int, int, Optional[str]]:
    """Returns (rows_parsed, inserted, deduped, malformed, error_str)."""
    time.sleep(random.uniform(delay_ms_min, delay_ms_max) / 1000.0)

    try:
        text, source_url = scraper.fetch_page(date_filter, page)
    except Exception as exc:
        return 0, 0, 0, 0, str(exc)

    if text is None:
        return 0, 0, 0, 0, None

    rows, malformed = parse_response(text)
    if not rows:
        return 0, 0, 0, malformed, None

    with get_db() as db:
        stats = ObituaryRepo(db).upsert_many(
            rows, source_url, scraped_at=datetime.now(timezone.utc)
        )

    return len(rows), stats.inserted, stats.deduped, malformed, None


if __name__ == "__main__":
    from app.utils.logging import configure_logging
    configure_logging()
    sys.exit(run_sync())
