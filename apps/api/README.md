# ARI Backend API

OpenAI-compatible chat endpoint backed by Azure OpenAI streaming, with model-driven MCP tool orchestration.

## Endpoints

- `POST /v1/chat/completions`
  - Request: OpenAI Chat Completions-style body (`model`, `messages`, `stream=true`)
  - Response: SSE stream (`Content-Type: text/event-stream`) with chat completion chunks and final `[DONE]`
- `GET /health`
- `GET /`

## Requirements

- Python 3.9+
- Azure OpenAI deployment (GPT-5.2)
- MCP tool server running (`apps/mcp`)

## Setup

```bash
cd apps/api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create `apps/api/.env`:

```bash
AZURE_OPENAI_KEY=<your-key>
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT=gpt-5.2-chat
AZURE_OPENAI_API_VERSION=2024-12-01-preview
FRONTEND_URL=http://localhost:3000
DEBUG=False

# MCP orchestration
MCP_ENABLED=True
MCP_BASE_URL=http://localhost:8100
MCP_TIMEOUT_SECONDS=10
MCP_TOOL_MAX_ROUNDS=2
MCP_TOOL_MAX_CALLS_PER_ROUND=4
```

## Run

```bash
cd apps/api
python3 app.py
```

Server starts on `http://localhost:8000`.

## Example

```bash
curl -N -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2-chat",
    "messages": [
      {"role": "user", "content": "Run comps on 123 Main St and explain assumptions"}
    ],
    "stream": true,
    "max_tokens": 700
  }'
```

## Notes

- The endpoint requires `stream=true`.
- For GPT-5 deployments, the backend maps `max_tokens` to Azure `max_completion_tokens`.
- CORS is enabled for `FRONTEND_URL`.
- The model can choose and chain MCP tools server-side (frontend does not access MCP).
- MCP tools include route context plus helper extract/search calls (`extract-address`, `extract-city-state`, `buyers-search`, `bricked-comps`) for less rigid tool plans.
- Env loading precedence is: process env > `apps/api/.env`.
- Route/system prompts should be set in `apps/api/.env` and `apps/mcp/.env`.
