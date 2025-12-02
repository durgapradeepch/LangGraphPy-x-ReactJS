#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  LangGraphPy-x-ReactJS Startup Script${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0
    else
        return 1
    fi
}

# Function to kill process on port
kill_port() {
    local port=$1
    local name=$2
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port is already in use. Killing existing process...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null
        sleep 2
    fi
}

# Function to check if Docker is running
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed. Please install Docker Desktop.${NC}"
        echo -e "${YELLOW}   Download from: https://www.docker.com/products/docker-desktop${NC}"
        return 1
    fi
    
    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ Docker is not running. Please start Docker Desktop.${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✅ Docker is running${NC}"
    return 0
}

# Function to start VictoriaLogs Docker container
start_victorialogs() {
    echo -e "${BLUE}Checking VictoriaLogs Docker container...${NC}"
    
    local container_name="victorialogs"
    local image="victoriametrics/victoria-logs:latest"
    local port=9428
    
    # Check if container already exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        # Container exists, check if it's running
        if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
            echo -e "${GREEN}✅ VictoriaLogs container is already running${NC}"
            return 0
        else
            # Container exists but not running, start it
            echo -e "${YELLOW}⚠️  Starting existing VictoriaLogs container...${NC}"
            docker start $container_name
            sleep 3
            echo -e "${GREEN}✅ VictoriaLogs container started${NC}"
            return 0
        fi
    else
        # Container doesn't exist, create and start it
        echo -e "${YELLOW}⚠️  Creating VictoriaLogs Docker container...${NC}"
        
        # Create data directory for persistent storage
        mkdir -p "$PROJECT_DIR/victoria-logs-data"
        
        # Pull the latest image
        echo -e "${BLUE}Pulling VictoriaLogs Docker image...${NC}"
        docker pull $image
        
        # Run the container
        docker run -d \
            --name $container_name \
            --restart unless-stopped \
            -p $port:$port \
            -v "$PROJECT_DIR/victoria-logs-data:/victoria-logs-data" \
            $image \
            -storageDataPath=/victoria-logs-data \
            -httpListenAddr=:$port
        
        if [ $? -eq 0 ]; then
            sleep 3
            echo -e "${GREEN}✅ VictoriaLogs container created and started${NC}"
            echo -e "${GREEN}   URL: http://localhost:$port${NC}"
            echo -e "${GREEN}   Data: $PROJECT_DIR/victoria-logs-data${NC}"
            return 0
        else
            echo -e "${RED}❌ Failed to start VictoriaLogs container${NC}"
            return 1
        fi
    fi
}

# Function to start a service
start_service() {
    local name=$1
    local command=$2
    local port=$3
    local log_file="$PROJECT_DIR/logs/${name}.log"
    
    echo -e "${BLUE}Starting $name on port $port...${NC}"
    
    # Create logs directory if it doesn't exist
    mkdir -p "$PROJECT_DIR/logs"
    
    # Kill existing process on port
    kill_port $port "$name"
    
    # Start the service
    eval "$command" > "$log_file" 2>&1 &
    local pid=$!
    
    # Wait a bit and check if process started successfully
    sleep 3
    
    if ps -p $pid > /dev/null 2>&1; then
        if check_port $port; then
            echo -e "${GREEN}✅ $name started successfully (PID: $pid)${NC}"
            echo -e "${GREEN}   Log: $log_file${NC}"
            return 0
        else
            echo -e "${RED}❌ $name started but not listening on port $port${NC}"
            echo -e "${RED}   Check log: $log_file${NC}"
            return 1
        fi
    else
        echo -e "${RED}❌ $name failed to start${NC}"
        echo -e "${RED}   Check log: $log_file${NC}"
        return 1
    fi
}

# Check for Python virtual environment
echo -e "${BLUE}Checking Python environment...${NC}"
if [ ! -d "venv" ]; then
    echo -e "${RED}❌ Virtual environment not found. Creating one...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if required Python packages are installed
echo -e "${BLUE}Checking Python dependencies...${NC}"
if ! python -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Installing Python dependencies...${NC}"
    pip install -r requirements.txt
fi

# Check Node.js dependencies
echo -e "${BLUE}Checking Node.js dependencies...${NC}"
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠️  Installing Node.js dependencies...${NC}"
    npm install
fi

# Check frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠️  Installing frontend dependencies...${NC}"
    cd frontend && npm install && cd ..
fi

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  Starting Services${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check Docker and start VictoriaLogs
if check_docker; then
    start_victorialogs
else
    echo -e "${YELLOW}⚠️  Skipping VictoriaLogs (Docker not available)${NC}"
fi

echo ""

# Start Node.js MCP Server (Port 3001)
start_service "Node.js MCP Server" "node server.js" 3001

# Start Python FastAPI Backend (Port 8000)
echo ""
echo -e "${BLUE}📊 Service URLs:${NC}"
echo -e "   🔹 React Frontend:     ${GREEN}http://localhost:3000${NC}"
echo -e "   🔹 Python Backend:     ${GREEN}http://localhost:8000${NC}"
echo -e "   🔹 Node.js MCP Server: ${GREEN}http://localhost:3001${NC}"
echo -e "   🔹 VictoriaLogs:       ${GREEN}http://localhost:9428${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  All Services Started!${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}📊 Service URLs:${NC}"
echo -e "   🔹 React Frontend:    ${GREEN}http://localhost:3000${NC}"
echo -e "   🔹 Python Backend:    ${GREEN}http://localhost:8000${NC}"
echo -e "   🔹 Node.js MCP Server: ${GREEN}http://localhost:3001${NC}"
echo ""
echo -e "${BLUE}📝 Logs Location:${NC}"
echo -e "   ${PROJECT_DIR}/logs/"
echo ""
echo -e "${BLUE}🛑 To stop all services:${NC}"
echo -e "   Run: ${YELLOW}./stop.sh${NC}"
echo -e "   Or manually: ${YELLOW}lsof -ti:3000,3001,8000 | xargs kill -9${NC}"
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
