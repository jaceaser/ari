# Billing & Metering Foundation — Progress Tracker

## Feature Overview

Internal usage metering and cost tracking for ARI. Every LLM call and tool
invocation is recorded to PostgreSQL with token counts, cost estimates, and
timing. An admin reporting API surfaces spend breakdowns by user, model, tool,
and time period. No user-facing billing UI is included in Phase 1.

---

## Goals (Phase 1)

- Record every billable action (LLM call, tool call) to a persistent store
- Estimate cost per action using configurable pricing registries
- Expose admin-only reporting endpoints for spend analysis
- Design the schema so Phase 2 wallet/credits can reference it without migration changes
- Metering failures must **never** crash user requests

## Non-Goals (Phase 1)

- User-facing billing UI, wallet, or balance display
- Checkout flows, payment processing, or Stripe billing integration
- Per-user budget enforcement or blocking on low balance
- Pricing stored in database (it's config/code in Phase 1)
- Any changes to `apps/web`

---

## Architecture

```
User Request
     │
     ▼
routes/sessions.py  ──►  _generation_task()
     │                        │
     │                   metering.start_event()
     │                        │
     │                   _run_mcp_tool_orchestration()
     │                        │
     │              ┌─────────┴──────────┐
     │              │                    │
     │         LLM planning        Tool dispatch
     │         (non-streaming)     (_call_mcp_tool_endpoint /
     │              │               _handle_generate_document /
     │         metering.complete    _handle_stack_lists)
     │              │                    │
     │              └─────────┬──────────┘
     │                   metering.complete_event()
     │                        │
     │                   Main streaming call
     │                   (gpt-5.2-chat, SSE)
     │                        │
     │                   metering.complete_event()
     │                        │
     ▼                        ▼
SSE to client          usage_events table
                        (PostgreSQL ari_metering)
                               │
                               ▼
                        admin_routes.py
                        GET /admin/usage/*
```

---

## Tech Stack Notes

| Concern | Choice | Notes |
|---------|--------|-------|
| Metering DB | PostgreSQL (`ari_metering`) | Same server as `apps/lead_agent` (`ari-leads-pg`) — separate database |
| ORM | SQLAlchemy 2.x async | asyncpg driver; matches Quart's async model |
| Migrations | Alembic | Async-aware env.py (asyncpg + asyncio.run) |
| Pricing | Pure Python config | Decimal arithmetic throughout — no float |
| App framework | Quart (async) | All metering calls are `async def`, awaited correctly |
| Cosmos DB | **Not used for billing** | Cosmos stays for conversation/session data only |

---

## Implementation Checklist

### Phase 1A — Database Schema & Models
- [x] `billing/models.py` — `UsageEvent` SQLAlchemy model
- [x] `billing/database.py` — async engine + `get_db_session()` context manager
- [x] `billing/exceptions.py` — `MeteringError` hierarchy
- [x] `alembic.ini` — points to `migrations/`, URL from env at runtime
- [x] `migrations/env.py` — async-aware (asyncpg + `asyncio.run`)
- [x] `migrations/versions/001_create_usage_events.py` — table + 5 indexes
- [x] `requirements.txt` — added `sqlalchemy[asyncio]`, `asyncpg`, `alembic`
- [x] `tests/billing/test_phase1a.py` — 56 tests passing
- [x] Bug fix: `tests/conftest.py` — added missing `get_magic_token_raw` AsyncMock

### Phase 1B — Pricing Configuration
- [x] `billing/model_pricing.py` — `MODEL_PRICING` registry + `calculate_token_cost()`
- [x] `billing/tool_pricing.py` — `TOOL_PRICING` registry + `get_tool_cost()`
- [x] `tests/billing/test_pricing.py` — 44 tests passing
- [ ] **Pending human review**: verify pricing numbers against actual Azure/ScrapingBee invoices

### Phase 1C — Core Metering Service
- [ ] `billing/metering_service.py` — `start_event`, `complete_event`, `fail_event`
- [ ] Context manager `metering.track()`
- [ ] Idempotency guard on `complete_event` (execution_id deduplication)
- [ ] Failure isolation (metering errors never propagate to callers)
- [ ] `tests/billing/test_metering.py`

### Phase 1D — Integration into Existing Call Paths
- [ ] `app.py` — instrument `_classify_user_intent()` (gpt-5-mini)
- [ ] `app.py` — instrument MCP planning rounds in `_run_mcp_tool_orchestration()`
- [ ] `app.py` — instrument each tool dispatch in the orchestration loop
- [ ] `routes/sessions.py` — instrument main streaming call in `_generation_task()`
- [ ] Verify no user-facing behaviour changed

### Phase 1E — Admin Reporting Service
- [ ] `billing/reporting_service.py` — 9 query functions
- [ ] `billing/admin_routes.py` — 7 admin endpoints under `/admin/usage/*`
- [ ] `@require_admin` decorator (ADMIN_API_KEY env var stub)
- [ ] Register `admin_bp` in `app.py`
- [ ] `tests/billing/test_reporting.py`

### Phase 1F — Documentation
- [x] `docs/codebase-discovery-notes.md`
- [x] `docs/billing-metering-foundation-progress.md` (this file)
- [ ] Update after 1C, 1D, 1E complete

---

## Integration Points

> Populated as Phase 1D is implemented.

| File | Function | Action Type | What's Captured |
|------|----------|-------------|-----------------|
| `app.py` | `_classify_user_intent()` | `chat` / `intent-classification` | model, tokens, duration |
| `app.py` | `_run_mcp_tool_orchestration()` loop | `chat` / `mcp-planning` | model, tokens, duration, round index |
| `app.py` | `_run_mcp_tool_orchestration()` tool dispatch | `tool` / `<tool_name>` | tool name, duration, success/fail |
| `routes/sessions.py` | `_generation_task()` | `chat` / `<deployment>` | model, estimated tokens, duration |

---

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| PostgreSQL for metering, not Cosmos | Metering is relational/analytical — Cosmos is document-oriented and suited for conversation history, not aggregated spend queries |
| Reuse `ari-leads-pg` server, new `ari_metering` DB | No new Azure resource; billing data isolated from lead scraping data |
| Async SQLAlchemy + asyncpg | Quart is async — sync DB calls would block the event loop. Lead-agent uses sync but it's a batch job, not a web server |
| Alembic uses asyncio.run() in env.py | Alembic CLI is sync; wrapping with asyncio.run() lets us use the same asyncpg driver as the app with no extra dependency |
| Decimal for all costs | Float arithmetic accumulates error across many events. Decimal is exact and matches the Numeric(12,6) Postgres type |
| Metering is optional (no-op when METERING_DATABASE_URL unset) | Allows deployment without a metering DB — existing functionality is never blocked by missing billing infrastructure |
| Unknown models/tools return $0 with warning | Pricing gaps should be visible in logs and fixable, not crash-worthy |
| `@require_admin` stub with ADMIN_API_KEY | No role system exists today — stub keeps endpoints guarded while keeping the implementation replaceable |

---

## Open Questions

- [ ] Confirm `gpt-5.2-chat` and `gpt-5-mini` pricing against Azure invoices
- [ ] Confirm per-call ScrapingBee cost for `mcp_leads_context`
- [ ] Who is admin? Will `ADMIN_API_KEY` be sufficient long-term or does this need user roles?
- [ ] Should streaming token counts use `stream_options={"include_usage": True}` (exact) or tiktoken estimation (simpler)? Currently planning tiktoken.

---

## Phase 2 Plan

> Do not implement. Reference for next engineer.

### 2A — Wallet & Credits Data Model
- `wallets` table: `(user_id, balance NUMERIC(12,6), currency, status, created_at)`
- `wallet_transactions` table: `(wallet_id, amount, type: credit|debit, reference_event_id → usage_events.id, created_at)`
- Balance check and top-up functions

### 2B — Pre-Execution Balance Checks
- Middleware/decorator that checks wallet balance before billable actions
- Estimated cost pre-check using pricing modules from 1B
- Insufficient balance: block vs. warn vs. allow-with-flag (TBD policy)

### 2C — Post-Execution Billing
- Deduct actual cost from wallet after `complete_event`
- Handle partial failures (LLM succeeds, billing deduction fails)
- Atomic transaction between `usage_events` and `wallet_transactions`

### 2D — Auto-Recharge
- Threshold-based recharge rules
- Payment provider integration
- Recharge history

### 2E — User-Facing Usage Visibility
- Usage dashboard data endpoints (user-scoped, not admin)
- Current balance endpoint
- Transaction history
- These power future `apps/web` UI components

### 2F — Admin Dashboard
- Build on Phase 1E reporting endpoints
- Real-time usage monitoring
- User wallet management UI

### 2G — Pricing Management
- Admin ability to update model/tool pricing
- Per-user/per-plan pricing tiers
- Move pricing config from code to database
