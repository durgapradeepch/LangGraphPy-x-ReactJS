#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  LangGraphPy-x-ReactJS Service Status${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Function to check service status
check_service() {
    local port=$1
    local name=$2
    local url=$3
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        local pid=$(lsof -ti:$port)
        echo -e "${GREEN}✅ $name${NC}"
        echo -e "   Port: $port | PID: $pid"
        echo -e "   URL: ${BLUE}$url${NC}"
    else
        echo -e "${RED}❌ $name${NC}"
        echo -e "   Port: $port | ${RED}Not Running${NC}"
    fi
    echo ""
}

# Check all services
check_service 3000 "React Frontend    " "http://localhost:3000"
check_service 8000 "Python Backend    " "http://localhost:8000"
check_service 3001 "Node.js MCP Server" "http://localhost:3001"

# Summary
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

running_count=0
for port in 3000 8000 3001; do
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        ((running_count++))
    fi
done

if [ $running_count -eq 3 ]; then
    echo -e "${GREEN}  All services are running! (3/3)${NC}"
elif [ $running_count -eq 0 ]; then
    echo -e "${RED}  No services are running (0/3)${NC}"
    echo -e "${YELLOW}  Run ./start.sh to start all services${NC}"
else
    echo -e "${YELLOW}  Some services are not running ($running_count/3)${NC}"
    echo -e "${YELLOW}  Run ./stop.sh then ./start.sh to restart all${NC}"
fi

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
