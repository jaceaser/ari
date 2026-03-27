# ARI Lead Agent

Automated Zillow lead ingestion pipeline. Scrapes pre-foreclosures, FSBOs, and other
distressed property types across US geographies and stores them in Azure PostgreSQL,
so ARI can serve pre-scraped lead lists instantly instead of hitting Zillow live on
every user request.

## How It Works

```
User asks ARI for leads
       │
       ▼
MCP server queries PostgreSQL (pg_leads.py)
       │
  hit? │ yes → return cached list (~instant)
       │
       │ no  → build Zillow URL → ScrapingBee → parse → return live
```

The lead agent is the background process that keeps PostgreSQL populated so the
"hit" path is the common case.

## Architecture

```
main.py (CLI)
  └── monthly-refresh / on-demand / seed / migrate
        │
        ▼
BatchOrchestrator          fans out: geographies × lead_types
  └── RunOrchestrator      handles one (geo, lead_type) pair
        ├── ScrapeService          ScrapingBee → raw HTML
        ├── ZillowParser           HTML → DataFrame
        ├── NormalizerService      address normalization
        ├── DeduplicationService   canonical_hash dedup
        └── PostgreSQL             upsert properties + observations
```

**Concurrency:** `ThreadPoolExecutor` with `MAX_CONCURRENT_SCRAPES` workers (default 5,
set to 50 for bulk runs). Each worker gets its own DB connection.

**Cache TTL per tier:**
- Tier 1 geographies: 7 days
- Tier 2: 14 days
- Tier 3: 30 days

The `RunOrchestrator` checks `scrape_runs` for a recent completed run before scraping.
If one exists within TTL, it skips.

## Database Schema

Hosted on **Azure Database for PostgreSQL Flexible Server** (`ari-leads-pg.postgres.database.azure.com`),
database `ari_leads`.

| Table | Purpose |
|---|---|
| `geographies` | Counties and cities with Zillow slugs and priority tiers |
| `lead_types` | Scrape types (pre_foreclosure, fsbo, etc.) with refresh intervals |
| `properties` | Canonical property records, one row per unique address |
| `property_observations` | Price/status snapshots per scrape run (time-series) |
| `property_tags` | Tag definitions (maps lead type slugs) |
| `property_tag_map` | Many-to-many: property → tags |
| `scrape_runs` | Full audit log of every scrape run |
| `lead_list_definitions` | Monthly list snapshots per geo+lead_type |
| `lead_list_membership` | Properties in each list snapshot |
| `user_property_map` | Per-user CRM / deal pipeline tracking |
| `user_lead_requests` | Audit of every lead request served to users |

Properties are deduplicated by `canonical_hash` (SHA-256 of normalized address).
Each scrape creates a new `property_observation` row — price history is preserved.

## Lead Types

| Slug | Display Name | Refresh Interval |
|---|---|---|
| `pre_foreclosure` | Pre-Foreclosure | 7 days (weekly) |
| `fsbo` | For Sale By Owner | 14 days |
| `as_is` | As-Is | 14 days |
| `fixer_upper` | Fixer Upper | 30 days |
| `tired_landlord` | Tired Landlord | 30 days |
| `subject_to` | Subject To | 30 days |
| `land` | Land | 30 days |

## Geographies

124 seeded geographies (top US counties by population + major Texas cities).
Each has a `priority_tier` (1 = highest) and a `zillow_slug` used to build the scrape URL.

Add new geographies by editing `seed/geographies.json` and re-running `seed`.

## CLI Commands

```bash
# Run scheduled refresh — all tier-1 geos, all active lead types
python -m app.main monthly-refresh

# Run only specific lead types (for per-cadence scheduling)
python -m app.main monthly-refresh --lead-types pre_foreclosure
python -m app.main monthly-refresh --lead-types fsbo,as_is
python -m app.main monthly-refresh --lead-types land,tired_landlord,fixer_upper,subject_to

# Extend to tier-2 geographies
python -m app.main monthly-refresh --tier 2

# Scrape a single geography on demand
python -m app.main on-demand --geo harris-county-tx --lead-type pre_foreclosure
python -m app.main on-demand --geo los-angeles-ca --lead-type fsbo --force

# Seed reference tables (geographies, lead types, tags)
python -m app.main seed

# Run Alembic migrations
python -m app.main migrate
```

## Environment Variables

```
AZURE_PG_HOST=ari-leads-pg.postgres.database.azure.com
AZURE_PG_DATABASE=ari_leads
AZURE_PG_USERNAME=ariadmin
AZURE_PG_PASSWORD=...
AZURE_PG_PORT=5432

SCRAPINGBEE_API_KEY=...
SCRAPE_MAX_PAGES=5          # Pages per Zillow search result
SCRAPE_TIMEOUT_SECONDS=90

MAX_CONCURRENT_SCRAPES=5    # Use 50 for bulk runs
```

## Scheduling (Not Yet Deployed)

The agent is designed to run as **Azure Container Apps Jobs** — one job per cadence group:

| Job Name | Cron | Command |
|---|---|---|
| `lead-agent-weekly` | `0 6 * * 1` (Mon 6am) | `monthly-refresh --lead-types pre_foreclosure` |
| `lead-agent-biweekly` | `0 6 1,15 * *` (1st & 15th) | `monthly-refresh --lead-types fsbo,as_is` |
| `lead-agent-monthly` | `0 6 1 * *` (1st of month) | `monthly-refresh --lead-types land,tired_landlord,fixer_upper,subject_to` |

Container image: `ariprodacr.azurecr.io/ari-lead-agent:latest`

See deployment docs for provisioning steps.

## Local Development

```bash
cd apps/lead_agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env  # fill in PG + ScrapingBee creds

python -m app.main migrate
python -m app.main seed
python -m app.main on-demand --geo harris-county-tx --lead-type pre_foreclosure
```

## Stats (First Batch Run)

- 807 scrape runs completed
- ~65K properties stored
- 124 geographies × 7 lead types
- Concurrency: 50 workers
- `render_js=false` (ScrapingBee premium proxy, no JS rendering needed for Zillow JSON)
