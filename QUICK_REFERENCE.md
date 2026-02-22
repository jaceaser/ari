# ARI Vertical Slice - Quick Reference

## 📋 Files Created/Modified

### New Backend Files
```
apps/api/
├── app.py                 ✨ Quart API with /v1/chat/completions endpoint
├── requirements.txt       ✨ Dependencies: quart, pydantic, python-dotenv
├── .env.example          ✨ Config template (FRONTEND_URL, DEBUG)
├── .gitignore            ✨ Python-specific ignores
└── README.md             ✨ API documentation with examples
```

### New Root Documentation
```
SETUP.md                   ✨ Full step-by-step setup guide
IMPLEMENTATION_SUMMARY.md  ✨ Detailed implementation notes
start.sh                   ✨ Bash startup script (macOS/Linux)
start.bat                  ✨ Batch startup script (Windows)
```

### Modified Frontend Files
```
apps/web/
├── components/chat.tsx    ✏️  Updated to use NEXT_PUBLIC_API_URL
└── .env.example          ✏️  Added NEXT_PUBLIC_API_URL variable
```

---

## 🚀 Quick Start (Choose One)

### Option A: Using Start Scripts (Recommended)

**macOS/Linux:**
```bash
# Terminal 1: Start backend
./start.sh backend

# Terminal 2: Start frontend
./start.sh frontend
```

**Windows:**
```cmd
# Command Prompt 1: Start backend
start.bat backend

# Command Prompt 2: Start frontend
start.bat frontend
```

### Option B: Manual Setup

**Backend:**
```bash
cd apps/api
python3 -m venv venv
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt
python3 app.py
```

**Frontend:**
```bash
cd apps/web
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" >> .env.local
pnpm dev
```

---

## ✅ After Startup

| URL | Purpose |
|-----|---------|
| http://localhost:8000/health | Backend health check |
| http://localhost:8000/v1/chat/completions | Chat API endpoint |
| http://localhost:3000 | Frontend web app |

---

## 🧪 Test the Integration

### 1. Backend Test (in another terminal)
```bash
curl http://localhost:8000/health
```

Should return:
```json
{"status":"ok","timestamp":"...","version":"0.1.0"}
```

### 2. Chat Test
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model":"gpt-5.2-chat",
    "messages":[{"role":"user","content":"Hello"}],
    "stream":true
  }'
```

Should stream SSE responses.

### 3. Frontend Test
1. Open http://localhost:3000
2. Sign in
3. Send a chat message
4. Watch streaming response appear

---

## 🔧 Configuration

### Backend (.env in apps/api/)
```
FRONTEND_URL=http://localhost:3000    # CORS origin
DEBUG=False                           # Debug mode
```

### Frontend (.env.local in apps/web/)
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Leave `NEXT_PUBLIC_API_URL` empty to use internal `/api/chat`.

---

## 📊 Architecture

```
┌──────────────────────┐
│   Frontend (3000)    │
│   ↓                  │
│ POST /v1/chat/completions
│ (CORS enabled)       │
│   ↓                  │
├──────────────────────┤
│   Backend (5000)     │
│   Quart API          │
│   Mocked responses   │
│   SSE streaming      │
└──────────────────────┘
```

---

## 🐛 Troubleshooting

| Issue | Solution |
|-------|----------|
| Port 5000 in use | Kill process: `lsof -i :5000`, then `kill -9 <PID>` |
| Port 3000 in use | Change frontend port: `pnpm dev -- -p 3001` |
| CORS errors | Check `FRONTEND_URL` in backend `.env` |
| API not responding | Ensure `NEXT_PUBLIC_API_URL` is set correctly |
| `python: command not found` | Use `python3` instead or alias it |
| `pnpm: command not found` | Install pnpm: `npm install -g pnpm` |

---

## 📚 Documentation

- **Setup Guide**: [SETUP.md](SETUP.md)
- **Implementation Details**: [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)
- **API Docs**: [apps/api/README.md](apps/api/README.md)
- **Architecture**: [docs/bmad/01-architecture.md](docs/bmad/01-architecture.md)
- **API Contract**: [docs/bmad/03-api-contracts.md](docs/bmad/03-api-contracts.md)

---

## ✨ What Works Now

✅ Backend API running and responding  
✅ Frontend configured to call backend  
✅ SSE streaming working  
✅ CORS enabled for local development  
✅ Health check endpoint  
✅ Mocked responses (deterministic for testing)  

---

## 🎯 Next Phases

- **Milestone 2**: Azure OpenAI integration
- **Milestone 3**: MCP tool server
- **Milestone 4**: Agent tool-calling loop
- **Milestone 5**: Azure cloud deployment

---

## 💡 Key Points

- **No breaking changes** - Frontend still works without backend URL set
- **Environment config** - All hardcoded values now configurable
- **OpenAI compatible** - Can swap mocked responses for real models
- **SSE streaming** - Real-time token delivery
- **CORS configured** - Works across localhost domains
- **Well documented** - Setup guides for all use cases

---

## 📞 Support

For issues or questions, refer to:
1. Check [SETUP.md](SETUP.md) troubleshooting section
2. Check [apps/api/README.md](apps/api/README.md) for API details
3. Review [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details
