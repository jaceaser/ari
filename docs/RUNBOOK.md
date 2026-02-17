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

#### Frontend (required)

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL |
| `API_JWT_EMAIL` | Email for JWT token generation |
| `API_JWT_SECRET` | Shared JWT secret (must match backend) |
| `AUTH_SECRET` | NextAuth session secret |

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
| Sealed session still editable | Frontend not checking status | Verify backend returns `status: "sealed"` on session GET |
