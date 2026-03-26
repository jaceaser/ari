"""
Address normalization for canonical property identity.

Ensures "123 Main St" and "123 Main Street" produce the same canonical_hash,
so the properties table stays deduplicated across scrape runs.
"""
from __future__ import annotations

import hashlib
import re
from typing import Optional

# Applied in order — longer patterns before shorter to avoid partial substitution.
_ABBREVS: list[tuple[re.Pattern, str]] = [
    # Street types
    (re.compile(r"\bblvd\b"), "boulevard"),
    (re.compile(r"\bpkwy\b"), "parkway"),
    (re.compile(r"\bhwy\b"), "highway"),
    (re.compile(r"\bfwy\b"), "freeway"),
    (re.compile(r"\bave?\b"), "avenue"),
    (re.compile(r"\bstr?\b"), "street"),
    (re.compile(r"\brd\b"), "road"),
    (re.compile(r"\bdr\b"), "drive"),
    (re.compile(r"\bln\b"), "lane"),
    (re.compile(r"\bct\b"), "court"),
    (re.compile(r"\bpl\b"), "place"),
    (re.compile(r"\bcir\b"), "circle"),
    (re.compile(r"\btr?l\b"), "trail"),
    (re.compile(r"\bsq\b"), "square"),
    # Directionals
    (re.compile(r"\bnorth\b"), "north"),  # already expanded, keep
    (re.compile(r"\bsouth\b"), "south"),
    (re.compile(r"\beast\b"), "east"),
    (re.compile(r"\bwest\b"), "west"),
    (re.compile(r"\bne\b"), "northeast"),
    (re.compile(r"\bnw\b"), "northwest"),
    (re.compile(r"\bse\b"), "southeast"),
    (re.compile(r"\bsw\b"), "southwest"),
    (re.compile(r"\bn\b"), "north"),
    (re.compile(r"\bs\b"), "south"),
    (re.compile(r"\be\b"), "east"),
    (re.compile(r"\bw\b"), "west"),
    # Strip unit designators entirely
    (re.compile(r"\b(apt|unit|ste|suite|#)\s*[\w-]+"), ""),
]


def normalize_address_line1(raw: str) -> str:
    """Lowercase, strip punctuation, expand abbreviations. Used only for hashing."""
    val = raw.lower().strip()
    val = re.sub(r"[^\w\s]", " ", val)
    val = re.sub(r"\s+", " ", val)
    for pattern, replacement in _ABBREVS:
        val = pattern.sub(replacement, val)
    return re.sub(r"\s+", " ", val).strip()


def normalize_city(raw: str) -> str:
    return raw.lower().strip()


def normalize_state(raw: str) -> str:
    return raw.upper().strip()[:2]


def normalize_zip(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    return digits[:5] if len(digits) >= 5 else None


def compute_canonical_hash(
    address_line1: str,
    city: str,
    state: str,
    zip5: Optional[str],
) -> str:
    """
    SHA-256 of pipe-delimited normalized address components.
    Primary deduplication key for the properties table.
    """
    parts = [
        normalize_address_line1(address_line1),
        normalize_city(city),
        normalize_state(state),
        normalize_zip(zip5) or "",
    ]
    fingerprint = "|".join(parts)
    return hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()


def normalize_property_raw(raw: "PropertyRaw") -> Optional["NormalizedProperty"]:  # noqa: F821
    """
    Convert a PropertyRaw into a NormalizedProperty ready for dedup.
    Returns None if we cannot construct a valid address from the raw data.
    """
    from app.models.domain import NormalizedProperty, PropertyRaw

    street = (raw.address_street or "").strip()
    city = (raw.address_city or "").strip()
    state = (raw.address_state or "").strip()
    zip_raw = raw.address_zip

    # Fall back to full_address parsing if individual fields are missing
    if (not street or not city or not state) and raw.full_address:
        parts = [p.strip() for p in raw.full_address.split(",")]
        if len(parts) >= 3:
            street = street or parts[0]
            city = city or parts[1]
            state_zip = parts[2].strip().split()
            state = state or (state_zip[0] if state_zip else "")
            zip_raw = zip_raw or (state_zip[1] if len(state_zip) > 1 else None)

    if not street or not city or not state:
        return None

    norm_zip = normalize_zip(zip_raw)
    canonical_hash = compute_canonical_hash(street, city, state, norm_zip)

    return NormalizedProperty(
        address_line1=street.title(),
        address_city=city.title(),
        address_state=normalize_state(state),
        address_zip=norm_zip,
        canonical_hash=canonical_hash,
        zillow_zpid=raw.source_listing_id,
        latitude=raw.latitude,
        longitude=raw.longitude,
        beds=raw.beds,
        baths=raw.baths,
        sqft=raw.sqft,
        lot_area_value=raw.lot_area_value,
        lot_area_unit=raw.lot_area_unit,
        price=raw.price,
        listing_status=raw.listing_status,
        days_on_market=raw.days_on_market,
        detail_url=raw.detail_url,
        raw_json=raw.raw_json,
    )
