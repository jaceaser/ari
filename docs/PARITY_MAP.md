# ARI Parity Map

## Current Capabilities (As-Is) and Migration Status

### Legend
- **Legacy**: Feature exists in `/legacy`
- **New**: Feature exists in `/apps` (web/api/mcp)
- **Gap**: Feature not yet migrated

---

### 1. Authentication & Session Management

| Capability | Legacy Location | New Location | Status |
|------------|----------------|--------------|--------|
| Magic link email auth | `legacy/app.py` (login, verify_magic_link) | `apps/web/app/(auth)` (NextAuth credentials) | **Different approach** - legacy uses magic links + Redis sessions; new uses email/password + NextAuth |
| Stripe subscription check | `legacy/app.py` (auth_required decorator) | Not implemented | **GAP** |
| Subscription tiers (lite/pro/elite) | `legacy/subscription.py` + `legacy/app.py` | Not implemented | **GAP** |
| Redis session store | `legacy/app.py` (create_async_redis_client) | `apps/web` uses SQLite | **Different approach** |
| Guest sessions | Not in legacy | `apps/web/app/(auth)/api/auth/guest` | **New only** |
| Session persistence (user_email key) | `legacy/app.py` (session['user_email']) | NextAuth session (userId) | **Partial** - user identity works, but no subscription/plan data |

### 2. Chat Flow

| Capability | Legacy Location | New Location | Status |
|------------|----------------|--------------|--------|
| Prompt classification | `legacy/chat_handler.py` (classify_prompt) | `apps/mcp/app.py` (classify route) | **Partial** - MCP has classifier but not wired to web |
| Tier-based routing (lite=Education, pro=most, elite=all) | `legacy/chat_handler.py` (handle_conversation) | Not implemented | **GAP** |
| WebSocket streaming | `legacy/app.py` (/ws/conversation, /ws/history/generate) | `apps/web/app/(chat)/api/chat` (HTTP SSE via AI SDK) | **Different approach** - new uses HTTP streaming |
| Token budgeting per route | `legacy/chat_handler.py` (ROUTE_BUDGETS, _build_messages_with_budget) | Not implemented | **GAP** |
| Session summary persistence | `legacy/chat_handler.py` (session_summary, _compress_context_summary) | Not implemented | **GAP** |
| Context injection per route | `legacy/chat_handler.py` (_add_context_to_request) | `apps/api/app.py` (_inject_server_system_prompts) | **Partial** - API injects system prompts from MCP tool results |
| Multi-model support | Legacy uses Azure OpenAI only | New supports Anthropic, OpenAI, Google, xAI via Vercel AI Gateway | **Improved** |

### 3. Route Handlers (Business Logic)

| Route | Legacy Location | New Location | Status |
|-------|----------------|--------------|--------|
| Education | `chat_handler.py` (_handle_education_query) | MCP: `/tools/education` (stub) | **GAP** - MCP returns hints but no real logic |
| Leads | `chat_handler.py` (_handle_leads_query) + `lead_gen.py` | MCP: `/tools/leads` (stub) | **GAP** - lead scraping not migrated |
| Comps | `chat_handler.py` (_handle_comps_query) + `lead_gen.py` (get_bricked_comps) | MCP: `/tools/bricked-comps` (stub) | **GAP** - Bricked API integration not migrated |
| Attorneys | `chat_handler.py` (_handle_attorneys_query) + `lead_gen.py` (get_attorneys) | MCP: `/tools/attorneys` (stub) | **GAP** |
| Strategy | `chat_handler.py` (_handle_strategy_query) | MCP: `/tools/strategy` (stub) | **GAP** |
| Contracts | `chat_handler.py` (_handle_contracts_query) | MCP: `/tools/contracts` (stub) | **GAP** |
| Buyers | `chat_handler.py` (_handle_buyers_query) | MCP: `/tools/buyers-search` (stub) | **GAP** - Cosmos buyers query not migrated |
| OffTopic | `chat_handler.py` (_handle_offtopic_query) | MCP: `/tools/offtopic` (stub) | **GAP** |

### 4. Data Services

| Service | Legacy Location | New Location | Status |
|---------|----------------|--------------|--------|
| CosmosDB conversations | `legacy/cosmos_db.py` (CosmosConversationClient) | `apps/web/lib/db` (SQLite + Drizzle) | **Different approach** |
| CosmosDB lead caching | `legacy/cosmos_db.py` (CosmosLeadGenClient) | Not implemented | **GAP** |
| CosmosDB buyers list | `legacy/cosmos_db.py` (CosmosBuyersClient) | Not implemented | **GAP** |
| Azure Blob Storage | `legacy/azure_blob.py` (AzureBlobService) | Not implemented | **GAP** |
| Azure Search (RAG) | `legacy/azure_openai.py` (retrieve_search_results) | Not implemented | **GAP** |
| Lead scraping (ScrapingBee) | `legacy/lead_gen.py` (get_properties, get_all_pages) | Not implemented | **GAP** |
| Bricked API (comps) | `legacy/lead_gen.py` (get_bricked_comps) | Not implemented | **GAP** |
| Exa search (subject property) | `legacy/lead_gen.py` (get_subj_property) | Not implemented | **GAP** |

### 5. Chat History

| Capability | Legacy Location | New Location | Status |
|------------|----------------|--------------|--------|
| List conversations | `legacy/app.py` (/history/list) | `apps/web/app/(chat)/api/history` | **Implemented** (SQLite) |
| Read conversation messages | `legacy/app.py` (/history/read) | `apps/web` (via Drizzle queries) | **Implemented** |
| Create conversation + auto-title | `legacy/app.py` (/history/generate) | `apps/web/app/(chat)/api/chat` (auto) | **Implemented** |
| Delete conversation | `legacy/app.py` (/history/delete) | `apps/web` sidebar actions | **Implemented** |
| Delete all conversations | `legacy/app.py` (/history/delete_all) | Not implemented | **GAP** |
| Rename conversation | `legacy/app.py` (/history/rename) | Not implemented | **GAP** |
| Update with assistant response | `legacy/app.py` (/history/update) | Auto-saved via AI SDK | **Implemented** |

### 6. UI/UX Features

| Feature | Legacy | New | Status |
|---------|--------|-----|--------|
| Chat interface | React + Fluent UI | Next.js + Tailwind + shadcn | **Implemented** (different style) |
| Chat history sidebar | ChatHistoryPanel.tsx | app-sidebar + sidebar-history | **Implemented** |
| Message feedback (thumbs) | Answer.tsx (positive/negative/neutral) | message-actions.tsx (vote) | **Implemented** |
| Typewriter effect | TypewriterEffect.tsx | Streaming via AI SDK | **Implemented** (different approach) |
| Suggested actions | QuestionInput.tsx (suggested questions) | suggested-actions.tsx | **Implemented** |
| Splash screen | SplashScreen.tsx | Not implemented | **GAP** |
| Profile page | Profile.tsx | sidebar-user-nav.tsx (minimal) | **Partial** |
| Citation display | Answer.tsx (citations with preview) | Not implemented | **GAP** - important for RAG |
| ARI branding (logo, colors) | Gold (#F7C35D) + black theme | Generic chatbot theme | **GAP** - needs branding alignment |
| Document/artifact editor | Not in legacy | Full implementation | **New only** |
| Multi-model selector | Not in legacy | model-selector.tsx | **New only** |
| Excel download links | In chat responses (blob URLs) | Not implemented | **GAP** |

### 7. Observability & Error Handling

| Feature | Legacy | New | Status |
|---------|--------|-----|--------|
| Discord error reporting | `discorderrorreporter.py` | Not implemented | **GAP** |
| Structured logging | RotatingFileHandler | console.log only | **GAP** |
| Correlation IDs | Not implemented | Not implemented | **GAP** in both |
| Rate limiting | Subscription-based (tier checks) | Basic entitlements in web | **Partial** |

---

## Migration Priority Order (Highest User Impact First)

1. **Chat routing through MCP** - Wire classifier + route handlers so the new app routes queries correctly
2. **Subscription/tier enforcement** - Without this, feature gating doesn't work
3. **Lead generation workflow** - Core business feature (Leads route + scraping + Excel download)
4. **Buyers list workflow** - Core business feature (Cosmos query + Excel export)
5. **Comps workflow** - Bricked API integration for property valuation
6. **Attorneys workflow** - ScrapingBee + legal directory parsing
7. **Azure Search RAG** - Education/Contracts routes need grounding
8. **UI branding alignment** - ARI logo, gold/black theme, splash screen
9. **Cosmos DB for conversations** - Replace SQLite for production scale
10. **Error reporting** - Discord webhook integration
