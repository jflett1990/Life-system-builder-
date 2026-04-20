#!/bin/bash

# Life System Builder - Full Stack Startup Script

echo "🚀 Starting Life System Builder..."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check for required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  Warning: OPENAI_API_KEY is not set${NC}"
    echo "   Some AI features will not work without this API key."
    echo ""
fi

# Create a named pipe for managing parallel processes
trap 'kill $(jobs -p) 2>/dev/null' EXIT

echo -e "${GREEN}Starting backend (FastAPI on port 8080)...${NC}"
cd /vercel/share/v0-project
uv run main.py &
BACKEND_PID=$!

# Give backend time to start
sleep 3

echo -e "${GREEN}Starting frontend (React + Vite on port 5173)...${NC}"
cd /vercel/share/v0-project/artifacts/life-system-builder
npm run dev &
FRONTEND_PID=$!

echo ""
echo -e "${GREEN}✓ Both services started!${NC}"
echo ""
echo "📱 Frontend: http://localhost:5173"
echo "🔌 Backend API: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

wait
