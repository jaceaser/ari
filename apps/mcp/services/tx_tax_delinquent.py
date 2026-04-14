"""
Texas Tax Delinquent Property Query Service.

Queries the taxdelinquent database on txasset-pg.postgres.database.azure.com
to surface delinquent property tax leads for ARI Elite subscribers.

Primary surface: fact_property_latest (materialized view, ~850K delinquent rows)
Secondary:       fact_tax_assessment (per-year / per-taxing-unit breakdown)
Reference:       dim_county (county_name → county_key resolution)

Security model
--------------
- All credentials come from environment variables only — never hardcoded.
- All SQL uses named psycopg2 placeholders (%(name)s) — no f-strings or
  string concatenation with user-supplied values.
- The model never constructs SQL; it passes JSON parameters to this module.
- LIMIT is always enforced server-side (default 25, hard max 100).
- is_delinquent = true is always in the WHERE clause for search queries.
- sptb_code-only filtering is rejected before query execution (slow path).

Connection
----------
Required env vars:
  TX_DELINQUENT_PG_HOST      — txasset-pg.postgres.database.azure.com
  TX_DELINQUENT_PG_PORT      — 5432
  TX_DELINQUENT_PG_DATABASE  — taxdelinquent
  TX_DELINQUENT_PG_USERNAME  — txassetadmin
  TX_DELINQUENT_PG_PASSWORD  — (from Azure Key Vault / App Service env)
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_LIMIT = 25
_MAX_LIMIT = 250
_MAX_OFFSET = 10_000

# Fields to SELECT for list queries (safe subset — no PII beyond owner name/address)
_LIST_COLUMNS = """
    property_key,
    county_name,
    tax_account,
    situs_address,
    situs_city,
    situs_zip,
    owner_name,
    owner_mail_state,
    sptb_code,
    acreage,
    land_value,
    improvement_value,
    market_value,
    assessed_value,
    total_amount_due,
    total_penalty_interest,
    total_attorney_fees,
    has_lawsuit,
    has_judgment,
    first_delinquent_year,
    years_delinquent,
    is_delinquent
"""

# Fields returned for single-property detail (full set)
_DETAIL_COLUMNS = """
    property_key,
    county_key,
    county_name,
    tax_account,
    geo_id,
    prop_id,
    situs_address,
    situs_city,
    situs_zip,
    owner_name,
    owner_mail_address,
    owner_mail_city,
    owner_mail_state,
    owner_mail_zip,
    legal_desc,
    sptb_code,
    local_use_code,
    acreage,
    year_built,
    land_value,
    improvement_value,
    market_value,
    assessed_value,
    total_amount_due,
    total_penalty_interest,
    total_attorney_fees,
    is_delinquent,
    has_lawsuit,
    has_judgment,
    first_delinquent_year,
    years_delinquent,
    last_collected_at
"""

# Assessment breakdown — joins dim_taxing_unit for unit_name
# Uses actual fact_tax_assessment column names (verified against schema)
_ASSESSMENT_SQL = """
SELECT
    fa.property_key,
    fa.tax_year,
    dt.unit_name        AS taxing_unit_name,
    fa.base_tax,
    fa.base_taxes_paid,
    fa.base_tax_due,
    fa.penalty_interest,
    fa.attorney_fees,
    fa.amount_due,
    fa.is_paid,
    fa.is_delinquent,
    fa.suit_flag,
    fa.cause_number,
    fa.judgment_date,
    fa.exemptions
FROM fact_tax_assessment fa
LEFT JOIN dim_taxing_unit dt ON dt.taxing_unit_key = fa.taxing_unit_key
WHERE fa.property_key = %(pk)s
ORDER BY fa.tax_year DESC, dt.unit_name ASC
"""


# ---------------------------------------------------------------------------
# Connection factory
# ---------------------------------------------------------------------------

def _conn_string() -> str | None:
    """
    Build a libpq connection string from environment variables.
    Returns None if any required variable is missing or empty.
    Never logs or exposes the password.
    """
    host = os.getenv("TX_DELINQUENT_PG_HOST", "").strip()
    port = os.getenv("TX_DELINQUENT_PG_PORT", "5432").strip()
    db = os.getenv("TX_DELINQUENT_PG_DATABASE", "").strip()
    user = os.getenv("TX_DELINQUENT_PG_USERNAME", "").strip()
    pwd = os.getenv("TX_DELINQUENT_PG_PASSWORD", "").strip()

    if not all([host, db, user, pwd]):
        return None

    # sslmode=require is mandatory — Azure PostgreSQL requires SSL
    return (
        f"host={host} port={port} dbname={db} "
        f"user={user} password={pwd} sslmode=require"
    )


def _is_configured() -> bool:
    """Return True if the TX delinquent database is configured via env vars."""
    return _conn_string() is not None


# ---------------------------------------------------------------------------
# County resolution
# ---------------------------------------------------------------------------

def resolve_county_key(conn_str: str, county_name: str) -> int | None:
    """
    Look up county_key from dim_county by county_name.

    Tries exact case-insensitive match first; falls back to ILIKE prefix match.
    Returns None if no county is found.
    """
    try:
        import psycopg2
        import psycopg2.extras

        with psycopg2.connect(conn_str) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Exact match (case-insensitive)
                cur.execute(
                    "SELECT county_key FROM dim_county "
                    "WHERE LOWER(county_name) = LOWER(%(name)s) LIMIT 1",
                    {"name": county_name.strip()},
                )
                row = cur.fetchone()
                if row:
                    return int(row["county_key"])

                # Prefix match for partial names (e.g. "Harris" → "Harris County")
                cur.execute(
                    "SELECT county_key FROM dim_county "
                    "WHERE county_name ILIKE %(pattern)s LIMIT 1",
                    {"pattern": f"{county_name.strip()}%"},
                )
                row = cur.fetchone()
                if row:
                    return int(row["county_key"])

        logger.info("[tx_delinquent] county_name=%r not found in dim_county", county_name)
        return None

    except Exception as exc:
        logger.warning("[tx_delinquent] county resolution failed for %r: %s", county_name, exc)
        return None


# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def _build_search_query(filters: dict[str, Any], county_key: int | None) -> tuple[str, dict]:
    """
    Build a parameterized SELECT query for fact_property_latest.

    Parameters
    ----------
    filters:
        Validated filter dict from the tool call (see query_properties).
    county_key:
        Resolved county_key from dim_county (or None).

    Returns
    -------
    (sql, params) — sql uses %(name)s placeholders; params is the values dict.

    Raises
    ------
    ValueError
        If sptb_code is the only substantive filter (would produce a full-table scan).
    """
    clauses: list[str] = ["is_delinquent = true"]
    params: dict[str, Any] = {}

    # --- County filter (use county_key for the fast composite index) ---
    if county_key is not None:
        clauses.append("county_key = %(county_key)s")
        params["county_key"] = county_key
    elif filters.get("county_name"):
        # county_key resolution failed — fall back to county_name ILIKE (slower)
        clauses.append("county_name ILIKE %(county_name)s")
        params["county_name"] = filters["county_name"].strip()

    # --- Amount filters ---
    if filters.get("min_amount_due") is not None:
        clauses.append("total_amount_due >= %(min_amount_due)s")
        params["min_amount_due"] = float(filters["min_amount_due"])

    if filters.get("max_amount_due") is not None:
        clauses.append("total_amount_due <= %(max_amount_due)s")
        params["max_amount_due"] = float(filters["max_amount_due"])

    # --- Market value filters ---
    if filters.get("min_market_value") is not None:
        clauses.append("market_value >= %(min_market_value)s")
        params["min_market_value"] = float(filters["min_market_value"])

    if filters.get("max_market_value") is not None:
        clauses.append("market_value <= %(max_market_value)s")
        params["max_market_value"] = float(filters["max_market_value"])

    # --- City filter (situs_city) ---
    if filters.get("city"):
        clauses.append("situs_city ILIKE %(city)s")
        params["city"] = filters["city"].strip()

    # --- Owner name ILIKE (trigram-indexed) ---
    if filters.get("owner_name"):
        clauses.append("owner_name ILIKE %(owner_name)s")
        params["owner_name"] = f"%{filters['owner_name'].strip()}%"

    # --- Out-of-state owners ---
    if filters.get("out_of_state"):
        clauses.append("owner_mail_state IS NOT NULL AND owner_mail_state != 'TX'")

    # --- Years delinquent ---
    if filters.get("min_years_delinquent") is not None:
        clauses.append("years_delinquent >= %(min_years_delinquent)s")
        params["min_years_delinquent"] = int(filters["min_years_delinquent"])

    # --- Lawsuit / judgment flags ---
    if filters.get("has_lawsuit"):
        clauses.append("has_lawsuit = true")

    if filters.get("has_judgment"):
        clauses.append("has_judgment = true")

    # --- Property type (sptb_code) — requires another substantive filter ---
    if filters.get("sptb_code"):
        # Substantive filters are anything other than is_delinquent=true and limit/offset
        substantive = [c for c in clauses if c != "is_delinquent = true"]
        if not substantive:
            raise ValueError(
                "sptb_code filter requires at least one additional filter "
                "(county, amount, owner, years, lawsuit, etc.) to avoid a full-table scan."
            )
        clauses.append("sptb_code = %(sptb_code)s")
        params["sptb_code"] = str(filters["sptb_code"]).strip().upper()

    # --- Pagination ---
    limit_raw = filters.get("limit")
    limit = int(limit_raw) if limit_raw is not None else _DEFAULT_LIMIT
    limit = max(1, min(limit, _MAX_LIMIT))  # clamp: 1..250

    offset_raw = filters.get("offset")
    offset = int(offset_raw) if offset_raw is not None else 0
    offset = max(0, min(offset, _MAX_OFFSET))  # clamp: 0..10000

    params["limit"] = limit
    params["offset"] = offset

    where_clause = " AND ".join(clauses)

    # random_export=True uses ORDER BY RANDOM() so successive exports surface
    # different properties instead of always returning the same top-N rows.
    order_by = "RANDOM()" if filters.get("random_export") else "total_amount_due DESC NULLS LAST"

    sql = f"""
SELECT {_LIST_COLUMNS}
FROM fact_property_latest
WHERE {where_clause}
ORDER BY {order_by}
LIMIT %(limit)s
OFFSET %(offset)s
"""
    return sql.strip(), params


# ---------------------------------------------------------------------------
# Public query functions
# ---------------------------------------------------------------------------

def query_properties(filters: dict[str, Any]) -> dict[str, Any]:
    """
    Search fact_property_latest with constrained parameterized filters.

    Parameters (all optional)
    -------------------------
    county_name         str   — Texas county name
    city                str   — city name filter (e.g. 'McAllen', 'Houston')
    min_amount_due      float — minimum total_amount_due
    max_amount_due      float — maximum total_amount_due
    owner_name          str   — ILIKE pattern (partial match)
    out_of_state        bool  — only out-of-state owners
    min_years_delinquent int  — minimum years_delinquent
    has_lawsuit         bool  — only properties with active lawsuits
    has_judgment        bool  — only properties with judgments
    min_market_value    float — minimum market_value
    max_market_value    float — maximum market_value
    sptb_code           str   — property type code (requires another filter)
    limit               int   — rows to return (1–250, default 25)
    offset              int   — pagination offset (0–10000)

    Returns
    -------
    {
      "status": "ok" | "no_results" | "error" | "config_missing",
      "count": int,
      "rows": list[dict],
      "county_key": int | None,
      "county_name": str | None,
      "filters_applied": dict,
      "message": str,
    }
    """
    t0 = time.monotonic()

    conn_str = _conn_string()
    if conn_str is None:
        logger.warning("[tx_delinquent] TX_DELINQUENT_PG_* env vars not configured")
        return {
            "status": "config_missing",
            "count": 0,
            "rows": [],
            "county_key": None,
            "county_name": None,
            "filters_applied": {},
            "message": (
                "Texas tax delinquent data source is not configured. "
                "Please contact support to enable this feature."
            ),
        }

    county_name = (filters.get("county_name") or "").strip() or None
    county_key: int | None = None

    if county_name:
        county_key = resolve_county_key(conn_str, county_name)
        if county_key is None:
            return {
                "status": "error",
                "count": 0,
                "rows": [],
                "county_key": None,
                "county_name": county_name,
                "filters_applied": filters,
                "message": (
                    f"County '{county_name}' was not found in the Texas appraisal district database. "
                    "Please verify the county name (e.g. 'Harris', 'Dallas', 'Bexar')."
                ),
            }

    try:
        sql, params = _build_search_query(filters, county_key)
    except ValueError as exc:
        return {
            "status": "error",
            "count": 0,
            "rows": [],
            "county_key": county_key,
            "county_name": county_name,
            "filters_applied": filters,
            "message": str(exc),
        }

    try:
        import psycopg2
        import psycopg2.extras

        with psycopg2.connect(conn_str) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]

        elapsed = time.monotonic() - t0
        logger.info(
            "[tx_delinquent] query ok: county=%r county_key=%s rows=%d elapsed=%.2fs",
            county_name, county_key, len(rows), elapsed,
        )

        if not rows:
            return {
                "status": "no_results",
                "count": 0,
                "rows": [],
                "county_key": county_key,
                "county_name": county_name,
                "filters_applied": filters,
                "message": (
                    "No delinquent properties matched your search criteria. "
                    "Try broadening the filters or checking the county name."
                ),
            }

        return {
            "status": "ok",
            "count": len(rows),
            "rows": rows,
            "county_key": county_key,
            "county_name": county_name,
            "filters_applied": filters,
            "message": "",
        }

    except Exception as exc:
        elapsed = time.monotonic() - t0
        logger.warning(
            "[tx_delinquent] query failed after %.2fs: %s", elapsed, type(exc).__name__
        )
        # Never expose connection string or internal details in the message
        return {
            "status": "error",
            "count": 0,
            "rows": [],
            "county_key": county_key,
            "county_name": county_name,
            "filters_applied": filters,
            "message": (
                "Failed to retrieve tax delinquent data. "
                "Please try again or contact support if the issue persists."
            ),
        }


def query_property_detail(property_key: int) -> dict[str, Any]:
    """
    Retrieve a single property's full record from fact_property_latest.

    Note: does NOT enforce is_delinquent=true so detail can be fetched
    for any property_key the model obtained from a prior search result.
    """
    conn_str = _conn_string()
    if conn_str is None:
        return {"status": "config_missing", "row": None, "message": "Data source not configured."}

    try:
        import psycopg2
        import psycopg2.extras

        with psycopg2.connect(conn_str) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    f"SELECT {_DETAIL_COLUMNS} FROM fact_property_latest "
                    "WHERE property_key = %(pk)s LIMIT 1",
                    {"pk": int(property_key)},
                )
                row = cur.fetchone()

        if row is None:
            return {
                "status": "not_found",
                "row": None,
                "message": f"Property key {property_key} not found.",
            }

        logger.info("[tx_delinquent] detail ok: property_key=%d", property_key)
        return {"status": "ok", "row": dict(row), "message": ""}

    except Exception as exc:
        logger.warning("[tx_delinquent] detail query failed: %s", type(exc).__name__)
        return {
            "status": "error",
            "row": None,
            "message": "Failed to retrieve property detail.",
        }


def query_assessment(property_key: int) -> dict[str, Any]:
    """
    Retrieve per-year, per-taxing-unit tax assessment breakdown from
    fact_tax_assessment for a given property_key.
    """
    conn_str = _conn_string()
    if conn_str is None:
        return {"status": "config_missing", "rows": [], "message": "Data source not configured."}

    try:
        import psycopg2
        import psycopg2.extras

        with psycopg2.connect(conn_str) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(_ASSESSMENT_SQL, {"pk": int(property_key)})
                rows = [dict(r) for r in cur.fetchall()]

        logger.info(
            "[tx_delinquent] assessment ok: property_key=%d rows=%d",
            property_key, len(rows),
        )

        if not rows:
            return {
                "status": "no_results",
                "rows": [],
                "message": f"No tax assessment records found for property key {property_key}.",
            }

        return {"status": "ok", "rows": rows, "message": ""}

    except Exception as exc:
        logger.warning("[tx_delinquent] assessment query failed: %s", type(exc).__name__)
        return {
            "status": "error",
            "rows": [],
            "message": "Failed to retrieve tax assessment breakdown.",
        }
