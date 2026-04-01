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

## Scheduling

Runs as **Azure Container Apps Jobs** in `rg-ari-prod` / `cae-ari-prod`:

| Job Name | Cron | Command |
|---|---|---|
| `lead-agent-weekly` | `0 6 * * 1` (Mon 6am UTC) | `monthly-refresh --lead-types pre_foreclosure` |
| `lead-agent-biweekly` | `0 6 1,15 * *` (1st & 15th 6am UTC) | `monthly-refresh --lead-types fsbo,as_is` |
| `lead-agent-monthly` | `0 6 1 * *` (1st of month 6am UTC) | `monthly-refresh --lead-types land,tired_landlord,fixer_upper,subject_to` |
| `lead-agent-obituary-sync` | `0 6 * * *` (daily 6am UTC) | `sync-recent-obituaries --overlap-days 7` |

Container image: `ariprodacr.azurecr.io/ari-lead-agent:latest`

To trigger a job manually:
```bash
az containerapp job start -n lead-agent-weekly -g rg-ari-prod
```

To view execution history:
```bash
az containerapp job execution list -n lead-agent-weekly -g rg-ari-prod -o table
```

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

## Obituary Ingestion Pipeline

Scrapes obituary listings from **Dignity Memorial** via ScrapingBee AI extraction and stores
them in PostgreSQL. Two modes: a one-time 365-day backfill and a recurring daily sync.

### How It Works

```
Dignity Memorial listing page (pageNo=1, 2, …)
        │
        ▼
ScrapingBee AI extraction → JSON array (name, city, state, dob, dod, link)
        │
        ▼
obituary_parser.py  (normalize state, parse dates, validate links)
        │
        ▼
PostgreSQL `obituaries` table  (INSERT … ON CONFLICT DO NOTHING)
```

### Database Tables

| Table | Purpose |
|---|---|
| `obituaries` | One row per person — name, city, state, DOB, DOD, obituary link |
| `obituary_backfill_state` | Checkpoint: last completed page per date-filter so the backfill can resume |

**Deduplication (two layers):**
1. `uq_obituary_link` — partial unique index on `obituary_link` (primary key per person)
2. `uq_obituary` — composite constraint on `(full_name, city, state, source_site, source_url)`

### Run the Migration

```bash
cd apps/lead_agent
python -m app.main migrate
# verify: alembic current  →  f2d9e5b3c108 (head)
```

### One-Time Initial Backfill (365 days, ~234k obituaries)

```bash
python -m app.main backfill-obituaries
```

- Defaults: 365-day filter, **25 concurrent workers**, 500–2000 ms jitter per worker
- Checkpoint is written after every 25-page batch — safe to interrupt and resume
- Logs every page: `page_done page=N rows_parsed=50 inserted=50 deduped=0`
- Stops automatically when a page returns 0 rows

**Resume after interruption** (automatic — just re-run the same command):
```bash
python -m app.main backfill-obituaries
# resumes from last checkpoint
```

**Force restart from page 1:**
```bash
python -m app.main backfill-obituaries --no-resume
```

**Resume from a specific page:**
```bash
python -m app.main backfill-obituaries --start-page 300
```

### Daily Sync

```bash
# Standard daily (last 1 day)
python -m app.main sync-recent-obituaries

# 3-day overlap to catch delayed postings
python -m app.main sync-recent-obituaries --overlap-days 3
```

Safe to run more than once — duplicates are silently ignored.

**Suggested cron:**
```
0 6 * * * cd /app && python -m app.main sync-recent-obituaries --overlap-days 3
```

### Tuning Concurrency

| Setting | Default | Env var |
|---|---|---|
| Backfill workers | **25** | `OBITUARY_BACKFILL_CONCURRENCY` |
| Daily sync workers | 5 | `OBITUARY_CONCURRENCY` |
| Request delay (jitter) | 500–2000 ms | `OBITUARY_REQUEST_DELAY_MS_MIN` / `MAX` |

Watch for `scrapingbee_rate_limited` in the logs. If you see it repeatedly, reduce concurrency:
```bash
OBITUARY_BACKFILL_CONCURRENCY=10 python -m app.main backfill-obituaries
```

Do not exceed 50 workers (ScrapingBee plan limit).

### Environment Variables (Obituary)

```
OBITUARY_BACKFILL_CONCURRENCY=25   # workers for the 365-day backfill
OBITUARY_CONCURRENCY=5             # workers for the daily sync
OBITUARY_REQUEST_DELAY_MS_MIN=500  # min jitter delay per worker (ms)
OBITUARY_REQUEST_DELAY_MS_MAX=2000 # max jitter delay per worker (ms)
```

---

## Stats (First Batch Run)

- 807 scrape runs completed
- ~65K properties stored
- 124 geographies × 7 lead types
- Concurrency: 50 workers
- `render_js=false` (ScrapingBee premium proxy, no JS rendering needed for Zillow JSON)
