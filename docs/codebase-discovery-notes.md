# ARI API Codebase Discovery Notes

> Generated as part of the billing/metering foundation work (Phase 1).  
> See `billing-metering-foundation-progress.md` for the full implementation tracker.

---

## 1. Directory Structure

```
apps/api/
├── app.py                         # Main Quart app, Azure OpenAI client, MCP orchestration
├── cosmos.py                      # Azure Cosmos DB persistence layer
├── schemas.py                     # Pydantic schemas
├── requirements.txt               # Python dependencies
├── pytest.ini                     # Pytest config (asyncio_mode = strict)
├── Dockerfile
├── startup.sh
├── .env.example
├── middleware/
│   ├── __init__.py
│   ├── auth.py                    # JWT + API key auth
│   ├── rate_limit.py              # Sliding-window rate limiter (60 req/min/user)
│   └── guardrails.py              # Prompt injection + content moderation
├── routes/
│   ├── __init__.py                # Blueprint registration
│   ├── auth.py                    # POST /auth/exchange
│   ├── sessions.py                # CRUD + SSE streaming (/sessions/*)
│   ├── lead_runs.py               # /lead-runs/*
│   ├── documents.py               # /documents/*
│   ├── billing.py                 # /billing/*, /subscriptions/*
│   ├── frontend_data.py           # Extended message persistence
│   ├── magic_link.py              # Magic-link auth
│   ├── stripe_webhook.py          # Stripe webhook handler
│   └── demo.py                    # Public demo endpoint
├── services/
│   ├── __init__.py
│   ├── azure_blob.py              # Azure Blob Storage
│   ├── docx_export.py             # Markdown → DOCX
│   └── stack_lists.py             # Property list overlap analysis
└── tests/
    ├── conftest.py                # Fixtures: JWT, mock Cosmos, Quart test client
    ├── _constants.py
    ├── test_api.py
    ├── test_billing.py
    ├── test_sessions.py
    ├── test_lead_runs.py
    ├── test_guardrails.py
    ├── test_jwt_auth.py
    ├── test_magic_link.py
    ├── test_long_conversation.py
    ├── test_stress_integration.py
    └── test_regression.py
```

---

## 2. App Factory / Initialization

**Framework:** Quart (async Flask equivalent, built on asyncio)

- `app = Quart(__name__)` at `app.py:94`
- Blueprints registered inline (not a factory function): `app.py:105-113`
- `@app.before_request` at `app.py:535` — auth + rate limiting
- `@app.after_request` at `app.py:583` — CORS + security headers

---

## 3. LLM / Model Call Sites

All Azure OpenAI calls use `AsyncAzureOpenAI` (openai SDK ≥1.0).

| File:Line | Function | Model | Streaming | Purpose |
|-----------|----------|-------|-----------|---------|
| `app.py:1634` | `_classify_user_intent()` | `gpt-5-mini` | No | Pre-classify user intent (10-token max) |
| `app.py:1696` | `_run_mcp_tool_orchestration()` (loop) | `gpt-5.2-chat` | No | Model decides which MCP tools to call |
| `routes/sessions.py:566` | `_generation_task()` | `gpt-5.2-chat` | Yes | Primary SSE streaming chat response |
| `app.py:1823` | `generate_azure_response()` | `gpt-5.2-chat` | Yes | Legacy direct `/v1/chat/completions` endpoint |

**Client init:** `get_azure_client()` at `app.py:649` — `AsyncAzureOpenAI(api_key, api_version, azure_endpoint)`

**Non-streaming responses** have `resp.usage.prompt_tokens` / `resp.usage.completion_tokens` available directly.

**Streaming responses** do not include usage counts by default. Token counts must be estimated via tiktoken (already used in `_count_message_tokens()` at `app.py:758`).

---

## 4. Tool / Service Call Sites

**MCP Tool Endpoints** (registered in `MCP_TOOL_ENDPOINTS` at `app.py:212-229`):

| Tool Name | MCP Endpoint | Notes |
|-----------|-------------|-------|
| `mcp_leads_context` | `/tools/leads` | Zillow scraping via ScrapingBee |
| `mcp_buyers_search` | `/tools/buyers-search` | Cash buyer DB query |
| `mcp_comps_context` | `/tools/comps` | Comparable property analysis |
| `mcp_bricked_comps` | `/tools/bricked-comps` | ARV calc via Bricked integration |
| `mcp_attorneys_context` | `/tools/attorneys` | Attorney directory lookup |
| `mcp_strategy_context` | `/tools/strategy` | Knowledge-base retrieval |
| `mcp_contracts_context` | `/tools/contracts` | Contract template retrieval |
| `mcp_education_context` | `/tools/education` | Educational content |
| `mcp_offtopic_context` | `/tools/offtopic` | Off-topic deflection |
| `mcp_buyers_context` | `/tools/buyers` | Buyer context |
| `mcp_extract_city_state` | `/tools/extract-city-state` | NLP extraction |
| `mcp_extract_address` | `/tools/extract-address` | NLP extraction |
| `mcp_classify_route` | `/tools/classify` | Route classification |
| `mcp_integration_config` | `/tools/integration-config` | Backend availability |
| `mcp_build_retrieval_query` | `/tools/build-retrieval-query` | Query building |
| `mcp_infer_lead_type` | `/tools/infer-lead-type` | Lead type inference |

**Local Tools** (no HTTP proxy — handled in `_run_mcp_tool_orchestration()` at `app.py:1740-1744`):

| Tool Name | Handler | Notes |
|-----------|---------|-------|
| `generate_document` | `_handle_generate_document()` | Markdown→DOCX + Azure Blob upload |
| `mcp_stack_lists` | `_handle_stack_lists()` | Excel overlap analysis + Blob upload |

**Tool dispatch:** `app.py:1735-1751` (inside `_run_mcp_tool_orchestration()` loop)  
**HTTP proxy:** `_call_mcp_tool_endpoint()` at `app.py:1079`

---

## 5. Database / Persistence

**Primary database: Azure Cosmos DB (NoSQL)**

- Driver: `azure.cosmos.aio.CosmosClient` (async)
- No ORM — direct query execution
- No Alembic / SQLAlchemy — none present in the codebase
- File: `cosmos.py`
- Database: `db_conversation_history` (env: `AZURE_COSMOSDB_DATABASE`)
- Container: `sessions` (env: `AZURE_COSMOSDB_SESSIONS_CONTAINER`)
- Partition key: `/userId`

**There is NO PostgreSQL connection in `apps/api` currently.**  
The billing/metering work introduces PostgreSQL as a new, separate persistence layer.

---

## 6. Auth / Admin Middleware

**File:** `middleware/auth.py`

Two auth schemes:
1. **API Key:** `Authorization: Bearer <api-key>` or `API_KEYS` env var. Sets `request.api_key_auth = True`.
2. **JWT:** `Authorization: Bearer <jwt>`. Sets `request.user_id` and `request.user_email`.

**No admin role or admin endpoints exist today.** The billing work adds `@require_admin` stub.

**Auth bypass paths:** `/`, `/health`, `/webhook/stripe`, `/auth/exchange`, `/auth/magic-link/*`, `/auth/review-code`

---

## 7. Existing Usage Tracking

- **Message counting:** `cosmos.get_user_prompt_count_since()` — counts user messages for free-tier daily limit (5/day). Used at `routes/sessions.py:434`.
- **Structured JSON logs:** `_JSONFormatter` at `app.py:32` — every request logs `duration_ms`, `status`, `path`, `method`.
- **No token tracking** today — Azure OpenAI usage not persisted anywhere.
- **No cost tracking** today.

---

## 8. Async Patterns

- All route handlers: `async def`
- All Cosmos DB calls: `async def` with `azure.cosmos.aio`
- **Detached task pattern** in `routes/sessions.py:711`: `asyncio.ensure_future(_generation_task())` — generation runs independently of HTTP connection lifecycle
- Queue-based SSE streaming: `asyncio.Queue` bridges `_generation_task` → SSE generator
- Quart `asyncio_mode = strict` in pytest

---

## 9. Test Framework

- **Runner:** pytest with `pytest-asyncio`
- **Config:** `pytest.ini` — `asyncio_mode = strict`
- **Fixtures:** `tests/conftest.py` — JWT tokens, mock Cosmos, Quart test client
- **Pattern:** `@pytest.mark.asyncio` on all async tests
- **Mocking:** `unittest.mock.AsyncMock` + `unittest.mock.patch`

---

## 10. Route Registration

Blueprint pattern:
```python
# routes/__init__.py defines blueprints
# app.py:105-113 registers them:
app.register_blueprint(auth_bp)
app.register_blueprint(sessions_bp)
# ...
```

New `admin_bp` from `billing/admin_routes.py` registers at `/admin/*`.

---

## Key Finding: No PostgreSQL Exists Today

The billing/metering work introduces:
- `sqlalchemy[asyncio]` + `asyncpg` (new dependencies)
- `alembic` (new migration tool)
- `METERING_DATABASE_URL` env var pointing to a PostgreSQL instance
- `billing/` package with all metering code
- `migrations/` directory with Alembic config

**Metering is designed as an optional add-on:** if `METERING_DATABASE_URL` is not set, all metering calls are no-ops — no errors, no crashes.
