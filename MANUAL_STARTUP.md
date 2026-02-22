# Manual Startup Guide - ARI Vertical Slice

Due to macOS port conflicts, the backend API now runs on **port 8000** (instead of 5000).

## Quick Start (Manual Steps)

### Terminal 1: Start MCP Server

```bash
cd apps/mcp

# Create virtual environment (first time only)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Start MCP server
python3 app.py
```

You should see MCP listening on:
```
 * Running on http://0.0.0.0:8100
```

### Terminal 2: Start Backend API

```bash
cd apps/api

# Create virtual environment (first time only)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies (first time only)
pip install -r requirements.txt

# Start the server
python3 app.py
```

You should see:
```
 * Serving Quart app 'app'
 * Running on http://0.0.0.0:8000 (CTRL + C to quit)
```

### Terminal 3: Start Frontend

```bash
cd apps/web

# Create .env.local if it doesn't exist
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Install dependencies (first time only)
pnpm install

# Start dev server
pnpm dev
```

You should see:
```
- ready started server on 0.0.0.0:3000, url: http://localhost:3000
```

### Terminal 4 (Optional): Test the API

```bash
# Test health check
curl http://localhost:8000/health

# Test chat streaming
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2-chat",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": true
  }'
```

## Port Information

| Service | URL | Purpose |
|---------|-----|---------|
| MCP Server | http://localhost:8100 | Tool endpoints (Comps, Education, etc.) |
| Backend API | http://localhost:8000 | Quart API server |
| Frontend | http://localhost:3000 | Next.js web app |
| Health Check | http://localhost:8000/health | API status |
| Chat Endpoint | http://localhost:8000/v1/chat/completions | Main streaming endpoint |

## Why Port 8000?

macOS's ControlCenter process was using port 5000, causing conflicts. Port 8000 is commonly used for development and doesn't conflict.

## Environment Configuration

### Backend (`apps/api/.env`)
```
FRONTEND_URL=http://localhost:3000
DEBUG=True
MCP_ENABLED=True
MCP_BASE_URL=http://localhost:8100
```

`apps/api` and `apps/mcp` load configuration from their own local `.env` files. Keep these files populated with the values you want active.

### Frontend (`apps/web/.env.local`)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Troubleshooting

### Port 8000 already in use
```bash
# Kill the process using port 8000
lsof -i :8000 | grep LISTEN | awk '{print $2}' | xargs kill -9
```

### Port 3000 already in use
```bash
# Change frontend port
cd apps/web
pnpm dev -- -p 3001
```

### Virtual environment issues
```bash
# Delete and recreate venv
cd apps/api
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Dependencies not installing
```bash
# Upgrade pip and try again
pip install --upgrade pip
pip install -r requirements.txt
```

## Next Steps

1. Open http://localhost:3000 in your browser
2. Sign in (or create test account)
3. Start a new chat
4. Send a message and watch the response stream in real-time
5. Check Network tab in DevTools to see API calls

## All Documentation Files

- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - Quick commands
- [SETUP.md](SETUP.md) - Full setup guide
- [apps/api/README.md](apps/api/README.md) - API documentation
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - Technical details
- [PORT_MIGRATION.md](PORT_MIGRATION.md) - Port 5000 → 8000 migration notes
