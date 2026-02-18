# ARI Runbook

## Local Development

### Prerequisites

- Node.js 20+
- Python 3.11+
- pnpm 9+

### 1. Backend (apps/api)

```bash
cd apps/api

# Copy and fill in env vars
cp .env.example .env.local
# Required: AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT
# Optional: AZURE_OPENAI_DEPLOYMENT (default: gpt-5.2-chat)
# Optional: API_KEYS (comma-separated list for key auth)
# Optional: JWT_SECRET (enables JWT auth for session endpoints)
# Optional: AZURE_STORAGE_* (enables file upload to Azure Blob)
# Optional: COSMOS_* (enables Cosmos DB persistence)

# Install dependencies
pip install -r requirements.txt

# Run
python app.py
# Starts on http://localhost:8000
# Health check: GET http://localhost:8000/health
```

### 2. Frontend (apps/web)

```bash
cd apps/web

# Install dependencies
pnpm install

# Configure env
cp .env.example .env.local
# Required for external backend mode:
#   NEXT_PUBLIC_API_URL=http://localhost:8000
#   API_JWT_EMAIL=demo@example.com
#   API_JWT_SECRET=<same as backend JWT_SECRET>
# Auth (NextAuth):
#   AUTH_SECRET=<random string>

# Run dev server
pnpm dev
# Starts on http://localhost:3000
```

### 3. Verify

1. Open http://localhost:3000
2. You should be auto-logged in as a guest
3. Type a message and verify streaming works
4. Check backend logs for request flow

## Production Deployment

### Environment Variables

#### Backend (required)

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_DEPLOYMENT` | Model deployment name (default: `gpt-5.2-chat`) |
| `AZURE_OPENAI_API_VERSION` | API version (default: `2024-12-01-preview`) |
| `JWT_SECRET` | Shared secret for JWT auth between web and API |

#### Backend (optional)

| Variable | Description |
|----------|-------------|
| `API_KEYS` | Comma-separated API keys for Bearer auth |
| `COSMOS_ENDPOINT` | Cosmos DB endpoint for session persistence |
| `COSMOS_KEY` | Cosmos DB key |
| `COSMOS_DATABASE` | Cosmos DB database name |
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Blob connection string for file uploads |
| `AZURE_STORAGE_CONTAINER` | Blob container name (default: `uploads`) |
| `ARI_SYSTEM_PROMPT` | Global system prompt override |
| `MCP_SERVER_URL` | MCP server URL for tool orchestration |
| `RATE_LIMIT` | Requests per window (default: 60) |
| `FRONTEND_URL` | Frontend URL for magic link emails (default: `http://localhost:3000`) |
| `AZURE_COMMUNICATION_ENDPOINT` | Azure Communication Services connection string for magic link email |
| `AZURE_COMMUNICATION_SENDER` | Sender address for magic link email (default: `DoNotReply@reilabs.ai`) |
| `STRIPE_SECRET_KEY` | Stripe API secret key |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `STRIPE_PRICE_ID` | Stripe Price ID for subscription checkout |

#### Frontend (required)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL |
| `API_JWT_EMAIL` | Email for JWT token generation |
| `API_JWT_SECRET` | Shared JWT secret (must match backend) |
| `AUTH_SECRET` | NextAuth session secret |

#### Frontend (optional)

| Variable | Description |
|----------|-------------|
| `COOKIE_DOMAIN` | Cookie domain for cross-subdomain auth (e.g. `.reilabs.ai`) |
| `STRIPE_PRICE_ID` | Stripe Price ID (enables subscription enforcement in chat) |

---

## Azure App Service Deployment

### Architecture

Three App Services (Linux, B1/B2 tier):

| Service | Runtime | Port | Startup Command |
|---------|---------|------|----------------|
| `ari-api` | Python 3.11 | 8000 | `bash startup.sh` |
| `ari-mcp` | Python 3.11 | 8100 | `bash startup.sh` |
| `ari-web` | Node 20 | 3000 | `bash startup.sh` |

### Deploy Steps

1. **API backend** (`apps/api`):
   - Create Python 3.11 App Service
   - Set startup command: `bash startup.sh`
   - Configure env vars (see Backend tables above)
   - Set `ALLOWED_ORIGINS=https://app.reilabs.ai`
   - Set `MCP_SERVER_URL` to internal MCP service URL

2. **MCP server** (`apps/mcp`):
   - Create Python 3.11 App Service
   - Set startup command: `bash startup.sh`
   - Typically internal-only (not public-facing)

3. **Web frontend** (`apps/web`):
   - Build locally: `cd apps/web && pnpm build`
   - Deploy the `.next/standalone` directory
   - Copy `public/` and `.next/static` into the standalone dir
   - Set startup command: `bash startup.sh`
   - Set `NEXT_PUBLIC_API_URL=https://api.reilabs.ai`
   - Set `COOKIE_DOMAIN=.reilabs.ai` for cross-subdomain cookies

### Custom Domain Setup

- `app.reilabs.ai` → Web frontend App Service
- `api.reilabs.ai` → API backend App Service
- Set `COOKIE_DOMAIN=.reilabs.ai` so NextAuth cookies work across both subdomains
- Set `ALLOWED_ORIGINS=https://app.reilabs.ai` on the API

### Startup Validation

The backend validates required env vars at startup and fails fast with a clear error if `AZURE_OPENAI_KEY` or `AZURE_OPENAI_ENDPOINT` are missing.

### Rate Limiting

- 60 requests/minute per client (sliding window)
- Keyed by API key when auth is active, or client IP (via `X-Forwarded-For`) when behind a proxy
- `/health` and `/` are exempt
- Returns `429 Too Many Requests` with `retry_after` header

### Health Check

```bash
curl http://localhost:8000/health
# Returns: { "status": "ok", "timestamp": "...", "version": "...", "mcp_enabled": true/false }
```

### Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 401 on all requests | JWT_SECRET mismatch | Ensure same secret on both web and API |
| "Missing required environment variables" at startup | Env not loaded | Check `.env.local` exists and has required vars |
| Messages cut off | max_tokens too low | Increase `max_tokens` (default: 16384) |
| Streaming freezes | Network/proxy timeout | Check proxy timeout settings (need >60s for SSE) |
| Rate limited (429) | Too many requests | Wait for `retry_after` seconds or increase `RATE_LIMIT` |
| File upload fails | Azure Blob not configured | Set `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_STORAGE_CONTAINER` |
