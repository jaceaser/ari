# ARI Contracts Map

## API Routes (Web <-> API)

### Current: apps/web internal routes

| Method | Route | Request | Response | Auth | Notes |
|--------|-------|---------|----------|------|-------|
| POST | `/api/chat` | `{ id, message: {id, role, parts}, selectedChatModel, selectedVisibilityType }` | SSE stream (AI SDK format) | NextAuth session | Main chat endpoint (local SQLite) |
| POST | `/api/chat/openai` | `{ messages, session_id? }` | SSE stream (UIMessageStream) | NextAuth session | Routes to `/v1/chat/completions` or `/sessions/:id/messages` |
| GET | `/api/chat/[id]/stream` | Query: `chatId` | SSE stream | NextAuth session | Resume interrupted stream |
| GET | `/api/history` | `?limit=N` | `{ chats: Chat[], hasMore }` | NextAuth session | External: proxies GET /sessions; Local: SQLite |
| POST | `/api/vote` | `{ chatId, messageId, type: "up"|"down" }` | `{ success }` | NextAuth session | Message feedback |
| POST | `/api/document` | `{ id, title, kind, content }` | Document record | NextAuth session | Create/update document |
| POST | `/api/files/upload` | FormData (file) | `{ url, name, contentType }` | NextAuth session | File upload |
| POST | `/api/suggestions` | `{ documentId }` | `Suggestion[]` | NextAuth session | AI suggestions |

### Phase 2: apps/web proxy routes (→ apps/api with JWT)

| Method | Route | Upstream | Auth | Notes |
|--------|-------|----------|------|-------|
| GET | `/api/sessions` | GET /sessions | NextAuth → JWT | List user sessions |
| POST | `/api/sessions` | POST /sessions `{ id?, title? }` | NextAuth → JWT | Create session (optional client ID) |
| GET | `/api/sessions/[id]/messages` | GET /sessions/:id/messages | NextAuth → JWT | Message history (UI replay) |
| POST | `/api/sessions/[id]/seal` | POST /sessions/:id/seal | NextAuth → JWT | Seal session |
| GET | `/api/lead-runs` | GET /lead-runs | NextAuth → JWT | List lead runs |
| GET | `/api/lead-runs/[id]` | GET /lead-runs/:id | NextAuth → JWT | Lead run detail + file_url |
| PATCH | `/api/sessions/[id]` | PATCH /sessions/:id `{ title }` | NextAuth → JWT | Update session title |
| DELETE | `/api/chat?id=` | DELETE /sessions/:id | NextAuth → JWT | Delete session + messages |
| POST | `/api/files/upload` | POST /documents/upload (FormData) | NextAuth → JWT | Upload file to Azure Blob |

### Current: apps/api routes

| Method | Route | Request | Response | Auth | Notes |
|--------|-------|---------|----------|------|-------|
| POST | `/v1/chat/completions` | OpenAI-compatible ChatCompletionRequest | SSE stream | API key (Bearer) | Main chat with MCP orchestration |
| GET | `/health` | None | `{ status, timestamp, version, mcp_enabled }` | None | Health check |
| GET | `/` | None | `{ name, version, endpoints }` | None | Root info |

### Phase 2: apps/api routes (JWT auth)

| Method | Route | Request | Response | Auth | Notes |
|--------|-------|---------|----------|------|-------|
| POST | `/auth/exchange` | None (reads session cookie) | `{ token, user_id, email }` | Session cookie | Exchange session for JWT |
| POST | `/sessions` | `{ title? }` | `{ id, created_at }` (201) | JWT | Create chat session |
| GET | `/sessions` | None | `SessionListItem[]` | JWT | List user sessions |
| GET | `/sessions/<id>` | None | `SessionDetail` | JWT | Get session detail |
| POST | `/sessions/<id>/seal` | None | `{ id, status, sealed_at }` | JWT | Seal session (no more messages) |
| POST | `/sessions/<id>/messages` | `{ content: string, images?: string[], documents?: {url,name,mediaType}[] }` | SSE stream | JWT | Send message + stream response |
| GET | `/sessions/<id>/messages` | None | `MessageResponse[]` | JWT | Full message history (UI replay) |
| PATCH | `/sessions/<id>` | `{ title: string }` | `{ id, title, status }` | JWT | Update session title |
| DELETE | `/sessions/<id>` | None | `{ id, deleted: true }` | JWT | Delete session + all messages |
| POST | `/documents/upload` | FormData (file) | `{ url, name, contentType, size }` | JWT | Upload file to Azure Blob |
| GET | `/lead-runs` | None | `LeadRunListItem[]` | JWT | List lead runs |
| GET | `/lead-runs/<id>` | None | `LeadRunDetail` | JWT | Lead run detail with file_url |

### Legacy routes (to be migrated)

| Method | Route | Request | Response | Auth | Notes |
|--------|-------|---------|----------|------|-------|
| POST | `/login` | Form: `{ email }` | Redirect | None | Magic link initiation |
| GET | `/auth/verify` | Query: `{ token }` | Redirect + session | None | Magic link verification |
| GET | `/api/userinfo` | None | `{ name, email, subscription_plan, subscription_id }` | Session | User info |
| POST | `/webhook/stripe` | Stripe event payload | `{ success }` | Stripe signature | Subscription events |
| WS | `/ws/conversation` | `{ messages, type? }` | Stream chunks | Session | Real-time chat |
| WS | `/ws/history/generate` | `{ messages, conversation_id? }` | Stream chunks + metadata | Session | Chat with history persistence |
| POST | `/history/generate` | `{ messages, conversation_id? }` | Chat response | Session | HTTP fallback for chat |
| GET | `/history/list` | Query: `{ offset }` | `Conversation[]` | Session | List conversations |
| POST | `/history/read` | `{ conversation_id }` | `{ conversation_id, messages }` | Session | Read conversation |
| POST | `/history/rename` | `{ conversation_id, title }` | Updated conversation | Session | Rename conversation |
| POST | `/history/update` | `{ conversation_id, messages }` | `{ success }` | Session | Save assistant response |
| POST | `/history/clear` | `{ conversation_id }` | `{ message }` | Session | Clear messages |
| DELETE | `/history/delete` | `{ conversation_id }` | `{ message }` | Session | Delete conversation |
| DELETE | `/history/delete_all` | None | `{ message }` | Session | Delete all conversations |
| GET | `/history/ensure` | None | `{ message }` | None | Cosmos health check |
| GET | `/frontend_settings` | None | UI_CONFIG object | None | Frontend config |

---

## MCP Tools (API/Web <-> MCP)

### Tool Definitions (from apps/api/app.py)

| Tool Name | Endpoint | Input Schema | Output | Purpose |
|-----------|----------|-------------|--------|---------|
| `mcp_integration_config` | `/tools/integration-config` | `{}` | Availability flags | Check backend availability |
| `mcp_classify_route` | `/tools/classify` | `{ prompt: string }` | `{ route: string }` | Classify query into route |
| `mcp_education_context` | `/tools/education` | `{ prompt: string }` | Context + hints | Education route context |
| `mcp_comps_context` | `/tools/comps` | `{ prompt: string }` | Context + hints | Comps route context |
| `mcp_bricked_comps` | `/tools/bricked-comps` | `{ prompt?, address?, max_comps? }` | ARV/CMV/comps payload | Bricked API proxy |
| `mcp_leads_context` | `/tools/leads` | `{ prompt: string }` | Lead type + hints | Leads route context |
| `mcp_attorneys_context` | `/tools/attorneys` | `{ prompt: string }` | Context + hints | Attorneys route context |
| `mcp_strategy_context` | `/tools/strategy` | `{ prompt: string }` | Context + hints | Strategy route context |
| `mcp_contracts_context` | `/tools/contracts` | `{ prompt: string }` | Context + hints | Contracts route context |
| `mcp_buyers_context` | `/tools/buyers` | `{ prompt: string }` | Location hints | Buyers route context |
| `mcp_buyers_search` | `/tools/buyers-search` | `{ prompt?, city?, state?, max_results? }` | Buyer rows preview | Cosmos buyers query |
| `mcp_extract_city_state` | `/tools/extract-city-state` | `{ prompt?, city?, state? }` | `{ city, state }` | Location extraction |
| `mcp_extract_address` | `/tools/extract-address` | `{ prompt?, address? }` | `{ address }` | Address extraction |
| `mcp_offtopic_context` | `/tools/offtopic` | `{ prompt: string }` | Redirect strategy | Off-topic handling |
| `mcp_build_retrieval_query` | `/tools/build-retrieval-query` | `{ prompt: string }` | Short keyword query | Search query builder |
| `mcp_infer_lead_type` | `/tools/infer-lead-type` | `{ prompt?, url? }` | Lead type string | Lead type inference |

### MCP Request Envelope (API -> MCP)

```json
{
  "prompt": "string (user prompt or fallback)",
  "messages": [
    { "role": "user|assistant|system", "content": "string" }
  ],
  "arguments": { "...tool-specific args" }
}
```

### MCP Response Envelope (MCP -> API)

```json
{
  "ok": true,
  "tool": "tool_name",
  "data": { "...tool-specific response" }
}
```

Error response:
```json
{
  "ok": false,
  "tool": "tool_name",
  "error": "error message",
  "body": "optional response body"
}
```

---

## Data Models

### User
| Field | Type | Source | Notes |
|-------|------|--------|-------|
| id | string (uuid) | apps/web (SQLite) | Primary key |
| email | string | Both | Unique identifier |
| password | string (hash) | apps/web only | bcrypt hash |
| subscription_plan | string | legacy only (Redis) | ari_lite / ari_pro / ari_elite |
| subscription_id | string | legacy only (Redis) | Stripe subscription ID |

### Chat/Conversation
| Field | Type | Source | Notes |
|-------|------|--------|-------|
| id | string (uuid) | Both | Primary key |
| title | string | Both | Auto-generated or renamed |
| userId | string | Both | Owner (email in legacy, uuid in new) |
| createdAt | datetime | Both | Creation timestamp |
| updatedAt | datetime | legacy only | Last message timestamp |
| visibility | "public" / "private" | apps/web only | New feature |
| type | "conversation" | legacy only | Cosmos document type |

### Message
| Field | Type | Source | Notes |
|-------|------|--------|-------|
| id | string (uuid) | Both | Primary key |
| chatId / conversationId | string | Both | Parent conversation |
| role | string | Both | user / assistant / system / tool |
| parts | JSON array | apps/web only | `[{type: "text", text: "..."}, {type: "file", ...}]` |
| content | string | legacy only | Plain text content |
| createdAt | datetime | Both | Timestamp |
| feedback | string | legacy only | User feedback on message |

### Vote (new only)
| Field | Type | Notes |
|-------|------|-------|
| chatId | string | Chat reference |
| messageId | string | Message reference |
| type | "up" / "down" | Vote type |

### Session (Phase 2 — Cosmos `sessions` container)
| Field | Type | Notes |
|-------|------|-------|
| id | string (uuid) | Document ID |
| type | "session" | Document type discriminator |
| userId | string | Partition key |
| title | string? | Optional session title |
| status | "active" / "sealed" | Session lifecycle |
| createdAt | datetime (ISO) | Creation timestamp |
| sealedAt | datetime? (ISO) | When sealed |

### Message (Phase 2 — Cosmos `sessions` container)
| Field | Type | Notes |
|-------|------|-------|
| id | string (uuid) | Document ID |
| type | "message" | Document type discriminator |
| userId | string | Partition key |
| sessionId | string | Parent session |
| role | "user" / "assistant" | Message author |
| content | string | Plain text content |
| metadata | dict? | Optional metadata |
| createdAt | datetime (ISO) | Timestamp |

### Lead Run (Phase 2 — Cosmos `sessions` container)
| Field | Type | Notes |
|-------|------|-------|
| id | string (uuid) | Document ID |
| type | "lead_run" | Document type discriminator |
| userId | string | Partition key |
| sessionId | string? | Associated session |
| summary | string | Run description |
| location | string | Target location |
| strategy | string | Lead strategy used |
| resultCount | int | Number of results |
| fileUrl | string | Download URL (never logged) |
| filters | dict? | Applied filters |
| createdAt | datetime (ISO) | Timestamp |

### Lead Run (legacy only - needs migration)
| Field | Type | Notes |
|-------|------|-------|
| id | string (uuid) | Cosmos document ID |
| url | string | Source URL |
| timestamp | datetime | When cached |
| data | JSON string | Property data (serialized DataFrame) |
| excel_link | string | Azure Blob SAS URL |

### Buyer (legacy only - needs migration)
| Field | Type | Notes |
|-------|------|-------|
| First Name | string | |
| Last Name | string | |
| Full Name | string | |
| Phones_Formatted | string | |
| Email | string | |
| cities | string | Lowercase city list |
| state | string | Partition key |

---

## Environment Variables

### Required for apps/web
| Variable | Purpose | Default |
|----------|---------|---------|
| `AUTH_SECRET` | NextAuth encryption key | (required) |
| `AI_GATEWAY_API_KEY` | Vercel AI Gateway API key | (required) |
| `NEXT_PUBLIC_API_URL` | External API URL (optional) | (internal) |

### Required for apps/api
| Variable | Purpose | Default |
|----------|---------|---------|
| `AZURE_OPENAI_KEY` | Azure OpenAI API key | (required) |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | (required) |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name | gpt-5.2-chat |
| `AZURE_OPENAI_API_VERSION` | API version | 2024-12-01-preview |
| `ARI_SYSTEM_PROMPT` | Global system prompt | (empty) |
| `MCP_ENABLED` | Enable MCP orchestration | true |
| `MCP_BASE_URL` | MCP server URL | http://localhost:8100 |
| `MCP_TIMEOUT_SECONDS` | MCP call timeout | 10 |
| `FRONTEND_URL` | CORS allowed origin | http://localhost:3000 |
| `API_KEYS` | Comma-separated API keys for /v1/* | (disabled if unset) |
| `JWT_SECRET` | Secret for JWT signing (Phase 2) | (disabled if unset) |
| `JWT_ALGORITHM` | JWT signing algorithm | HS256 |
| `SESSION_SECRET` | Quart session cookie secret | dev-secret-change-me |
| `AZURE_COSMOSDB_ACCOUNT` | Cosmos DB account name | (disabled if unset) |
| `AZURE_COSMOSDB_ACCOUNT_KEY` | Cosmos DB key | (disabled if unset) |
| `AZURE_COSMOSDB_DATABASE` | Cosmos DB database | db_conversation_history |
| `AZURE_COSMOSDB_SESSIONS_CONTAINER` | Sessions container | sessions |
| `AZURE_BLOB_ACCOUNT_NAME` | Blob storage account | (for file uploads/DOCX) |
| `AZURE_BLOB_ACCOUNT_KEY` | Blob storage key | (for file uploads/DOCX) |

### Required for apps/mcp
| Variable | Purpose | Default |
|----------|---------|---------|
| `AZURE_OPENAI_KEY` | For classify/extraction tools | (required) |
| `AZURE_OPENAI_ENDPOINT` | Azure endpoint | (required) |
| `AZURE_COSMOSDB_*` | Cosmos DB connections | (for buyers/leads) |
| `BRICKED_API_KEY` | Bricked comps API | (for comps) |
| `SCRAPING_BEE_API_KEY` | Web scraping | (for leads/attorneys) |
| `EXA_API_KEY` | Exa search API | (for comps) |
| `AZURE_BLOB_ACCOUNT_NAME` | Blob storage | (for Excel export) |
| `AZURE_BLOB_ACCOUNT_KEY` | Blob storage key | (for Excel export) |

### Required for legacy (reference)
| Variable | Purpose |
|----------|---------|
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | Session store |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Payments |
| `SMTP_SERVER` / `SMTP_USERNAME` / `SMTP_PASSWORD` / `FROM_EMAIL` | Magic link emails |
| `DISCORD_WEBHOOK_URL` | Error reporting |
| `SECRET_KEY` | Session encryption |
| `HOST_URL` | Base URL for magic links |
| `AZURE_SEARCH_*` | Azure Cognitive Search (RAG) |
| All `AZURE_OPENAI_*` prompts | Route-specific system prompts |

---

## PR5 Manual QA Checklist

1. **Login** — Open `http://localhost:3000`, log in via magic link or guest. Confirm session cookie is set and sidebar loads.
2. **Session creation** — Click "New Chat". Verify a new session appears in the sidebar. Check browser network tab: `POST /api/sessions` returns 201.
3. **Chat streaming** — Send a message. Verify the response streams token-by-token without freezing. Check network: `POST /api/chat/openai` with `session_id` returns SSE stream.
4. **Chat history** — Refresh the page, reopen the chat. Verify previous messages reload correctly from `GET /api/sessions/:id/messages`.
5. **Session title** — After the first message, verify the sidebar shows an auto-derived title (not "Untitled"). Check network: `PATCH /api/sessions/:id`.
6. **Delete chat** — Click the delete button on a sidebar chat. Confirm the deletion dialog appears, click Continue. Verify the chat disappears and `DELETE /api/chat?id=` returns 200.
7. **Lead runs** — If lead runs exist, verify the "Lead Runs" sidebar section shows entries with summary, count, and a working "Download" link.
8. **JWT auto-refresh** — (Advanced) Invalidate the JWT by waiting or manually clearing it, then send a chat message. Verify the request succeeds without a 401 error reaching the user (the proxy retries with a fresh token).
