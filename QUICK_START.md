# Quick Reference - Azure OpenAI Backend

## Current Status

✅ **Backend API:** Ready at `http://localhost:8000`
✅ **OpenAI-Compatible:** POST `/v1/chat/completions` with SSE streaming
✅ **Azure OpenAI Integration:** Streaming from GPT-5.2
✅ **MCP Tooling:** Model-driven tool calls to `apps/mcp` (Comps, Education, Leads, etc.)
✅ **Frontend:** Running at `http://localhost:3000`
✅ **Database:** SQLite at `ari.db` (local dev)

## Start Services

```bash
# Terminal 1: MCP
cd apps/mcp
python3 app.py
# → http://localhost:8100/health

# Terminal 2: Backend
cd apps/api
python3 app.py
# → http://localhost:8000/health

# Terminal 3: Frontend  
cd apps/web
npm run dev
# → http://localhost:3000
```

## Test Streaming

```bash
# Test health
curl http://localhost:8000/health

# Test chat
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2-chat",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }' | head -20
```

## Enable Real Azure OpenAI

Edit `apps/api/.env`:

```bash
AZURE_OPENAI_KEY=your-key-here
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
```

Restart backend:
```bash
python3 app.py
```

## Chat Interface

1. Open http://localhost:3000
2. Sign in (guest auth works)
3. Type a message
4. Watch tokens stream in real-time

## Key Files

| File | Purpose |
|------|---------|
| `apps/api/app.py` | Backend API with Azure OpenAI streaming |
| `apps/api/requirements.txt` | API dependencies (`openai`, `httpx`, Quart) |
| `apps/api/.env` | Azure credentials (optional) |
| `apps/web/.env.local` | Frontend config (NEXT_PUBLIC_API_URL, AUTH_SECRET) |
| `AZURE_OPENAI_SETUP.md` | Detailed Azure setup guide |
| `AZURE_OPENAI_MIGRATION.md` | Technical migration details |

## API Endpoint

### POST /v1/chat/completions

**Request:**
```json
{
  "model": "gpt-5.2-chat",
  "messages": [
    {"role": "system", "content": "You are ARI, a real estate AI."},
    {"role": "user", "content": "What's good about real estate?"}
  ],
  "stream": true,
  "temperature": 0.7,
  "max_tokens": 2048
}
```

**Response:** Server-Sent Events

```
data: {"choices": [{"delta": {"content": "Real"}}]}
data: {"choices": [{"delta": {"content": " estate"}}]}
...
data: [DONE]
```

## Environment Variables

### Backend (`apps/api/.env`)

```bash
# Azure OpenAI
AZURE_OPENAI_KEY=<your-key>
AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5.2-chat
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# General
FRONTEND_URL=http://localhost:3000
DEBUG=True
MCP_ENABLED=True
MCP_BASE_URL=http://localhost:8100
```

`apps/api` and `apps/mcp` read only their own local `.env` files (plus process env overrides).

### Frontend (`apps/web/.env.local`)

```bash
# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000

# Authentication
AUTH_SECRET=<generated-secret>

# Database
DATABASE_URL=./ari.db
```

## Troubleshooting

### Port 8000 in use
```bash
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

### Port 3000 in use
```bash
cd apps/web && npm run dev -- -p 3001
```

### Azure credentials not working
- Check `AZURE_OPENAI_KEY` and `AZURE_OPENAI_ENDPOINT` are set
- Verify credentials are correct in Azure Portal
- Check API version is compatible with deployment
- Check `DEBUG=True` in `.env` to see error messages

### Frontend not loading
- Verify `NEXT_PUBLIC_API_URL=http://localhost:8000`
- Check `AUTH_SECRET` is set
- Ensure database file `ari.db` exists

### Chat not working
- Check backend is running: `curl http://localhost:8000/health`
- Check frontend console for errors (DevTools)
- Check Network tab to see API request/response

## Commands

### Backend

```bash
# Start
cd apps/api && python3 app.py

# Install/update dependencies
pip install -r requirements.txt

# Check Python version
python3 --version  # Should be 3.9+
```

### Frontend

```bash
# Start
cd apps/web && npm run dev

# Install/update dependencies  
npm install --legacy-peer-deps

# Build
npm run build

# Run migrations
npm run db:migrate
```

## Architecture

```
Browser (http://localhost:3000)
    ↓ HTTP/SSE
Next.js Frontend (apps/web)
    ↓ POST /v1/chat/completions
Python Backend (apps/api) - Quart
    ↓ GPT-5 tool call planning
MCP Server (apps/mcp) - Quart
    ↓ tool outputs
Python Backend (apps/api) - Quart
    ↓ AsyncAzureOpenAI() final stream
Azure OpenAI API (GPT-5.2)
    ↓ Streaming tokens
Python Backend
    ↓ SSE formatted chunks
Next.js Frontend
    ↓ useChat hook (AI SDK)
Browser UI
    ↓ Real-time token display
```

## What's Working

- ✅ Backend API listens on port 8000
- ✅ OpenAI-compatible `/v1/chat/completions` endpoint
- ✅ SSE streaming (Server-Sent Events)
- ✅ Azure OpenAI integration ready
- ✅ Model-driven MCP tool orchestration
- ✅ Frontend connects via REST API
- ✅ Chat UI with real-time streaming
- ✅ Authentication with guest mode
- ✅ SQLite database for persistence
- ✅ CORS enabled for cross-origin requests

## Next: Verify End-to-End Tool Calls

1. Start `apps/mcp` on port `8100`
2. Start `apps/api` on port `8000`
3. Ask a route-specific prompt (e.g., comps/leads/contracts)
4. Confirm streamed response quality and inspect API logs for tool usage

## Documentation

- **Full Setup:** [AZURE_OPENAI_SETUP.md](AZURE_OPENAI_SETUP.md)
- **Technical Details:** [AZURE_OPENAI_MIGRATION.md](AZURE_OPENAI_MIGRATION.md)
- **API Docs:** [apps/api/README.md](apps/api/README.md)
- **Frontend Setup:** [apps/web](apps/web)
