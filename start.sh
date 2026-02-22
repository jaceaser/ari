#!/bin/bash
# Quick start script for ARI Milestone 1-2 vertical slice
# Usage: ./start.sh [backend|frontend|both]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE="${1:-both}"

echo "🚀 ARI Vertical Slice Starter"
echo "═══════════════════════════════════════════════════════════"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

start_backend() {
    echo -e "\n${BLUE}Starting Backend API (Quart)...${NC}"
    echo "📁 Directory: $SCRIPT_DIR/apps/api"
    
    cd "$SCRIPT_DIR/apps/api"
    
    # Check if venv exists
    if [ ! -d "venv" ]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate venv
    source venv/bin/activate
    
    # Check if requirements installed
    if ! python3 -c "import quart" 2>/dev/null; then
        echo "📥 Installing requirements..."
        pip install -q -r requirements.txt
    fi
    
    # Create .env if needed
    if [ ! -f ".env" ]; then
        echo "⚙️  Creating .env from template..."
        cp .env.example .env
    fi
    
    echo -e "${GREEN}✅ Backend ready!${NC}"
    echo "🌐 Starting server on http://localhost:8000"
    echo ""
    python3 app.py
}

start_frontend() {
    echo -e "\n${BLUE}Starting Frontend (Next.js)...${NC}"
    echo "📁 Directory: $SCRIPT_DIR/apps/web"
    
    cd "$SCRIPT_DIR/apps/web"
    
    # Check if node_modules exists
    if [ ! -d "node_modules" ]; then
        echo "📦 Installing dependencies..."
        pnpm install
    fi
    
    # Create/update .env.local
    if [ ! -f ".env.local" ]; then
        echo "⚙️  Creating .env.local..."
        echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
    else
        # Check if NEXT_PUBLIC_API_URL is set
        if ! grep -q "NEXT_PUBLIC_API_URL" .env.local; then
            echo "⚙️  Adding NEXT_PUBLIC_API_URL to .env.local..."
            echo "NEXT_PUBLIC_API_URL=http://localhost:8000" >> .env.local
        fi
    fi
    
    echo -e "${GREEN}✅ Frontend ready!${NC}"
    echo "🌐 Starting dev server on http://localhost:3000"
    echo ""
    pnpm dev
}

case "$MODE" in
    backend)
        start_backend
        ;;
    frontend)
        start_frontend
        ;;
    both)
        echo -e "\n${YELLOW}⚠️  To run both, open two terminals and run:${NC}"
        echo -e "   Terminal 1: ${BLUE}./start.sh backend${NC}"
        echo -e "   Terminal 2: ${BLUE}./start.sh frontend${NC}"
        echo ""
        echo -e "${YELLOW}Starting backend in this terminal...${NC}"
        start_backend
        ;;
    *)
        echo "Usage: $0 [backend|frontend|both]"
        echo ""
        echo "Examples:"
        echo "  $0 backend    # Start just the backend API"
        echo "  $0 frontend   # Start just the frontend"
        echo "  $0 both       # Show instructions for running both"
        exit 1
        ;;
esac
