"""
Parse ScrapingBee AI extraction response for Dignity Memorial obituaries.

The AI returns a JSON array like:
    [
        {
            "name": "Mark Alan Sabo",
            "city": "Pasadena",
            "state": "TX",
            "date_of_birth": "07/06/1958",
            "date_of_death": "03/24/2026",
            "obituary_link": "https://www.dignitymemorial.com/obituaries/pasadena-tx/mark-sabo-12812279"
        },
        ...
    ]

States may be 2-letter abbreviations ("TX") or full names ("Texas") — both are
normalised to 2-letter abbreviations.  Dates are parsed from MM/DD/YYYY.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

logger = logging.getLogger(__name__)

# ── State / province name → 2-letter abbreviation ────────────────────────────
STATE_NAME_TO_ABBR: dict[str, str] = {
    # US states
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID",
    "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE",
    "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ",
    "New Mexico": "NM", "New York": "NY", "North Carolina": "NC",
    "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC",
    "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT",
    "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "District of Columbia": "DC",
    # US territories
    "Puerto Rico": "PR", "Virgin Islands": "VI", "Guam": "GU",
    "American Samoa": "AS", "Northern Mariana Islands": "MP",
    # Canadian provinces / territories
    "Alberta": "AB", "British Columbia": "BC", "Manitoba": "MB",
    "New Brunswick": "NB", "Newfoundland and Labrador": "NL",
    "Northwest Territories": "NT", "Nova Scotia": "NS", "Nunavut": "NU",
    "Ontario": "ON", "Prince Edward Island": "PE", "Quebec": "QC",
    "Saskatchewan": "SK", "Yukon": "YT",
}

_KNOWN_ABBRS: set[str] = set(STATE_NAME_TO_ABBR.values())
_TWO_LETTER_RE = re.compile(r"^[A-Z]{2}$")

_DATE_FORMATS = ["%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y"]


@dataclass
class ObituaryRow:
    full_name: str
    city: Optional[str]
    state: Optional[str]          # 2-letter abbreviation or None
    date_of_birth: Optional[date]
    date_of_death: Optional[date]
    obituary_link: Optional[str]


def parse_response(raw: str) -> tuple[list[ObituaryRow], int]:
    """
    Parse the AI JSON response into ObituaryRow objects.

    Returns (rows, malformed_count).
    A row is malformed if it is missing a usable name.
    """
    rows: list[ObituaryRow] = []
    malformed = 0

    # Strip markdown code fences that ScrapingBee sometimes wraps JSON in.
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        logger.warning("json_parse_failed err=%s snippet=%r", exc, text[:200])
        return [], 0

    if not isinstance(data, list):
        logger.warning("unexpected_response_shape type=%s", type(data).__name__)
        return [], 0

    for entry in data:
        if not isinstance(entry, dict):
            malformed += 1
            logger.debug("non_dict_entry entry=%r", entry)
            continue

        full_name = _norm(entry.get("name") or "")
        if not full_name:
            malformed += 1
            logger.debug("empty_name entry=%r", entry)
            continue

        city = _norm(entry.get("city") or "") or None
        state = _normalize_state(entry.get("state") or "")
        dob = _parse_date(entry.get("date_of_birth") or "")
        dod = _parse_date(entry.get("date_of_death") or "")
        link = _normalize_link(entry.get("obituary_link") or "")

        rows.append(ObituaryRow(
            full_name=full_name,
            city=city,
            state=state,
            date_of_birth=dob,
            date_of_death=dod,
            obituary_link=link,
        ))

    return rows, malformed


# ── Helpers ───────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    return " ".join(s.split())


def _normalize_state(raw: str) -> Optional[str]:
    """Convert a raw state value to a 2-letter abbreviation, or None."""
    if not raw:
        return None
    stripped = raw.strip()

    # Already a 2-letter code?
    candidate = stripped.upper()
    if _TWO_LETTER_RE.match(candidate):
        return candidate  # keep even if not in our known set

    # Full name lookup (exact, then title-case)
    abbr = STATE_NAME_TO_ABBR.get(stripped) or STATE_NAME_TO_ABBR.get(stripped.title())
    if abbr:
        return abbr

    logger.debug("unknown_state raw=%r", raw)
    return None


def _parse_date(raw: str) -> Optional[date]:
    """Parse a date string in MM/DD/YYYY, YYYY-MM-DD, or MM-DD-YYYY format."""
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
    """Trim whitespace; return None for empty or obviously broken URLs."""
    if not raw:
        return None
    link = raw.strip()
    # Accept only http(s) links; some entries have typos like "ttps://..."
    if not link.startswith("http://") and not link.startswith("https://"):
        logger.debug("invalid_obituary_link raw=%r", raw)
        return None
    return link
