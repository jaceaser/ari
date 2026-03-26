"""
Zillow HTML parser.

Zillow embeds property data as JSON inside <script> tags.
We extract that JSON, normalize field names, and return List[PropertyRaw].

Cleaned-up port of the legacy lead_gen.py parser with better error handling
and lxml for faster HTML parsing.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from app.models.domain import PropertyRaw

logger = logging.getLogger(__name__)

RESULTS_PER_PAGE = 41

_TOTAL_RESULTS_RE = re.compile(r'"totalResultCount"\s*:\s*(\d+)')
_TOTAL_PAGES_RE = re.compile(r'"totalPages"\s*:\s*(\d+)')


def extract_total_results(html: bytes) -> int:
    """Extract total result count from Zillow HTML. Returns 0 if not found."""
    if not html:
        return 0
    content = html.decode("utf-8", errors="ignore")

    m = _TOTAL_RESULTS_RE.search(content)
    if m:
        return int(m.group(1))

    m = _TOTAL_PAGES_RE.search(content)
    if m:
        return int(m.group(1)) * RESULTS_PER_PAGE

    return 0


def parse_listings(html: bytes) -> list[PropertyRaw]:
    """
    Parse Zillow HTML into a list of PropertyRaw.
    Returns empty list on parse failure — never raises.
    """
    if not html:
        return []

    try:
        soup = BeautifulSoup(html, "lxml")
        for script in soup.find_all("script"):
            text = script.string
            if not text or "listResults" not in text:
                continue

            # Locate the searchResults JSON blob via the listResults key
            idx = text.find('"listResults"')
            if idx == -1:
                continue

            start = text.rfind('"searchResults"', 0, idx)
            if start == -1:
                continue

            try:
                decoder = json.JSONDecoder()
                brace_pos = text.index("{", start + len('"searchResults"') + 1)
                obj, _ = decoder.raw_decode(text, brace_pos)
                listings = obj.get("listResults", [])
                return [_parse_listing(l) for l in listings if _is_valid(l)]
            except (ValueError, KeyError, StopIteration):
                continue

    except Exception as exc:
        logger.error("Zillow parse error: %s", exc)

    return []


def _is_valid(listing: dict) -> bool:
    return bool(listing.get("addressStreet") or listing.get("address"))


def _parse_listing(listing: dict) -> PropertyRaw:
    home_info = listing.get("hdpData", {}).get("homeInfo", {})
    return PropertyRaw(
        source_listing_id=str(listing["zpid"]) if listing.get("zpid") else None,
        address_street=listing.get("addressStreet"),
        address_city=listing.get("addressCity"),
        address_state=listing.get("addressState"),
        address_zip=str(listing["addressZipcode"]) if listing.get("addressZipcode") else None,
        full_address=listing.get("address"),
        beds=_safe_float(listing.get("beds")),
        baths=_safe_float(listing.get("baths")),
        sqft=_safe_int(home_info.get("livingArea")),
        lot_area_value=_safe_float(home_info.get("lotAreaValue")),
        lot_area_unit=home_info.get("lotAreaUnit"),
        price=_parse_price(listing.get("price") or listing.get("unformattedPrice")),
        listing_status=home_info.get("homeStatus"),
        days_on_market=_safe_int(listing.get("daysOnZillow")),
        detail_url=_detail_url(listing.get("detailUrl")),
        latitude=_safe_float(home_info.get("latitude")),
        longitude=_safe_float(home_info.get("longitude")),
        raw_json=json.dumps(listing, default=str),
    )


def _parse_price(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = re.sub(r"[^\d.]", "", val)
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None
    return None


def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _safe_int(val) -> Optional[int]:
    try:
        return int(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _detail_url(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    if path.startswith("http"):
        return path
    return f"https://www.zillow.com{path}"
