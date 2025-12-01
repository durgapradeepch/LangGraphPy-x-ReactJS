#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  Stopping LangGraphPy-x-ReactJS Services${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Function to stop service on port
stop_port() {
    local port=$1
    local name=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo -e "${YELLOW}🛑 Stopping $name on port $port...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null
        sleep 1
        
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
            echo -e "${RED}❌ Failed to stop $name${NC}"
        else
            echo -e "${GREEN}✅ $name stopped${NC}"
        fi
    else
        echo -e "${GREEN}✅ $name already stopped (port $port not in use)${NC}"
    fi
}

# Stop all services
stop_port 3000 "React Frontend"
stop_port 8000 "Python Backend"
stop_port 3001 "Node.js MCP Server"

# Also kill any remaining processes by name
echo ""
echo -e "${YELLOW}🧹 Cleaning up remaining processes...${NC}"

pkill -f "uvicorn server:app" 2>/dev/null && echo -e "${GREEN}   Killed uvicorn${NC}"
pkill -f "node server.js" 2>/dev/null && echo -e "${GREEN}   Killed node server${NC}"
pkill -f "react-scripts start" 2>/dev/null && echo -e "${GREEN}   Killed react-scripts${NC}"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  All services stopped!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
