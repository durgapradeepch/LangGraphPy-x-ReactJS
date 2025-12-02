#!/bin/bash

# Kill any existing processes
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:3001 | xargs kill -9 2>/dev/null
lsof -ti:3000 | xargs kill -9 2>/dev/null

# Start Python backend server
cd /Users/pradeep/LangGraphPy-x-ReactJS
source venv/bin/activate
nohup python server.py > server.log 2>&1 &
echo "Started Python backend (port 8000)"

# Start Node.js MCP server
nohup node server.js > mcp_server.log 2>&1 &
echo "Started Node.js MCP server (port 3001)"

# Start React frontend
cd frontend
nohup npm start > frontend.log 2>&1 &
echo "Started React frontend (port 3000)"

# Wait and verify
sleep 5
echo ""
echo "✅ All servers started:"
echo "  - Python Backend: http://localhost:8000"
echo "  - Node.js MCP: http://localhost:3001"
echo "  - React Frontend: http://localhost:3000"
