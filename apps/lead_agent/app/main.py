"""
CLI entry point for the lead agent.

Usage:
  python -m app.main monthly-refresh
  python -m app.main on-demand --geo harris-county-tx --lead-type pre_foreclosure
  python -m app.main seed
  python -m app.main migrate
"""
from __future__ import annotations

import sys

import click

from app.utils.logging import configure_logging


@click.group()
def cli():
    """ARI Lead Agent — Zillow lead ingestion pipeline."""
    configure_logging()


@cli.command("monthly-refresh")
@click.option("--tier", default=1, show_default=True, help="Max priority tier (1=top100)")
@click.option(
    "--lead-types", "lead_types", default=None,
    help="Comma-separated lead type slugs to run (default: all active). "
         "e.g. pre_foreclosure,fsbo",
)
def monthly_refresh(tier: int, lead_types: str):
    """Run scheduled refresh for all tier-N geographies.

    Use --lead-types to target specific lead types, enabling
    different Container Apps Job schedules per cadence group.

    Examples:
      Weekly:    python -m app.main monthly-refresh --lead-types pre_foreclosure
      Bi-weekly: python -m app.main monthly-refresh --lead-types fsbo,as_is
      Monthly:   python -m app.main monthly-refresh --lead-types land,tired_landlord,fixer_upper,subject_to
    """
    slugs = [s.strip() for s in lead_types.split(",")] if lead_types else None
    from app.jobs.monthly_refresh_job import main
    sys.exit(main(lead_type_slugs=slugs, max_tier=tier))


@cli.command("on-demand")
@click.option("--geo", required=True, help="Zillow slug, e.g. harris-county-tx")
@click.option("--lead-type", "lead_type", required=True, help="e.g. pre_foreclosure")
@click.option("--user-id", "user_id", default=None)
@click.option("--force", is_flag=True, default=False, help="Bypass cache")
def on_demand(geo: str, lead_type: str, user_id: str, force: bool):
    """Execute a single on-demand scrape."""
    from app.jobs.on_demand_job import handle_request
    result = handle_request(geo, lead_type, user_id, force)
    click.echo(result.model_dump_json(indent=2))


@cli.command("seed")
def seed():
    """Seed the geographies, lead_types, sources, and reference tables."""
    from app.jobs.seed_job import run_seed
    run_seed()
    click.echo("Seed complete.")


@cli.command("backfill-obituaries")
@click.option(
    "--date-filter", "date_filter", default=365, show_default=True,
    help="Dignity Memorial creationDateFilter (days back to seed).",
)
@click.option(
    "--concurrency", default=None, type=int,
    help="Worker threads (default: OBITUARY_BACKFILL_CONCURRENCY env var, factory 25).",
)
@click.option(
    "--no-resume", "no_resume", is_flag=True, default=False,
    help="Ignore checkpoint and start from page 1.",
)
@click.option(
    "--start-page", "start_page", default=None, type=int,
    help="Start from a specific page number, overriding the saved checkpoint.",
)
def backfill_obituaries(date_filter: int, concurrency: int, no_resume: bool, start_page: int):
    """One-time 365-day backfill of Dignity Memorial obituaries.

    Safe to re-run — duplicates are silently ignored.
    Resumes from the last saved checkpoint by default.

    Examples:

      Initial seed (resume-safe):
        python -m app.main backfill-obituaries

      Force restart from page 1:
        python -m app.main backfill-obituaries --no-resume

      Resume manually from page 200:
        python -m app.main backfill-obituaries --start-page 200

      Raise concurrency (after testing at default):
        OBITUARY_BACKFILL_CONCURRENCY=40 python -m app.main backfill-obituaries
    """
    from app.jobs.backfill_obituaries_job import run_backfill
    sys.exit(
        run_backfill(
            date_filter=date_filter,
            concurrency=concurrency,
            resume=not no_resume,
            start_page=start_page,
        )
    )


@cli.command("sync-recent-obituaries")
@click.option(
    "--overlap-days", "overlap_days", default=1, show_default=True,
    help="creationDateFilter: 1 = strict daily, 3 = 3-day overlap for delayed postings.",
)
@click.option(
    "--concurrency", default=None, type=int,
    help="Worker threads (default: OBITUARY_CONCURRENCY env var, factory 5).",
)
def sync_recent_obituaries(overlap_days: int, concurrency: int):
    """Daily sync — pulls recent Dignity Memorial obituaries.

    Safe to run multiple times — duplicates are ignored.

    Examples:

      Standard daily run:
        python -m app.main sync-recent-obituaries

      3-day overlap (catch delayed postings):
        python -m app.main sync-recent-obituaries --overlap-days 3
    """
    from app.jobs.sync_recent_obituaries_job import run_sync
    sys.exit(run_sync(overlap_days=overlap_days, concurrency=concurrency))


@cli.command("migrate")
def migrate():
    """Run Alembic migrations to head."""
    import subprocess
    result = subprocess.run(["alembic", "upgrade", "head"], check=False)
    sys.exit(result.returncode)


if __name__ == "__main__":
    cli()
