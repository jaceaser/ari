"""
One-time backfill job — seeds the last N days of Dignity Memorial obituaries.

Default: 365 days.  The job is idempotent: re-running it simply skips records
that already exist (ON CONFLICT DO NOTHING).

Concurrency model (queue/worker):
  - Pages are enqueued into a bounded Queue.
  - A pool of worker threads drain the queue concurrently.
  - Each worker adds a small jittered delay between requests.
  - Workers stop automatically when any page returns 0 parsed rows.
  - A checkpoint is written after every batch so the run can be resumed.

Resume behaviour:
  - On startup, the last completed page is read from `obituary_backfill_state`.
  - Processing restarts from (last_completed_page + 1).
  - Pass --resume-from-page N on the CLI to override the checkpoint.
"""
from __future__ import annotations

import logging
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.config import get_settings
from app.db.session import get_db
from app.parsers.obituary_parser import parse_records
from app.repositories.obituary_repo import ObituaryRepo
from app.services.obituary_scraper import ObituaryScraper

logger = logging.getLogger(__name__)

# Safety cap — Dignity Memorial shouldn't have more than ~10k pages for 365 days,
# but we cap high to avoid an infinite loop if pagination logic has a bug.
_MAX_PAGES = 5_000
_DATE_FILTER = 365


@dataclass
class _PageResult:
    page: int
    rows_parsed: int
    inserted: int
    deduped: int
    malformed: int
    error: Optional[str] = None


@dataclass
class BackfillStats:
    pages_processed: int = 0
    rows_inserted: int = 0
    rows_deduped: int = 0
    rows_malformed: int = 0
    pages_failed: int = 0
    pages_empty: int = 0


def _process_page(
    scraper: ObituaryScraper,
    date_filter: int,
    page: int,
    delay_ms_min: int,
    delay_ms_max: int,
) -> _PageResult:
    """Fetch, parse, and insert one obituary listing page. Thread-safe."""
    # Jittered delay before the request to avoid thundering-herd
    time.sleep(random.uniform(delay_ms_min, delay_ms_max) / 1000.0)

    try:
        records, source_url = scraper.fetch_page(date_filter, page)
    except Exception as exc:
        return _PageResult(page=page, rows_parsed=0, inserted=0, deduped=0, malformed=0, error=str(exc))

    if records is None:
        return _PageResult(page=page, rows_parsed=0, inserted=0, deduped=0, malformed=0)

    rows, malformed = parse_records(records)

    if not rows:
        return _PageResult(page=page, rows_parsed=0, inserted=0, deduped=0, malformed=malformed)

    with get_db() as db:
        repo = ObituaryRepo(db)
        stats = repo.upsert_many(rows, source_url, scraped_at=datetime.now(timezone.utc))

    return _PageResult(
        page=page,
        rows_parsed=len(rows),
        inserted=stats.inserted,
        deduped=stats.deduped,
        malformed=malformed,
    )


def run_backfill(
    date_filter: int = _DATE_FILTER,
    concurrency: Optional[int] = None,
    resume: bool = True,
    start_page: Optional[int] = None,
) -> int:
    """
    Run the backfill.  Returns 0 on success, 1 if any pages failed.

    Args:
        date_filter:  Dignity Memorial creationDateFilter value (default 365).
        concurrency:  Worker count. Defaults to OBITUARY_BACKFILL_CONCURRENCY (25).
        resume:       If True (default), read the checkpoint and continue from there.
        start_page:   Override the starting page (ignores checkpoint when set).
    """
    settings = get_settings()
    workers = concurrency if concurrency is not None else settings.obituary_backfill_concurrency
    delay_min = settings.obituary_request_delay_ms_min
    delay_max = settings.obituary_request_delay_ms_max

    # ── Determine starting page ───────────────────────────────────────────────
    if start_page is not None:
        first_page = start_page
        logger.info("backfill_start date_filter=%d start_page=%d (manual override)", date_filter, first_page)
    elif resume:
        with get_db() as db:
            repo = ObituaryRepo(db)
            checkpoint = repo.get_last_completed_page(date_filter)
        first_page = checkpoint + 1
        logger.info(
            "backfill_start date_filter=%d resume=true checkpoint=%d first_page=%d",
            date_filter, checkpoint, first_page,
        )
    else:
        first_page = 1
        logger.info("backfill_start date_filter=%d resume=false first_page=1", date_filter)

    scraper = ObituaryScraper(settings.scrapingbee_api_key, settings.scrape_timeout_seconds)

    total = BackfillStats()
    stop_event = threading.Event()

    # ── Queue / worker model ──────────────────────────────────────────────────
    # Pages are submitted in batches equal to the concurrency window.
    # We advance to the next batch only after the current one fully completes.
    # This keeps the checkpoint simple: after each batch we record the highest
    # page number in that batch.
    page = first_page

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while not stop_event.is_set() and page < first_page + _MAX_PAGES:
            # Build current batch
            batch_end = min(page + workers, first_page + _MAX_PAGES)
            batch = list(range(page, batch_end))

            futures = {
                pool.submit(
                    _process_page, scraper, date_filter, p, delay_min, delay_max
                ): p
                for p in batch
            }

            batch_max_page = page
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    result = fut.result()
                except Exception as exc:
                    logger.error("page_exception page=%d err=%s", p, exc)
                    total.pages_failed += 1
                    continue

                batch_max_page = max(batch_max_page, result.page)

                if result.error:
                    logger.error("page_failed page=%d err=%s", result.page, result.error)
                    total.pages_failed += 1
                    continue

                total.pages_processed += 1
                total.rows_inserted += result.inserted
                total.rows_deduped += result.deduped
                total.rows_malformed += result.malformed

                if result.rows_parsed == 0:
                    logger.info(
                        "page_empty page=%d — no more results, stopping pagination",
                        result.page,
                    )
                    total.pages_empty += 1
                    stop_event.set()
                else:
                    logger.info(
                        "page_done page=%d rows_parsed=%d inserted=%d deduped=%d malformed=%d",
                        result.page,
                        result.rows_parsed,
                        result.inserted,
                        result.deduped,
                        result.malformed,
                    )

            # Save checkpoint after each completed batch
            with get_db() as db:
                ObituaryRepo(db).save_backfill_progress(date_filter, batch_max_page)
            logger.info("checkpoint_saved date_filter=%d last_page=%d", date_filter, batch_max_page)

            page += len(batch)

    logger.info(
        "backfill_complete date_filter=%d pages=%d inserted=%d deduped=%d "
        "malformed=%d failed=%d",
        date_filter,
        total.pages_processed,
        total.rows_inserted,
        total.rows_deduped,
        total.rows_malformed,
        total.pages_failed,
    )

    return 1 if total.pages_failed > 0 else 0


if __name__ == "__main__":
    from app.utils.logging import configure_logging
    configure_logging()
    sys.exit(run_backfill())
