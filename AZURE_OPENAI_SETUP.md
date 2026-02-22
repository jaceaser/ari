# Azure OpenAI GPT-5.2 Integration

The ARI backend now integrates with Azure OpenAI for real streaming chat completions.

## Configuration

### Environment Variables

Set these in `apps/api/.env`:

```bash
# Required
AZURE_OPENAI_KEY=<your-azure-openai-api-key>
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/

# Optional (defaults provided)
AZURE_OPENAI_DEPLOYMENT=gpt-5.2-chat
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Frontend and debug settings
FRONTEND_URL=http://localhost:3000
DEBUG=True
```

### Getting Azure OpenAI Credentials

1. Go to [Azure Portal](https://portal.azure.com)
2. Create or access your Azure OpenAI resource
3. Copy the **API Key** from "Keys and Endpoint" section
4. Copy the **Endpoint** URL

Example endpoint: `https://my-ari-resource.openai.azure.com/`

## API Endpoint

### POST /v1/chat/completions

OpenAI-compatible streaming endpoint.

**Request:**
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2-chat",
    "messages": [
      {"role": "system", "content": "You are ARI, a real estate AI assistant."},
      {"role": "user", "content": "Tell me about market trends"}
    ],
    "stream": true,
    "temperature": 0.7,
    "max_tokens": 2048
  }'
```

**Response:** Server-Sent Events (SSE) stream

```
data: {"id": "chatcmpl-...", "object": "text_completion.chunk", "created": 1770605359, "model": "gpt-5.2-chat", "choices": [{"index": 0, "delta": {"content": "Market"}, "finish_reason": null}]}

data: {"id": "chatcmpl-...", "object": "text_completion.chunk", "created": 1770605359, "model": "gpt-5.2-chat", "choices": [{"index": 0, "delta": {"content": " trends"}, "finish_reason": null}]}

...

data: [DONE]
```

## Fallback Behavior

If Azure OpenAI credentials are not configured, the backend will:
- Log a debug message: `[DEBUG] Azure OpenAI not configured`
- Automatically fall back to mock responses
- Continue streaming in the same OpenAI-compatible format

This allows development without Azure credentials while maintaining the same API contract.

## Testing

### Health Check
```bash
curl http://localhost:8000/health
```

### List Endpoints
```bash
curl http://localhost:8000/
```

### Chat Test (with mock fallback)
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2-chat",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }' | head -5
```

## Frontend Integration

The frontend at `apps/web` calls the backend via:

```typescript
const response = await fetch(`${apiUrl}/v1/chat/completions`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    model: "gpt-5.2-chat",
    messages,
    stream: true,
    temperature: 0.7,
    max_tokens: 2048
  })
});
```

The response is an SSE stream parsed by the frontend's `useChat` hook from `@ai-sdk/react`.

## Architecture

### Request Flow

```
Frontend (Next.js)
    ↓ POST /v1/chat/completions (SSE)
Backend (Quart)
    ↓ AsyncAzureOpenAI.chat.completions.create(stream=True)
Azure OpenAI API
    ↓ Streaming response
Backend (yields SSE chunks)
    ↓ SSE formatted delta tokens
Frontend (streams tokens to UI)
```

### Key Features

- ✅ **OpenAI-compatible API** - Works with any OpenAI client library
- ✅ **SSE streaming** - Real-time token-by-token responses
- ✅ **Fallback to mock** - Works without Azure credentials for development
- ✅ **Async streaming** - Non-blocking I/O with Quart
- ✅ **CORS enabled** - Frontend can make cross-origin requests
- ✅ **Error handling** - Graceful degradation if Azure is unavailable

## Legacy Reference

The integration is based on the legacy `backend/services/azure_openai.py`:
- Uses `AsyncAzureOpenAI` client for async streaming
- Supports reasoning models like GPT-5 with `max_completion_tokens`
- Configurable API versions (default: `2024-12-01-preview`)
- Production-ready error handling and logging

## Troubleshooting

### "Azure OpenAI not configured"
Set `AZURE_OPENAI_KEY` and `AZURE_OPENAI_ENDPOINT` in `.env`

### No streaming response
- Check `AZURE_OPENAI_DEPLOYMENT` matches your Azure resource
- Verify API version compatibility with your deployment
- Check frontend is requesting with `stream: true`

### CORS errors
- Verify `FRONTEND_URL` in backend `.env` matches frontend URL
- Ensure `POST /v1/chat/completions` has CORS headers

### Slow responses
- Check Azure region latency
- Monitor token/minute quota on Azure resource
- Check API version compatibility with deployment
