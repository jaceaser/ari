"""
Seeds the database with:
- sources (zillow)
- lead_types (from url_generator.py templates — single source of truth)
- geographies (from seed/counties.json)
- pipeline_stages
- property_tags
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.db.session import get_db
from app.models.db import LeadType, PipelineStage, PropertyTag, Source
from app.repositories.geography_repo import GeographyRepo
from app.services.url_generator import LEAD_TYPE_TEMPLATES

logger = logging.getLogger(__name__)

SEED_DIR = Path(__file__).parent.parent.parent / "seed"


def run_seed() -> None:
    with get_db() as db:
        _seed_sources(db)
        _seed_lead_types(db)
        _seed_geographies(db)
        _seed_pipeline_stages(db)
        _seed_property_tags(db)
        db.commit()
    logger.info("Seed complete.")


def _seed_sources(db) -> None:
    if not db.query(Source).filter(Source.slug == "zillow").first():
        db.add(Source(slug="zillow", display_name="Zillow", base_url="https://www.zillow.com"))
        logger.info("Seeded source: zillow")


def _seed_lead_types(db) -> None:
    for slug, meta in LEAD_TYPE_TEMPLATES.items():
        existing = db.query(LeadType).filter(LeadType.slug == slug).first()
        if not existing:
            db.add(LeadType(
                slug=slug,
                display_name=meta["display_name"],
                url_template=meta["url_template"],
                refresh_interval_days=meta.get("refresh_interval_days", 30),
            ))
        else:
            # Keep templates up to date when code changes
            existing.url_template = meta["url_template"]
            existing.display_name = meta["display_name"]
            existing.refresh_interval_days = meta.get("refresh_interval_days", 30)
    logger.info("Seeded %d lead types", len(LEAD_TYPE_TEMPLATES))


def _seed_geographies(db) -> None:
    path = SEED_DIR / "counties.json"
    if not path.exists():
        logger.warning("No counties.json at %s — skipping geography seed", path)
        return
    with open(path) as f:
        records = json.load(f)
    repo = GeographyRepo(db)
    for record in records:
        repo.upsert_from_seed(record)
    logger.info("Seeded %d geographies", len(records))


def _seed_pipeline_stages(db) -> None:
    stages = [
        ("new", "New", 1, False),
        ("researching", "Researching", 2, False),
        ("skip_traced", "Skip Traced", 3, False),
        ("contacted", "Contacted", 4, False),
        ("negotiating", "Negotiating", 5, False),
        ("under_contract", "Under Contract", 6, False),
        ("closed", "Closed", 7, True),
        ("dead", "Dead", 8, True),
    ]
    for slug, display, order, terminal in stages:
        if not db.query(PipelineStage).filter(PipelineStage.slug == slug).first():
            db.add(PipelineStage(
                slug=slug, display_name=display, stage_order=order, is_terminal=terminal
            ))
    logger.info("Seeded %d pipeline stages", len(stages))


def _seed_property_tags(db) -> None:
    tags = [
        ("fsbo", "For Sale By Owner", "lead_type"),
        ("as_is", "Agent As-Is", "lead_type"),
        ("pre_foreclosure", "Pre-Foreclosure", "lead_type"),
        ("auction", "Auction", "lead_type"),
        ("land", "Land", "lead_type"),
        ("tired_landlord", "Tired Landlord", "lead_type"),
        ("fixer_upper", "Fixer Upper", "lead_type"),
        ("wholesale", "Wholesale", "lead_type"),
        ("subject_to", "Subject To", "lead_type"),
        ("multi_list", "Appeared in Multiple Lists", "system"),
        ("recurring", "Recurring Observation", "system"),
    ]
    for slug, display, category in tags:
        if not db.query(PropertyTag).filter(PropertyTag.slug == slug).first():
            db.add(PropertyTag(slug=slug, display_name=display, tag_category=category))
    logger.info("Seeded %d property tags", len(tags))
