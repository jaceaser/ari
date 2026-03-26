"""
Deterministic Zillow URL generator.

URL templates are seeded into the lead_types DB table on first run.
The %%GEO_SLUG%% placeholder is replaced with the geography's zillow_slug.
No LLM involvement — pure, testable, version-controlled logic.

This replaces the AZURE_OPENAI_LEAD_LINK_MESSAGE system prompt entirely.
"""
from __future__ import annotations

import json
import urllib.parse

from app.models.domain import LeadTypeSlug

# Source of truth for URL templates. Seeded into the lead_types table via seed_job.
# Keys match LeadTypeSlug values exactly.
LEAD_TYPE_TEMPLATES: dict[str, dict] = {
    LeadTypeSlug.FSBO: {
        "display_name": "For Sale By Owner",
        "refresh_interval_days": 14,
        "url_template": (
            "https://www.zillow.com/%%GEO_SLUG%%/?searchQueryState="
            + urllib.parse.quote(
                json.dumps({
                    "pagination": {},
                    "filterState": {
                        "fsbo": {"value": True},
                        "fsba": {"value": False},
                        "price": {"min": None},
                        "mp": {"min": None},
                        "tow": {"value": False},
                        "con": {"value": False},
                        "apa": {"value": False},
                        "apco": {"value": False},
                        "sort": {"value": "globalrelevanceex"},
                        "mf": {"value": False},
                        "land": {"value": False},
                        "manu": {"value": False},
                        "auc": {"value": False},
                        "fore": {"value": False},
                        "nc": {"value": False},
                        "cmsn": {"value": False},
                        "doz": {"value": "36m"},
                    },
                    "isListVisible": True,
                    "category": "cat2",
                }),
                safe="",
            )
        ),
    },
    LeadTypeSlug.AS_IS: {
        "display_name": "Agent As-Is",
        "refresh_interval_days": 14,
        "url_template": (
            "https://www.zillow.com/%%GEO_SLUG%%/?searchQueryState="
            + urllib.parse.quote(
                json.dumps({
                    "pagination": {},
                    "filterState": {
                        "sort": {"value": "globalrelevanceex"},
                        "price": {"min": None, "max": None},
                        "doz": {"value": "36m"},
                        "att": {"value": "as is"},
                    },
                    "isListVisible": True,
                    "category": "cat1",
                }),
                safe="",
            )
        ),
    },
    LeadTypeSlug.PRE_FORECLOSURE: {
        "display_name": "Pre-Foreclosure / Auctions",
        "refresh_interval_days": 7,
        "url_template": (
            "https://www.zillow.com/%%GEO_SLUG%%/?searchQueryState="
            + urllib.parse.quote(
                json.dumps({
                    "pagination": {},
                    "filterState": {
                        "price": {"min": None},
                        "mp": {"min": None},
                        "tow": {"value": False},
                        "con": {"value": False},
                        "apa": {"value": False},
                        "apco": {"value": False},
                        "sort": {"value": "globalrelevanceex"},
                        "nc": {"value": False},
                        "cmsn": {"value": False},
                        "mf": {"value": False},
                        "land": {"value": False},
                        "manu": {"value": False},
                        "doz": {"value": "30"},
                        "fsba": {"value": False},
                        "fsbo": {"value": False},
                        "fore": {"value": False},
                        "pf": {"value": True},
                    },
                    "isListVisible": True,
                    "category": "cat2",
                }),
                safe="",
            )
        ),
    },
    LeadTypeSlug.LAND: {
        "display_name": "Land",
        "refresh_interval_days": 30,
        "url_template": (
            "https://www.zillow.com/%%GEO_SLUG%%/?searchQueryState="
            + urllib.parse.quote(
                json.dumps({
                    "pagination": {},
                    "filterState": {
                        "sort": {"value": "globalrelevanceex"},
                        "doz": {"value": "90"},
                        "nc": {"value": False},
                        "fore": {"value": False},
                        "auc": {"value": False},
                        "cmsn": {"value": False},
                        "sf": {"value": False},
                        "tow": {"value": False},
                        "mf": {"value": False},
                        "con": {"value": False},
                        "apa": {"value": False},
                        "manu": {"value": False},
                        "apco": {"value": False},
                        "lot": {"min": 21780, "max": 4356000},
                    },
                    "isListVisible": True,
                    "category": "cat1",
                }),
                safe="",
            )
        ),
    },
    LeadTypeSlug.TIRED_LANDLORD: {
        "display_name": "Tired Landlords",
        "refresh_interval_days": 30,
        "url_template": (
            "https://www.zillow.com/%%GEO_SLUG%%/rentals/?searchQueryState="
            + urllib.parse.quote(
                json.dumps({
                    "pagination": {},
                    "filterState": {
                        "fr": {"value": True},
                        "fsba": {"value": False},
                        "fsbo": {"value": False},
                        "nc": {"value": False},
                        "cmsn": {"value": False},
                        "auc": {"value": False},
                        "fore": {"value": False},
                        "price": {"max": 626745},
                        "mp": {"max": 3000},
                        "ah": {"value": True},
                        "doz": {"value": "36m"},
                        "att": {"value": ""},
                        "apco": {"value": False},
                        "tow": {"value": False},
                        "apa": {"value": False},
                        "con": {"value": False},
                    },
                    "isListVisible": True,
                }),
                safe="",
            )
        ),
    },
    LeadTypeSlug.FIXER_UPPER: {
        "display_name": "Fixer Upper / Wholesale",
        "refresh_interval_days": 30,
        "url_template": (
            "https://www.zillow.com/%%GEO_SLUG%%/fixer-upper_att/?searchQueryState="
            + urllib.parse.quote(
                json.dumps({
                    "pagination": {},
                    "filterState": {
                        "sort": {"value": "globalrelevanceex"},
                        "price": {"min": None, "max": 650000},
                        "doz": {"value": "90"},
                        "att": {"value": "fixer upper"},
                    },
                    "isListVisible": True,
                    "category": "cat1",
                }),
                safe="",
            )
        ),
    },
    LeadTypeSlug.SUBJECT_TO: {
        "display_name": "Subject To / SubTo / Sub2",
        "refresh_interval_days": 30,
        "url_template": (
            "https://www.zillow.com/%%GEO_SLUG%%/?searchQueryState="
            + urllib.parse.quote(
                json.dumps({
                    "pagination": {},
                    "filterState": {
                        "price": {"min": 50000, "max": 650000},
                        "mp": {"min": 258, "max": 3359},
                        "tow": {"value": False},
                        "con": {"value": False},
                        "apa": {"value": False},
                        "apco": {"value": False},
                        "sort": {"value": "globalrelevanceex"},
                        "nc": {"value": False},
                        "fore": {"value": False},
                        "auc": {"value": False},
                        "cmsn": {"value": False},
                        "mf": {"value": False},
                        "land": {"value": False},
                        "manu": {"value": False},
                        "doz": {"value": "6m"},
                        "built": {"min": 2015},
                        "ac": {"value": True},
                    },
                    "category": "cat1",
                    "isListVisible": True,
                }),
                safe="",
            )
        ),
    },
}


def generate_url(geo_slug: str, url_template: str) -> str:
    """Replace %%GEO_SLUG%% placeholder with the geography's Zillow slug."""
    return url_template.replace("%%GEO_SLUG%%", geo_slug)


def build_paginated_url(base_url: str, page: int) -> str:
    """Insert pagination into an existing Zillow URL for pages > 1.

    Zillow expects two changes for page N:
      1. Path suffix: /harris-county-tx/  →  /harris-county-tx/2_p/
      2. searchQueryState JSON: "pagination":{} → "pagination":{"currentPage":N}
    """
    if page == 1:
        return base_url

    parsed = urllib.parse.urlparse(base_url)
    qs = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

    # Patch the searchQueryState JSON
    sqs_raw = qs.get("searchQueryState", ["{}"])[0]
    sqs = json.loads(sqs_raw)
    sqs["pagination"] = {"currentPage": page}
    qs["searchQueryState"] = [json.dumps(sqs, separators=(",", ":"))]

    # Add /{page}_p/ suffix to path (strip trailing slash first)
    new_path = parsed.path.rstrip("/") + f"/{page}_p/"

    new_url = urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        new_path,
        parsed.params,
        urllib.parse.urlencode(qs, doseq=True),
        parsed.fragment,
    ))
    return new_url
