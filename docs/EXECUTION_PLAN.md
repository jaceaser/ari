# ARI Rebuild - Phased Execution Plan

## Phase 1: Foundation (PRs 1-3)

### PR 1: MCP Server - Wire Real Tool Logic
**Agent**: MCP Agent
**Scope**: Replace MCP stub responses with actual business logic migrated from legacy
**Files**:
- `apps/mcp/app.py` - Implement real classify, education, leads-context, comps-context handlers
- `apps/mcp/services/lead_gen.py` - Port LeadGenService from `legacy/lead_gen.py`
- `apps/mcp/services/cosmos_db.py` - Port CosmosDB clients from `legacy/cosmos_db.py`
- `apps/mcp/services/azure_blob.py` - Port AzureBlobService from `legacy/azure_blob.py`
- `apps/mcp/schemas/` - Pydantic request/response schemas for all 16 tools
- `apps/mcp/requirements.txt` - Updated dependencies
- `apps/mcp/tests/test_tools.py` - Unit tests for each tool endpoint

**Acceptance Tests**:
- [ ] POST `/tools/classify` returns valid route for 10 test prompts
- [ ] POST `/tools/leads` returns lead context with URL generation
- [ ] POST `/tools/bricked-comps` calls Bricked API and returns trimmed payload
- [ ] POST `/tools/buyers-search` queries Cosmos and returns preview rows
- [ ] All tool endpoints validate input with Pydantic and return typed responses
- [ ] All tool endpoints return `{ ok, tool, data/error }` envelope

### PR 2: API Layer - Auth, Session, and Contract Hardening
**Agent**: API Agent + Security Agent
**Scope**: Add auth middleware, request validation, CORS hardening, structured logging
**Files**:
- `apps/api/app.py` - Add API key auth middleware, correlation IDs, structured logging
- `apps/api/middleware/auth.py` - API key validation (for web->api calls)
- `apps/api/middleware/rate_limit.py` - Basic rate limiting per API key
- `apps/api/schemas.py` - Expand Pydantic models for all request/response types
- `apps/api/.env.example` - Document all required env vars
- `apps/api/tests/test_api.py` - Endpoint tests with mock Azure client

**Acceptance Tests**:
- [ ] Requests without valid API key return 401
- [ ] Invalid request bodies return 400 with descriptive errors
- [ ] CORS only allows configured origins
- [ ] All responses include correlation ID header
- [ ] Health endpoint shows component status (Azure, MCP)
- [ ] Rate limit returns 429 after threshold

### PR 3: Web Frontend - ARI Branding + Chat History Parity
**Agent**: Web Agent
**Scope**: Apply ARI branding, add missing chat history features, connect to external API
**Files**:
- `apps/web/app/globals.css` - ARI color scheme (gold #F7C35D, black, dark theme)
- `apps/web/components/greeting.tsx` - ARI-branded welcome with logo
- `apps/web/components/sidebar-history.tsx` - Add rename, delete-all actions
- `apps/web/components/chat-header.tsx` - ARI branding
- `apps/web/app/(chat)/api/chat/route.ts` - Route through external API when configured
- `apps/web/public/` - ARI logo assets from legacy
- `apps/web/tests/e2e/branding.spec.ts` - Visual regression tests

**Acceptance Tests**:
- [ ] Chat page shows ARI logo and gold/black theme
- [ ] Sidebar allows renaming conversations
- [ ] Sidebar has "delete all" option
- [ ] When NEXT_PUBLIC_API_URL is set, chat routes through external API
- [ ] Greeting message matches legacy UX

---

## Phase 2: Business Logic Integration (PRs 4-7)

### PR 4: Leads Workflow End-to-End
**Agent**: MCP Agent + Web Agent
- MCP: `/tools/leads` generates Zillow URLs, scrapes via ScrapingBee, caches in Cosmos, uploads Excel to Blob
- API: Tool orchestration picks up lead results and streams to user
- Web: Display Excel download links in chat messages
- Tests: E2E test with mock ScrapingBee response

### PR 5: Buyers Workflow End-to-End
**Agent**: MCP Agent + Web Agent
- MCP: `/tools/buyers-search` queries Cosmos buyers, uploads Excel, returns preview
- Web: Renders buyer preview table and download link
- Tests: Unit test with mock Cosmos response

### PR 6: Comps Workflow (Bricked API)
**Agent**: MCP Agent
- MCP: `/tools/bricked-comps` calls Bricked API, returns ARV/CMV/comps
- API: Streams enriched response with property data
- Tests: Integration test with Bricked API mock

### PR 7: Subscription & Tier Enforcement
**Agent**: API Agent + Security Agent
- API: Add Stripe webhook handler, Redis subscription store
- API: Tier-based route filtering (lite=Education only, pro=most, elite=all)
- Web: Pass subscription tier in chat requests
- Tests: Test tier routing with different subscription levels

---

## Phase 3: Polish & Observability (PRs 8-10)

### PR 8: Azure Search RAG Integration
**Agent**: MCP Agent + API Agent
- MCP: `/tools/build-retrieval-query` + search results injection
- API: Education and Contracts routes get Azure Search grounding
- Tests: Search integration test with mock index

### PR 9: Error Reporting & Observability
**Agent**: QA Agent + Security Agent
- All layers: Structured JSON logging with correlation IDs
- API/MCP: Discord error reporter (port from legacy)
- Web: Error boundaries with user-friendly messages
- All: Health check endpoints with dependency status
- Tests: Error scenario tests

### PR 10: Attorneys, Strategy, Contracts, OffTopic Routes
**Agent**: MCP Agent
- Complete remaining route handlers
- Attorneys: ScrapingBee integration for legal directories
- Strategy: Reasoning model with budget
- Contracts: Contract expansion + Azure Search
- OffTopic: Redirect with datetime injection
- Tests: Per-route unit tests

---

## Phase 4: Production Readiness (PRs 11-12)

### PR 11: Security Hardening
**Agent**: Security Agent
- Input sanitization on all user-facing endpoints
- Secrets audit (no keys in logs/responses)
- CORS, CSP, and security headers
- Safe prompt execution (no injection vectors)
- Dependency vulnerability scan

### PR 12: E2E Integration Tests + Documentation
**Agent**: QA Agent
- Full integration test suite (web -> api -> mcp -> external services)
- Load testing script for streaming endpoints
- Updated README with setup/run instructions
- Docker Compose for local development
- CI/CD pipeline configuration

---

## Milestones & Checkpoints

| Milestone | PRs | Checkpoint |
|-----------|-----|------------|
| **M1: Wired** | 1-3 | MCP tools return real data, API has auth, Web has branding |
| **M2: Core Workflows** | 4-6 | Leads, Buyers, Comps work end-to-end |
| **M3: Full Parity** | 7-10 | All routes work, subscriptions enforced, RAG integrated |
| **M4: Production** | 11-12 | Security hardened, fully tested, documented |
