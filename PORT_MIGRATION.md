# Port 5000 → 8000 Migration

## Issue
Port 5000 was in use by macOS's ControlCenter process, preventing the backend API from starting.

## Solution
Changed the backend API from port 5000 to port 8000 across the entire project.

## Changes Made

### Backend
- Updated [apps/api/app.py](apps/api/app.py) - Port changed to 8000

### Documentation Updated
- [SETUP.md](SETUP.md) - All port references updated
- [apps/api/README.md](apps/api/README.md) - All port references updated  
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - All port references updated
- [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) - All port references updated
- [apps/web/.env.example](apps/web/.env.example) - Comment updated

### Startup Scripts Updated
- [start.sh](start.sh) - All port references updated
- [start.bat](start.bat) - All port references updated

## Verification
✅ API running successfully on `http://localhost:8000`
✅ Health endpoint responding
✅ Chat endpoint streaming SSE responses

## New Configuration

### Backend
```
http://localhost:8000/health
http://localhost:8000/v1/chat/completions
```

### Frontend
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Next Steps
Start the vertical slice with:
```bash
./start.sh backend  # Terminal 1
./start.sh frontend # Terminal 2
```
