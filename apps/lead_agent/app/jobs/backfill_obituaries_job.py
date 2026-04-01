"""
One-time backfill job — seeds the last N days of Dignity Memorial obituaries.

Default: 365 days.  The job is idempotent: re-running it simply skips records
that already exist (ON CONFLICT DO NOTHING).

State-by-state pagination:
  The Dignity Memorial search API (backed by Elasticsearch/Solr) caps results at
  200 pages (10,000 records) per query regardless of the total result count.
  A single nationwide query would silently truncate at 10k.  To capture all
  ~234k obituaries we iterate state-by-state using the `locationState` parameter
  so each state's result set stays well under 10k.

Concurrency model (queue/worker):
  - Pages are submitted in batches equal to the concurrency window.
  - A pool of worker threads drain the batch concurrently.
  - Each worker adds a small jittered delay between requests.
  - Workers stop automatically when any page returns 0 parsed rows for a state.
  - A checkpoint is written after every batch so the run can be resumed.

Resume behaviour:
  - On startup, the last completed page is read from `obituary_backfill_state`
    for each (date_filter, state) pair.
  - Processing restarts from (last_completed_page + 1) per state.
  - Pass --resume-from-page N on the CLI to override for all states.
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

# Safety cap per state — no US state has anywhere near 200 pages (10k) of
# obituaries in 365 days, but cap high to avoid infinite loops.
_MAX_PAGES_PER_STATE = 500
_DATE_FILTER = 365

# All 54 US states, territories, and DC — matches _KNOWN_CODES in obituary_parser.py
_US_STATES: list[str] = [
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU",
]


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
    state: str,
    page: int,
    delay_ms_min: int,
    delay_ms_max: int,
) -> _PageResult:
    """Fetch, parse, and insert one obituary listing page. Thread-safe."""
    time.sleep(random.uniform(delay_ms_min, delay_ms_max) / 1000.0)

    try:
        records, source_url = scraper.fetch_page(date_filter, page, state=state)
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


def _backfill_state(
    scraper: ObituaryScraper,
    date_filter: int,
    state: str,
    workers: int,
    delay_min: int,
    delay_max: int,
    resume: bool,
    start_page: Optional[int],
) -> BackfillStats:
    """Run the full pagination loop for a single state. Returns per-state stats."""
    # Determine starting page for this state
    if start_page is not None:
        first_page = start_page
    elif resume:
        with get_db() as db:
            checkpoint = ObituaryRepo(db).get_last_completed_page(date_filter, state)
        first_page = checkpoint + 1
        if first_page > 1:
            logger.info("state_resume state=%s checkpoint=%d first_page=%d", state, checkpoint, first_page)
    else:
        first_page = 1

    if first_page > _MAX_PAGES_PER_STATE:
        logger.info("state_skip state=%s first_page=%d >= max=%d", state, first_page, _MAX_PAGES_PER_STATE)
        return BackfillStats()

    total = BackfillStats()
    stop_event = threading.Event()
    page = first_page

    with ThreadPoolExecutor(max_workers=workers) as pool:
        while not stop_event.is_set() and page < first_page + _MAX_PAGES_PER_STATE:
            batch_end = min(page + workers, first_page + _MAX_PAGES_PER_STATE)
            batch = list(range(page, batch_end))

            futures = {
                pool.submit(
                    _process_page, scraper, date_filter, state, p, delay_min, delay_max
                ): p
                for p in batch
            }

            batch_max_page = page
            for fut in as_completed(futures):
                p = futures[fut]
                try:
                    result = fut.result()
                except Exception as exc:
                    logger.error("page_exception state=%s page=%d err=%s", state, p, exc)
                    total.pages_failed += 1
                    continue

                batch_max_page = max(batch_max_page, result.page)

                if result.error:
                    logger.error("page_failed state=%s page=%d err=%s", state, result.page, result.error)
                    total.pages_failed += 1
                    continue

                total.pages_processed += 1
                total.rows_inserted += result.inserted
                total.rows_deduped += result.deduped
                total.rows_malformed += result.malformed

                if result.rows_parsed == 0:
                    logger.info("page_empty state=%s page=%d — pagination exhausted", state, result.page)
                    total.pages_empty += 1
                    stop_event.set()
                else:
                    logger.info(
                        "page_done state=%s page=%d rows=%d inserted=%d deduped=%d malformed=%d",
                        state, result.page, result.rows_parsed, result.inserted,
                        result.deduped, result.malformed,
                    )

            # Checkpoint after each batch
            with get_db() as db:
                ObituaryRepo(db).save_backfill_progress(date_filter, batch_max_page, state)
            logger.info("checkpoint state=%s last_page=%d", state, batch_max_page)

            page += len(batch)

    return total


def run_backfill(
    date_filter: int = _DATE_FILTER,
    concurrency: Optional[int] = None,
    resume: bool = True,
    start_page: Optional[int] = None,
    states: Optional[list[str]] = None,
) -> int:
    """
    Run the backfill across all US states/territories.  Returns 0 on success,
    1 if any pages failed.

    Args:
        date_filter:  Dignity Memorial creationDate value (default 365).
        concurrency:  Worker count per state. Defaults to OBITUARY_BACKFILL_CONCURRENCY (25).
        resume:       If True (default), read checkpoint per state and continue from there.
        start_page:   Override starting page for ALL states (ignores checkpoints when set).
        states:       Specific state codes to process (default: all 54 US states/territories).
    """
    settings = get_settings()
    workers = concurrency if concurrency is not None else settings.obituary_backfill_concurrency
    delay_min = settings.obituary_request_delay_ms_min
    delay_max = settings.obituary_request_delay_ms_max

    target_states = states or _US_STATES

    logger.info(
        "backfill_start date_filter=%d states=%d concurrency=%d resume=%s",
        date_filter, len(target_states), workers, resume,
    )

    scraper = ObituaryScraper(settings.scrapingbee_api_key, settings.scrape_timeout_seconds)

    grand_total = BackfillStats()

    for state in target_states:
        logger.info("state_start state=%s date_filter=%d", state, date_filter)
        stats = _backfill_state(
            scraper=scraper,
            date_filter=date_filter,
            state=state,
            workers=workers,
            delay_min=delay_min,
            delay_max=delay_max,
            resume=resume,
            start_page=start_page,
        )
        grand_total.pages_processed += stats.pages_processed
        grand_total.rows_inserted += stats.rows_inserted
        grand_total.rows_deduped += stats.rows_deduped
        grand_total.rows_malformed += stats.rows_malformed
        grand_total.pages_failed += stats.pages_failed
        grand_total.pages_empty += stats.pages_empty

        logger.info(
            "state_complete state=%s pages=%d inserted=%d deduped=%d failed=%d",
            state, stats.pages_processed, stats.rows_inserted, stats.rows_deduped, stats.pages_failed,
        )

    logger.info(
        "backfill_complete date_filter=%d total_pages=%d inserted=%d deduped=%d "
        "malformed=%d failed=%d",
        date_filter,
        grand_total.pages_processed,
        grand_total.rows_inserted,
        grand_total.rows_deduped,
        grand_total.rows_malformed,
        grand_total.pages_failed,
    )

    return 1 if grand_total.pages_failed > 0 else 0


if __name__ == "__main__":
    from app.utils.logging import configure_logging
    configure_logging()
    sys.exit(run_backfill())
