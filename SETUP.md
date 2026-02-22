# ARI Milestone 1-2 Vertical Slice Setup

This guide sets up the minimal backend and frontend needed for the Milestone 1-2 vertical slice.

## Architecture

```
Frontend (Next.js)
    ↓ POST /v1/chat/completions
Backend API (Quart)
    ↓ (mocked response)
Frontend receives SSE stream
```

## Prerequisites

- Python 3.9+
- Node.js 18+ (for frontend)
- Two terminal windows (one for backend, one for frontend)

## Part 1: Backend API Setup

### 1.1 Install and Run Backend

```bash
cd apps/api

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional, defaults work for local dev)
cp .env.example .env

# Start the server (runs on http://localhost:8000)
python app.py
```

You should see:
```
 * Running on http://0.0.0.0:5000
```

### 1.2 Test Backend Endpoint

In another terminal, test the health check:

```bash
curl http://localhost:8000/health
```

Should return:
```json
{
  "status": "ok",
  "timestamp": "...",
  "version": "0.1.0"
}
```

Test the chat endpoint:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2-chat",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }' \
  --no-buffer
```

You should see SSE stream with tokens.

---

## Part 2: Frontend Configuration

### 2.1 Configure Frontend Environment

```bash
cd apps/web

# Copy example env
cp .env.example .env.local

# Edit .env.local and set:
# NEXT_PUBLIC_API_URL=http://localhost:8000

# If using a .env.local file in the repo, update it directly:
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" >> .env.local
```

### 2.2 Run Frontend

```bash
# Install dependencies (if first time)
pnpm install

# Start dev server (runs on http://localhost:3000)
pnpm dev
```

---

## Part 3: End-to-End Test

1. Open http://localhost:3000 in your browser
2. Sign in (or sign up for test account)
3. Start a new chat
4. Type a message (e.g., "Hello")
5. Watch tokens stream in from the backend

You should see the browser network tab showing:
- POST `http://localhost:8000/v1/chat/completions` (Status 200)
- Response type: `text/event-stream`
- Tokens streaming as SSE data

---

## Troubleshooting

### Backend not responding

```bash
# Check if backend is running on port 5000
lsof -i :5000

# Verify CORS is configured
curl -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS http://localhost:8000/v1/chat/completions -v
```

### Frontend not connecting to backend

1. Check `NEXT_PUBLIC_API_URL` in `.env.local` or `.env`
2. Verify backend is running (`curl http://localhost:8000/health`)
3. Check browser console for CORS errors
4. Verify FRONTEND_URL in backend `.env` matches frontend origin

### SSE not streaming properly

- Check that `stream=true` in the request
- Verify `Content-Type: text/event-stream` in response headers
- Ensure no middleware is buffering the response

---

## File Structure

```
apps/
├── api/                         # Python backend
│   ├── app.py                  # Main Quart application
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example            # Environment template
│   ├── README.md               # API documentation
│   └── .gitignore
│
└── web/                         # Next.js frontend
    ├── components/chat.tsx      # Updated to call backend
    ├── .env.example             # Updated with NEXT_PUBLIC_API_URL
    └── ...
```

---

## Next Steps

After Milestone 1-2 validation:

1. **Milestone 2**: Replace mock responses with Azure OpenAI integration
2. **Milestone 3**: Add MCP server and tool registration
3. **Milestone 4**: Implement tool calling and chaining
4. **Milestone 5**: Deploy to Azure (App Service + Static Web Apps)

---

## Key Changes Made

### Backend (`apps/api`)
- ✅ Created `app.py` with Quart framework
- ✅ Implemented `POST /v1/chat/completions` with OpenAI-compatible interface
- ✅ Added SSE streaming with mock responses
- ✅ Configured CORS for `http://localhost:3000`
- ✅ Added `/health` endpoint for monitoring

### Frontend (`apps/web`)
- ✅ Updated `components/chat.tsx` to use `NEXT_PUBLIC_API_URL` environment variable
- ✅ Falls back to internal `/api/chat` if backend URL not configured
- ✅ Updated `.env.example` with new environment variable

---

## Documentation References

- Backend API: [apps/api/README.md](../api/README.md)
- Architecture: [docs/bmad/01-architecture.md](../../docs/bmad/01-architecture.md)
- API Contract: [docs/bmad/03-api-contracts.md](../../docs/bmad/03-api-contracts.md)
