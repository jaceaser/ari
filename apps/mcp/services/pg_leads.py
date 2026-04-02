"""
PostgreSQL lead query service.

Queries the lead_agent database (same Azure PostgreSQL) to serve
pre-scraped properties by city / state / lead_type without hitting
Zillow / ScrapingBee for every request.

Falls back gracefully (returns empty DataFrame) when:
- PG env vars are not configured
- psycopg2 is not installed
- The query returns no rows
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Maps MCP hyphenated lead-type slugs → DB underscore tag slugs
_MCP_TO_DB_SLUG: dict[str, str] = {
    "pre-foreclosure": "pre_foreclosure",
    "fixer-upper": "fixer_upper",
    "as-is": "as_is",
    "tired-landlords": "tired_landlord",
    "subject-to": "subject_to",
    "fsbo": "fsbo",
    "land": "land",
    "reo": "reo",
    "agent-owned": "agent_owned",
    "high-equity": "high_equity",
}

# Columns match the shape expected by the rest of tool_leads / AzureBlobService
_SQL = """
SELECT
    p.address_line1                                                    AS "Address",
    p.address_city                                                     AS "City",
    p.address_state                                                    AS "State",
    p.address_zip                                                      AS "Zip",
    p.beds                                                             AS "Beds",
    p.baths                                                            AS "Bathrooms",
    p.lot_area_value                                                   AS "Lot Size",
    p.lot_area_unit                                                    AS "Lot Unit",
    po.price                                                           AS "Asking Price",
    CONCAT(p.address_line1, ', ', p.address_city, ', ',
           p.address_state, ' ', COALESCE(p.address_zip, ''))          AS "Full Address",
    po.zillow_url                                                      AS "Property URL"
FROM  properties p
JOIN  property_tag_map ptm ON p.id       = ptm.property_id
JOIN  property_tags    pt  ON ptm.tag_id = pt.id
LEFT JOIN geographies  g   ON p.geography_id = g.id
LEFT JOIN LATERAL (
    SELECT price, zillow_url
    FROM   property_observations
    WHERE  property_id = p.id
    ORDER  BY observed_at DESC
    LIMIT  1
) po ON true
WHERE (
    p.address_city ILIKE %(city)s
    OR g.name      ILIKE %(city)s
)
  AND p.address_state = %(state)s
  AND pt.slug         = %(tag_slug)s
ORDER BY po.price ASC NULLS LAST
LIMIT 500
"""


def _conn_string() -> Optional[str]:
    host = os.getenv("AZURE_PG_HOST", "").strip()
    db   = os.getenv("AZURE_PG_DATABASE", "").strip()
    user = os.getenv("AZURE_PG_USERNAME", "").strip()
    pwd  = os.getenv("AZURE_PG_PASSWORD", "").strip()
    port = os.getenv("AZURE_PG_PORT", "5432").strip()
    if not all([host, db, user, pwd]):
        return None
    return f"host={host} port={port} dbname={db} user={user} password={pwd} sslmode=require"


def query_properties(city: str, state: str, mcp_lead_type: str) -> pd.DataFrame:
    """
    Query pre-scraped properties from PostgreSQL by city / state / lead_type.

    Returns a DataFrame with the same column shape as the live-scrape path
    (Address, City, State, Zip, Beds, Bathrooms, Lot Size, Lot Unit,
    Asking Price, Full Address, Property URL), or an empty DataFrame on
    any error / no results.
    """
    db_slug = _MCP_TO_DB_SLUG.get(mcp_lead_type)
    if not db_slug:
        logger.debug("No DB slug mapping for lead_type=%r; skipping DB lookup", mcp_lead_type)
        return pd.DataFrame()

    conn_str = _conn_string()
    if not conn_str:
        logger.debug("PG env vars not configured; skipping DB lookup")
        return pd.DataFrame()

    try:
        import psycopg2
        import psycopg2.extras

        with psycopg2.connect(conn_str) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(_SQL, {
                    "city": city,
                    "state": state.upper(),
                    "tag_slug": db_slug,
                })
                rows = cur.fetchall()

        if not rows:
            logger.info(
                "[pg_leads] no results: city=%r state=%r lead_type=%r",
                city, state, mcp_lead_type,
            )
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        logger.info(
            "[pg_leads] %d properties: city=%r state=%r lead_type=%r",
            len(df), city, state, mcp_lead_type,
        )
        return df

    except Exception as exc:
        logger.warning("[pg_leads] query failed (falling back to scrape): %s", exc)
        return pd.DataFrame()
