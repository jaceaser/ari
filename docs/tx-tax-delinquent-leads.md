# TX Tax Delinquent Leads — Feature Tracking

**Feature:** Texas Tax Delinquent Property Lead-Gen for Elite Subscribers  
**Branch:** `feature/billing-metering-foundation`  
**Started:** 2026-04-13  
**Owner:** Joshua Ceaser  
**Status:** Stage 1 (Discovery) → Stage 2 (Multi-Agent Prompt) → Stage 3 (Implementation)

---

## Progress

| Stage | Status | Notes |
|-------|--------|-------|
| Stage 1 — Discovery | ✅ Complete | Full codebase audit finished |
| Stage 2 — Multi-Agent Prompt | ✅ Complete | Agents defined below |
| Stage 3 — Implementation | ✅ Complete | 58/58 tests passing |

---

## Stage 1 — Discovery Report

### A. Architecture Summary

ARI is a monorepo with three services:
- **apps/api** — Python/Quart backend. Handles auth, chat streaming, MCP orchestration, billing.
- **apps/mcp** — Python/Quart MCP tool server. Implements individual lead/data tools called by apps/api.
- **apps/web** — Next.js 16 frontend (standalone Docker). Chat UI, billing pages, sidebar.

**Tier system:** Cosmos DB stores `tier` per user (`elite`, `lite`, `basic`, `free`, `canceled`).  
`elite` users get ALL tools. `lite`/`basic` get a curated subset. This is enforced in `apps/api/app.py` via `_get_tools_for_user()` which filters the tool list sent to the model.

**MCP pattern:** Each capability is an HTTP endpoint on the MCP server (`/tools/<name>`). The API orchestrates calls. The model sees only the tools its tier allows.

**Existing PostgreSQL lead pattern:** `apps/mcp/services/pg_leads.py` — synchronous psycopg2, new connection per call, `sslmode=require`, reads credentials from env vars. This is the exact pattern to follow.

---

### B. Findings

1. **Entitlement is already correct for Elite**: `_TIER_TOOLS["elite"] = _ALL_TOOL_NAMES`. Any tool added to `MCP_TOOL_DEFINITIONS` is automatically available to Elite without changing `_TIER_TOOLS`. Non-Elite tiers use explicit allow-lists that do NOT include the new tool — so they are blocked automatically.

2. **psycopg2-binary is already in `apps/mcp/requirements.txt`** — no new dependency required.

3. **MCP does NOT enforce tier** — it enforces intent classification only. Tier enforcement is 100% in `apps/api`. This is correct architecture; MCP is internal-only.

4. **The tool name "tax delinquent" already appears in the existing leads tool description** and in guardrails `_CORE_SIGNALS`. The new tool needs a distinct description so the model distinguishes it from the general Zillow-scrape leads tool.

5. **No connection pooling in the MCP service layer** — each service call opens and closes one psycopg2 connection. Acceptable for the expected query frequency (Elite subscribers only).

6. **`fact_property_latest` is the primary query surface** — it's a materialized view with all needed fields. Do NOT join to `dim_property` or `dim_county` for normal queries.

7. **County-name → county-key resolution is a performance optimization**: `county_key + is_delinquent` uses a fast composite index. `county_name` filtering on its own is slower. The service should resolve county_name to county_key via a lookup query when possible.

8. **`sptb_code`-only filtering can be slow** on 3.25M rows. Must require at least one other filter when sptb_code is used.

9. **The existing lead run tracking** in Cosmos (`lead_run` document type) can be extended to track tax delinquent queries, but for v1 we can omit this since there is no Excel export (results are shown in-chat).

10. **The model already knows about "tax delinquent"** as a general concept — it routes these to `mcp_leads_context`. The new tool needs a clear description that distinguishes it: "for Texas-specific tax delinquent property data from county appraisal district records — NOT Zillow."

11. **Azure Blob upload for large results**: The existing `AzureBlobService` in apps/mcp can be used to offer an Excel download link for large result sets (>50 properties). This is optional for v1 but should be architected.

12. **No asyncpg in apps/mcp** — apps/mcp uses sync psycopg2. apps/api uses asyncpg for billing. The new service should use sync psycopg2 (consistent with apps/mcp pattern).

---

### C. Assumptions / Open Questions

1. **Is `txassetadmin` a read-only user?** Assumed yes. Confirm with infra. If not, create a read-only `txasset_ro` user in Azure PostgreSQL before deploying.

2. **Are county_key values stable integers?** The county lookup table `dim_county` exists. We assume `county_key` is an integer PK. Confirm schema.

3. **Is `fact_property_latest` a materialized view or a physical table?** Query performance depends on this. Assumed materialized view with indexes as described in the spec.

4. **SSL cert for Azure PostgreSQL**: `sslmode=require` is sufficient on Azure (host cert is trusted). No client cert needed.

5. **Should large results be uploaded to Azure Blob as Excel?** The existing leads tool does this. For tax leads, results can be 100+ rows. v1 will return a truncated preview (25 rows) with row count. v1.5 can add Excel export.

6. **`dim_county` for county_key resolution** — Does it have `county_name` field? Query: `SELECT county_key FROM dim_county WHERE county_name ILIKE %(county_name)s LIMIT 1`. Assumed yes.

7. **Should the API layer (apps/api) also have a server-side enforcement layer for this specific tool?** Current design already handles this: `_get_tools_for_user()` only includes `mcp_tx_tax_leads` for elite users since elite = ALL tools. No additional route-level check needed.

---

### D. Recommended Implementation Approach

Implement as a **new MCP tool** (`/tools/tx-tax-leads`) following the exact same pattern as `/tools/leads`:

1. **New service module**: `apps/mcp/services/tx_tax_delinquent.py`
   - Connection factory (env-vars only, sslmode=require)
   - County-name → county-key resolution
   - Constrained parameterized query builder for `fact_property_latest`
   - Assessment detail function for `fact_tax_assessment`
   - All SQL fully parameterized — model never touches SQL

2. **New MCP endpoint**: `apps/mcp/app.py` → `POST /tools/tx-tax-leads`
   - Accepts structured JSON params (county, filters, pagination)
   - Calls service, formats response
   - Returns: status, count, preview (HTML table, top 25), route_system_prompt

3. **API tool definition**: `apps/api/app.py`
   - Add `mcp_tx_tax_leads` to `MCP_TOOL_DEFINITIONS` with rich description
   - Add to `MCP_TOOL_ENDPOINTS`
   - Elite = ALL tools already covers this

4. **Guardrails**: `apps/mcp/middleware/guardrails.py`
   - Add `/tools/tx-tax-leads` to `TOOL_ALLOWLIST[Intent.REAL_ESTATE_CORE]`

5. **Environment variables** (MCP `.env` and Azure App Service):
   - `TX_DELINQUENT_PG_HOST`, `TX_DELINQUENT_PG_PORT`, `TX_DELINQUENT_PG_DATABASE`
   - `TX_DELINQUENT_PG_USERNAME`, `TX_DELINQUENT_PG_PASSWORD`

---

### E. Files/Systems That Must Change

| File | Change Type | Description |
|------|-------------|-------------|
| `apps/mcp/services/tx_tax_delinquent.py` | **NEW** | Core service: connection factory, query builder, county resolution, assessment detail |
| `apps/mcp/app.py` | **MODIFY** | Add `POST /tools/tx-tax-leads` endpoint |
| `apps/mcp/middleware/guardrails.py` | **MODIFY** | Add `/tools/tx-tax-leads` to `REAL_ESTATE_CORE` allowlist |
| `apps/api/app.py` | **MODIFY** | Add `mcp_tx_tax_leads` to `MCP_TOOL_DEFINITIONS` + `MCP_TOOL_ENDPOINTS` |
| `apps/mcp/tests/test_tx_tax_delinquent.py` | **NEW** | Unit + integration tests |
| `docs/tx-tax-delinquent-leads.md` | **NEW** | This tracking file |
| `apps/mcp/.env.example` | **MODIFY** | Document new env vars (if exists) |

**No changes needed:**
- `apps/api/app.py` `_TIER_TOOLS` — elite = ALL already
- `apps/mcp/requirements.txt` — psycopg2-binary already present
- Frontend — chat already renders tool results; no new UI for v1
- Cosmos DB schema — no new document types for v1

---

### F. Phased Implementation Plan

**Phase 1 (v1 — This PR):**
- Service module with query builder + county resolution + assessment detail
- MCP endpoint with safe parameterized execution
- API tool definition + guardrails update
- Unit tests for query builder
- Env var documentation

**Phase 2 (v1.5 — Follow-on):**
- Excel export for large result sets via AzureBlobService
- Lead run tracking in Cosmos for tax delinquent results
- Statewide summary / county rollups
- Geo/radius search (if geom field accessible and PostGIS available)

**Phase 3 (v2 — Future):**
- Dedicated Elite UI tab for saved tax lead searches
- Side-by-side county comparison
- Owner contact enrichment
- Export to CRM

---

## Stage 2 — Multi-Agent Prompt

See section below.

---

## Stage 3 — Implementation Log

### Environment Variables Required

```
TX_DELINQUENT_PG_HOST=txasset-pg.postgres.database.azure.com
TX_DELINQUENT_PG_PORT=5432
TX_DELINQUENT_PG_DATABASE=taxdelinquent
TX_DELINQUENT_PG_USERNAME=txassetadmin
TX_DELINQUENT_PG_PASSWORD=<from Azure Key Vault or App Service env>
```

Must be set in:
- `apps/mcp/.env` (local dev)
- Azure App Service env vars for `ari-mcp-prod` and `ari-mcp-dev`
- Never committed to git

### Query Constraints (v1)

| Filter | Column | Type | Notes |
|--------|---------|------|-------|
| county_name | county_name / county_key | string | resolve to county_key first |
| min_amount_due | total_amount_due | float | fast index |
| max_amount_due | total_amount_due | float | fast index |
| owner_name | owner_name | string | ILIKE, trigram index |
| out_of_state | owner_mail_state | bool | != 'TX' |
| min_years_delinquent | years_delinquent | int | |
| has_lawsuit | has_lawsuit | bool | |
| has_judgment | has_judgment | bool | |
| min_market_value | market_value | float | |
| max_market_value | market_value | float | |
| sptb_code | sptb_code | string | requires another filter |
| limit | (query) | int | default 25, max 100 |
| offset | (query) | int | default 0 |
| property_key | property_key | int | detail lookup only |

### Safety Rules

1. `is_delinquent = true` is ALWAYS included (unless detail lookup by property_key)
2. `LIMIT` is always applied — default 25, max 100
3. `sptb_code`-only filter is rejected (must combine with county or amount or owner)
4. All inputs are parameterized — no f-strings with user data in SQL
5. County name resolution uses a separate parameterized query
6. The model NEVER constructs SQL — it passes JSON params to the tool

---

## Code Changes Made (Stage 3)

### New Files
| File | Description |
|------|-------------|
| `apps/mcp/services/tx_tax_delinquent.py` | PostgreSQL service: connection factory, county resolution, constrained query builder, property detail, assessment breakdown |
| `apps/mcp/tests/test_tx_tax_delinquent.py` | 58 unit tests: query builder, limit clamping, sptb_code rejection, entitlement, guardrails |
| `docs/tx-tax-delinquent-leads.md` | This tracking file |

### Modified Files
| File | Change |
|------|--------|
| `apps/mcp/app.py` | Added `POST /tools/tx-tax-leads` endpoint + three HTML formatting helpers |
| `apps/mcp/middleware/guardrails.py` | Added `/tools/tx-tax-leads` to `REAL_ESTATE_CORE` allowlist |
| `apps/api/app.py` | Added `mcp_tx_tax_leads` to `MCP_TOOL_DEFINITIONS`, `MCP_TOOL_ENDPOINTS`, and routing instructions |

### Tests Added
- 58 tests in `apps/mcp/tests/test_tx_tax_delinquent.py`
- All 58 passing (`pytest apps/mcp/tests/test_tx_tax_delinquent.py`)

### No Dependencies Added
- `psycopg2-binary` already in `apps/mcp/requirements.txt`
- No new packages required

---

## Open Issues / Follow-Ups

- [ ] **REQUIRED before deploy**: Add `TX_DELINQUENT_PG_PASSWORD` to Azure App Service env for `ari-mcp-prod` and `ari-mcp-dev`
- [ ] **REQUIRED before deploy**: Add all `TX_DELINQUENT_PG_*` env vars to Azure App Service settings
- [ ] **Confirm**: `txassetadmin` has SELECT-only grants (no INSERT/UPDATE/DELETE) on `taxdelinquent` db
- [ ] **Confirm**: `dim_county` schema has `county_name` + `county_key` columns as assumed
- [ ] **Confirm**: `fact_tax_assessment` has columns matching `_ASSESSMENT_COLUMNS` in the service
- [ ] **Confirm**: `fact_property_latest` is accessible (materialized view vs table doesn't change queries)
- [ ] Phase 2: Excel export for large result sets via AzureBlobService
- [ ] Phase 2: Lead run tracking in Cosmos for tax delinquent searches
- [ ] Phase 2: Statewide / county rollup summaries
- [ ] Phase 3: Dedicated Elite UI tab

---

## Architecture Decision Records

### ADR-001: MCP tool vs API route vs backend service

**Decision:** Implement as a new MCP tool (`/tools/tx-tax-leads`) following the exact pg_leads.py pattern.

**Rationale:** 
- Consistent with all other data-fetching tools
- API layer already handles tier enforcement, tool routing, MCP orchestration
- Service layer isolation means the model never touches SQL
- Easy to add to future lead source patterns

### ADR-002: Sync psycopg2 vs async asyncpg

**Decision:** Use sync psycopg2 (consistent with apps/mcp pattern).

**Rationale:** apps/mcp uses sync psycopg2 everywhere. apps/api uses asyncpg for billing. Introducing asyncpg to apps/mcp would require async endpoints which currently use Quart's async but run sync service calls in a thread executor. Not worth the complexity for v1.

### ADR-003: Constrained query builder vs freeform SQL

**Decision:** Constrained query builder with explicit allowed filters only.

**Rationale:** The model must never construct arbitrary SQL. A whitelist-based builder prevents injection, prevents expensive queries, and makes the capability auditable.

### ADR-004: County resolution strategy

**Decision:** Two-step: resolve county_name → county_key via dim_county lookup, then use county_key + is_delinquent composite index for main query.

**Rationale:** Performance guidance says county_key + is_delinquent is fast. county_name alone is slower on 3.25M rows.

### ADR-005: Separate env var prefix (TX_DELINQUENT_PG_*)

**Decision:** Use `TX_DELINQUENT_PG_*` env vars distinct from `AZURE_PG_*`.

**Rationale:** These point to a different PostgreSQL server (txasset-pg vs ari-leads-pg) with a different database (taxdelinquent vs lead_agent). Sharing env var names would cause a conflict.
