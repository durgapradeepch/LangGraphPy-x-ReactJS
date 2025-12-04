#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Banner
echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}║         ${MAGENTA}LangGraphPy-x-ReactJS${CYAN} - Stop Script              ║${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to stop service on port
stop_port() {
    local port=$1
    local name=$2
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        local pid=$(lsof -ti:$port)
        echo -e "${YELLOW}🛑 Stopping ${name} on port $port (PID: $pid)...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null
        sleep 1
        
        if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
            echo -e "${RED}❌ Failed to stop ${name}${NC}"
            return 1
        else
            echo -e "${GREEN}✅ ${name} stopped${NC}"
            return 0
        fi
    else
        echo -e "${GREEN}✅ ${name} not running${NC}"
        return 0
    fi
}

# Function to stop Docker container
stop_docker_container() {
    local container_name=$1
    
    if command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
        if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
            echo -e "${YELLOW}🛑 Stopping Docker container: ${container_name}...${NC}"
            docker stop $container_name >/dev/null 2>&1
            echo -e "${GREEN}✅ ${container_name} stopped${NC}"
        else
            echo -e "${GREEN}✅ ${container_name} not running${NC}"
        fi
    fi
}

# ============================================================================
# STOP APPLICATION SERVICES
# ============================================================================
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Stopping Application Services${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Stop React Frontend (Port 3000)
stop_port 3000 "React Frontend"

# Stop Python Backend (Port 8000)
stop_port 8000 "Python FastAPI Backend"

# Stop Node.js MCP Server (Port 3001)
stop_port 3001 "Node.js MCP Server"

echo ""

# ============================================================================
# STOP DOCKER CONTAINERS
# ============================================================================
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Stopping Docker Containers${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

if command -v docker &> /dev/null && docker info &> /dev/null 2>&1; then
    # Stop VictoriaLogs
    stop_docker_container "victorialogs"
    
    # Stop VictoriaMetrics (if it was started)
    stop_docker_container "victoriametrics"
    
    echo ""
    echo -e "${BLUE}ℹ️  Note: Docker containers will auto-restart on system reboot${NC}"
    echo -e "${BLUE}   To permanently remove: ${YELLOW}docker rm victorialogs${NC}"
else
    echo -e "${YELLOW}⚠️  Docker not available - skipping container cleanup${NC}"
fi

echo ""

# ============================================================================
# CLEANUP
# ============================================================================
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  Cleanup${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Kill any remaining Python/Node processes
echo -e "${BLUE}🧹 Cleaning up remaining processes...${NC}"

# Kill Python server processes
pkill -f "python.*server.py" 2>/dev/null && echo -e "${GREEN}✅ Python server processes cleaned${NC}"

# Kill Node.js server processes
pkill -f "node.*server.js" 2>/dev/null && echo -e "${GREEN}✅ Node.js server processes cleaned${NC}"

# Kill React/npm processes
pkill -f "react-scripts" 2>/dev/null && echo -e "${GREEN}✅ React processes cleaned${NC}"

# Remove any .log files in the project directory
echo -e "${BLUE}🗑️  Removing log files...${NC}"
find . -maxdepth 2 -name "*.log" -type f -exec rm -f {} \; 2>/dev/null
echo -e "${GREEN}✅ Log files removed${NC}"

echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}║               ${GREEN}✅ ALL SERVICES STOPPED${CYAN}                   ║${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}🔄 To start services again:${NC}"
echo -e "   ${YELLOW}./start.sh${NC}"
echo ""
echo -e "${BLUE}🗑️  To remove Docker containers permanently:${NC}"
echo -e "   ${YELLOW}docker rm victorialogs victoriametrics${NC}"
echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""
