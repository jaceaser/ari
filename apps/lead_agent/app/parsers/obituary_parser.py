"""
Parse Dignity Memorial obituary API response records.

The API returns structured JSON — no AI extraction needed.

Each record contains:
  displayName   – full name
  birthDate     – "MM/DD/YYYY" (may be null/empty)
  deathDate     – "MM/DD/YYYY" (may be null/empty)
  link          – "https://www.dignitymemorial.com/obituaries/{city-slug}-{state}/{name-id}"

City and state are parsed from the link slug.  Example:
  "obituaries/north-little-rock-ar/…" → city="North Little Rock", state="AR"
  "obituaries/el-paso-tx/…"           → city="El Paso",            state="TX"
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"]

# Known 2-letter state/province codes we want to keep.
# Any 2-letter code not in this set is stored as-is (best-effort).
_KNOWN_CODES: set[str] = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC","PR","VI","GU","AS","MP",
    # Canadian provinces
    "AB","BC","MB","NB","NL","NT","NS","NU","ON","PE","QC","SK","YT",
}


@dataclass
class ObituaryRow:
    full_name: str
    city: Optional[str]
    state: Optional[str]          # 2-letter abbreviation or None
    date_of_birth: Optional[date]
    date_of_death: Optional[date]
    obituary_link: Optional[str]


def parse_records(records: list[dict]) -> tuple[list[ObituaryRow], int]:
    """
    Convert raw API result dicts into ObituaryRow objects.

    Returns (rows, malformed_count).
    A record is malformed if it has no usable displayName.
    """
    rows: list[ObituaryRow] = []
    malformed = 0

    for rec in records:
        name = _norm(rec.get("displayName") or "")
        if not name:
            malformed += 1
            logger.debug("empty_name rec=%r", rec)
            continue

        link = _normalize_link(rec.get("link") or "")
        city, state = _parse_city_state(link)

        rows.append(ObituaryRow(
            full_name=name,
            city=city,
            state=state,
            date_of_birth=_parse_date(rec.get("birthDate") or ""),
            date_of_death=_parse_date(rec.get("deathDate") or ""),
            obituary_link=link,
        ))

    return rows, malformed


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return " ".join(s.split())


def _parse_date(raw: str) -> Optional[date]:
    if not raw:
        return None
    s = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    logger.debug("unparseable_date raw=%r", raw)
    return None


def _normalize_link(raw: str) -> Optional[str]:
    if not raw:
        return None
    link = raw.strip()
    if not link.startswith("http://") and not link.startswith("https://"):
        return None
    return link


def _parse_city_state(link: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Extract city and state from a Dignity Memorial obituary URL.

    URL path: /obituaries/{city-slug}-{state-abbr}/{name-id}
    Examples:
      /obituaries/north-little-rock-ar/…  → ("North Little Rock", "AR")
      /obituaries/el-paso-tx/…            → ("El Paso", "TX")
      /obituaries/fairfax-va/…            → ("Fairfax", "VA")
      /obituaries/surrey-bc/…             → ("Surrey", "BC")
    """
    if not link:
        return None, None
    try:
        path = urlparse(link).path         # e.g. /obituaries/fairfax-va/wilma-jenkins-12811783
        parts = [p for p in path.split("/") if p]
        if len(parts) < 2:
            return None, None
        city_state_slug = parts[1]         # e.g. "fairfax-va" or "north-little-rock-ar"
        # State is always the last 2 characters
        state_raw = city_state_slug[-2:].upper()
        state = state_raw if state_raw in _KNOWN_CODES else state_raw
        # City is everything before "-{state}"
        city_slug = city_state_slug[:-3]   # strip "-XX"
        city = city_slug.replace("-", " ").title() if city_slug else None
        return city or None, state or None
    except Exception as exc:
        logger.debug("city_state_parse_error link=%r err=%s", link, exc)
        return None, None
