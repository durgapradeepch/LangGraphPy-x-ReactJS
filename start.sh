#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# Banner
echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}║         ${MAGENTA}LangGraphPy-x-ReactJS${CYAN} - Start Script             ║${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Function to check if port is in use
check_port() {
    local port=$1
    lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1
}

# Function to kill process on port
kill_port() {
    local port=$1
    local name=$2
    if check_port $port; then
        echo -e "${YELLOW}⚠️  Port $port in use - stopping existing $name...${NC}"
        lsof -ti:$port | xargs kill -9 2>/dev/null
        sleep 1
    fi
}

# Function to check if Docker is available
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}⚠️  Docker not installed${NC}"
        return 1
    fi
    
    if ! docker info &> /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Docker not running${NC}"
        return 1
    fi
    
    return 0
}

# Function to start Docker container
start_docker_container() {
    local container_name=$1
    local image=$2
    local port=$3
    local data_dir=$4
    local extra_args=$5
    
    echo -e "${BLUE}🐳 Checking Docker container: ${container_name}${NC}"
    
    # Check if container exists and is running
    if docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo -e "${GREEN}✅ ${container_name} already running${NC}"
        return 0
    fi
    
    # Check if container exists but is stopped
    if docker ps -a --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo -e "${CYAN}   Starting existing container...${NC}"
        docker start $container_name >/dev/null 2>&1
        sleep 2
        echo -e "${GREEN}✅ ${container_name} started${NC}"
        return 0
    fi
    
    # Container doesn't exist - create it
    echo -e "${CYAN}   Creating new container...${NC}"
    
    # Create data directory if specified
    if [ -n "$data_dir" ]; then
        mkdir -p "$PROJECT_DIR/$data_dir"
    fi
    
    # Pull image if not exists
    if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${image}$"; then
        echo -e "${CYAN}   Pulling image: $image${NC}"
        docker pull $image >/dev/null 2>&1
    fi
    
    # Build docker run command
    local docker_cmd="docker run -d --name $container_name --restart unless-stopped -p $port:$port"
    
    # Add volume mount if data directory specified
    if [ -n "$data_dir" ]; then
        docker_cmd="$docker_cmd -v $PROJECT_DIR/$data_dir:/$data_dir"
    fi
    
    # Add extra arguments
    if [ -n "$extra_args" ]; then
        docker_cmd="$docker_cmd $image $extra_args"
    else
        docker_cmd="$docker_cmd $image"
    fi
    
    # Run container
    eval $docker_cmd >/dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        sleep 2
        echo -e "${GREEN}✅ ${container_name} created and started${NC}"
        echo -e "${GREEN}   📍 http://localhost:$port${NC}"
        return 0
    else
        echo -e "${RED}❌ Failed to start ${container_name}${NC}"
        return 1
    fi
}

# Function to start a service
start_service() {
    local name=$1
    local command=$2
    local port=$3
    local working_dir=$4
    
    echo -e "${BLUE}🚀 Starting ${name}...${NC}"
    
    # Kill existing process
    kill_port $port "$name"
    
    # Change to working directory if specified
    if [ -n "$working_dir" ]; then
        cd "$PROJECT_DIR/$working_dir"
    else
        cd "$PROJECT_DIR"
    fi
    
    # Start service (redirect output to /dev/null - no log files)
    eval "$command" >/dev/null 2>&1 &
    local pid=$!
    
    # Wait and verify
    sleep 3
    
    if ps -p $pid >/dev/null 2>&1 && check_port $port; then
        echo -e "${GREEN}✅ ${name} started (PID: $pid)${NC}"
        echo -e "${GREEN}   📍 http://localhost:$port${NC}"
        return 0
    else
        echo -e "${RED}❌ ${name} failed to start${NC}"
        return 1
    fi
}

# ============================================================================
# STEP 1: Environment Setup
# ============================================================================
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  STEP 1: Environment Setup${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check Python virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}⚠️  Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate
echo -e "${GREEN}✅ Python virtual environment activated${NC}"

# Install Python dependencies
if ! python -c "import fastapi; import langgraph; import langchain" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Installing Python dependencies...${NC}"
    pip install -q -r requirements.txt
    echo -e "${GREEN}✅ Python dependencies installed${NC}"
else
    echo -e "${GREEN}✅ Python dependencies already installed${NC}"
fi

# Install Node.js dependencies (root)
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}⚠️  Installing Node.js dependencies...${NC}"
    npm install --silent
    echo -e "${GREEN}✅ Node.js dependencies installed${NC}"
else
    echo -e "${GREEN}✅ Node.js dependencies already installed${NC}"
fi

# Install frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo -e "${YELLOW}⚠️  Installing frontend dependencies...${NC}"
    cd frontend && npm install --silent && cd ..
    echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
else
    echo -e "${GREEN}✅ Frontend dependencies already installed${NC}"
fi

echo ""

# ============================================================================
# STEP 2: Docker Containers
# ============================================================================
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  STEP 2: Docker Containers${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

if check_docker; then
    # Start VictoriaLogs
    start_docker_container \
        "victorialogs" \
        "victoriametrics/victoria-logs:latest" \
        "9428" \
        "victoria-logs-data" \
        "-storageDataPath=/victoria-logs-data -httpListenAddr=:9428"
    
    # Start VictoriaMetrics (if needed)
    # Uncomment if you need VictoriaMetrics
    # start_docker_container \
    #     "victoriametrics" \
    #     "victoriametrics/victoria-metrics:latest" \
    #     "8428" \
    #     "victoria-metrics-data" \
    #     "-storageDataPath=/victoria-metrics-data -httpListenAddr=:8428"
    
else
    echo -e "${YELLOW}⚠️  Docker not available - skipping containers${NC}"
    echo -e "${YELLOW}   Install Docker: https://www.docker.com/products/docker-desktop${NC}"
fi

echo ""

# ============================================================================
# STEP 3: Application Services
# ============================================================================
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo -e "${CYAN}  STEP 3: Application Services${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Start Node.js MCP Server (Port 3001)
start_service \
    "Node.js MCP Server" \
    "node backend/mcp_server/server.js" \
    "3001" \
    ""

echo ""

# Start Python FastAPI Backend (Port 8000)
start_service \
    "Python FastAPI Backend" \
    "source venv/bin/activate && python server.py" \
    "8000" \
    ""

echo ""

# Start React Frontend (Port 3000)
start_service \
    "React Frontend" \
    "npm start" \
    "3000" \
    "frontend"

echo ""

# ============================================================================
# SUMMARY
# ============================================================================
echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}║                  ${GREEN}✅ ALL SYSTEMS RUNNING${CYAN}                  ║${NC}"
echo -e "${CYAN}║                                                            ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}📍 Application URLs:${NC}"
echo -e "   ${GREEN}▸${NC} React Frontend:     ${CYAN}http://localhost:3000${NC}"
echo -e "   ${GREEN}▸${NC} Python Backend:     ${CYAN}http://localhost:8000${NC}"
echo -e "   ${GREEN}▸${NC} Node.js MCP Server: ${CYAN}http://localhost:3001${NC}"
echo -e "   ${GREEN}▸${NC} VictoriaLogs:       ${CYAN}http://localhost:9428${NC}"
echo ""
echo -e "${BLUE}🛑 To stop all services:${NC}"
echo -e "   ${YELLOW}./stop.sh${NC}"
echo ""
echo -e "${BLUE}📊 To check service status:${NC}"
echo -e "   ${YELLOW}lsof -i :3000,:3001,:8000,:9428${NC}"
echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
echo ""
