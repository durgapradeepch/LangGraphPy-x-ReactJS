# 🚀 Quick Start Scripts

This directory contains helper scripts to manage all services for the LangGraphPy-x-ReactJS project.

## 📋 Available Scripts

### `start.sh` - Start All Services
Starts all three services in the correct order:
1. Node.js MCP Server (port 3001)
2. Python FastAPI Backend (port 8000)
3. React Frontend (port 3000)

```bash
./start.sh
```

**Features:**
- ✅ Automatically checks and installs dependencies
- ✅ Kills existing processes on ports before starting
- ✅ Creates log files in `logs/` directory
- ✅ Validates that each service started successfully
- ✅ Shows service URLs and log locations

### `stop.sh` - Stop All Services
Stops all running services gracefully.

```bash
./stop.sh
```

**Features:**
- ✅ Stops services on ports 3000, 3001, 8000
- ✅ Cleans up any remaining processes
- ✅ Confirms each service has stopped

### `status.sh` - Check Service Status
Displays the current status of all services.

```bash
./status.sh
```

**Output:**
- Service name and status (✅ running / ❌ stopped)
- Port number and process ID
- Service URL
- Summary of running services

## 📊 Service URLs

When all services are running:

| Service | URL | Description |
|---------|-----|-------------|
| React Frontend | http://localhost:3000 | User interface |
| Python Backend | http://localhost:8000 | FastAPI server with LangGraph |
| Node.js MCP Server | http://localhost:3001 | MCP tools (Neo4j, Manifest API, etc.) |

## 📝 Logs

All service logs are stored in the `logs/` directory:
- `logs/Node.js MCP Server.log`
- `logs/Python Backend.log`
- `logs/React Frontend.log`

View logs in real-time:
```bash
tail -f logs/*.log
```

## 🛠️ Troubleshooting

### Services won't start
1. Check if ports are in use: `lsof -i :3000,3001,8000`
2. Stop all services: `./stop.sh`
3. Try starting again: `./start.sh`

### Check logs for errors
```bash
# View specific service log
cat logs/Python\ Backend.log

# Watch logs in real-time
tail -f logs/*.log
```

### Manual port cleanup
```bash
# Kill all services on their ports
lsof -ti:3000,3001,8000 | xargs kill -9
```

## 🔄 Typical Workflow

```bash
# 1. Start all services
./start.sh

# 2. Check status
./status.sh

# 3. Work on your project...

# 4. Stop when done
./stop.sh
```

## ⚙️ Requirements

- Python 3.x with venv
- Node.js and npm
- All dependencies in `requirements.txt` and `package.json`

The `start.sh` script will automatically check and install dependencies if missing.
