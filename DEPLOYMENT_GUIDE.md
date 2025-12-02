# LangGraph API Wrapper - Deployment Guide

## Overview

This guide explains how to deploy the LangGraph API wrapper for integration with your company's frontend.

## Architecture

```
┌─────────────────┐
│  Frontend       │
│  (React/Vue/    │
│   Angular)      │
└────────┬────────┘
         │ HTTP/WebSocket
         │
┌────────▼────────────────────┐
│  API Wrapper                │
│  - REST Endpoints           │
│  - WebSocket Streaming      │
│  - Authentication           │
│  - CORS Configuration       │
└────────┬────────────────────┘
         │
┌────────▼────────────────────┐
│  LangGraph Workflow         │
│  - Query Analysis           │
│  - Tool Orchestration       │
│  - Response Generation      │
└────────┬────────────────────┘
         │
┌────────▼────────────────────┐
│  MCP Server (Port 3001)     │
│  - 47 Tools                 │
│  - Data Access              │
└─────────────────────────────┘
```

## Quick Start

### 1. Basic Setup

```bash
# Start the API wrapper server
python api_wrapper.py

# Server will start on http://localhost:8000
# API docs available at: http://localhost:8000/api/docs
```

### 2. Using with Uvicorn (Production)

```bash
# Install uvicorn if not already installed
pip install uvicorn[standard]

# Run with production settings
uvicorn api_wrapper:app --host 0.0.0.0 --port 8000 --workers 4
```

### 3. Configuration Options

```python
# Custom configuration
from api_wrapper import create_api_wrapper

app = create_api_wrapper(
    title="MyCompany Chat API",
    version="1.0.0",
    allowed_origins=[
        "https://app.mycompany.com",
        "https://internal.mycompany.com"
    ]
)
```

## API Endpoints

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/status` | GET | Detailed status |
| `/api/chat` | POST | Send message (non-streaming) |
| `/api/capabilities` | GET | Get available features |
| `/api/sessions/{id}` | GET | Get session info |
| `/api/sessions/{id}` | DELETE | Delete session |
| `/api/docs` | GET | Interactive API documentation |
| `/api/redoc` | GET | ReDoc documentation |

### WebSocket Endpoint

| Endpoint | Protocol | Description |
|----------|----------|-------------|
| `/ws` | WebSocket | Streaming chat interface |

## Authentication

### Adding API Key Authentication

Edit `api_wrapper.py` to enable authentication:

```python
# In verify_api_key function (line ~70)
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    # Your authentication logic
    VALID_API_KEYS = {
        "key-123": "frontend-team",
        "key-456": "mobile-team"
    }
    
    if not x_api_key:
        raise HTTPException(status_code=401, detail="API key required")
    
    if x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return VALID_API_KEYS[x_api_key]
```

### Using JWT Tokens

```python
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt

security = HTTPBearer()

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid token")

# Apply to endpoints
@app.post("/api/chat", dependencies=[Depends(verify_token)])
async def chat(request: ChatRequest):
    ...
```

## CORS Configuration

### Development (Allow All Origins)

```python
app = create_api_wrapper(allowed_origins=["*"])
```

### Production (Specific Origins)

```python
app = create_api_wrapper(
    allowed_origins=[
        "https://app.mycompany.com",
        "https://internal-tool.mycompany.com",
        "https://mobile-app.mycompany.com"
    ]
)
```

### Advanced CORS

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.mycompany.com"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
    max_age=3600,
)
```

## Deployment Options

### Option 1: Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["uvicorn", "api_wrapper:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

Build and run:

```bash
docker build -t langgraph-api .
docker run -p 8000:8000 -e OPENAI_API_KEY=your-key langgraph-api
```

### Option 2: Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MCP_SERVER_URL=http://mcp-server:3001
    depends_on:
      - mcp-server
    restart: unless-stopped

  mcp-server:
    build: ./mcp-server
    ports:
      - "3001:3001"
    restart: unless-stopped
```

Run:

```bash
docker-compose up -d
```

### Option 3: Kubernetes

Create `k8s-deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: langgraph-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: langgraph-api
  template:
    metadata:
      labels:
        app: langgraph-api
    spec:
      containers:
      - name: api
        image: your-registry/langgraph-api:latest
        ports:
        - containerPort: 8000
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: openai-secret
              key: api-key
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "2Gi"
            cpu: "2000m"
---
apiVersion: v1
kind: Service
metadata:
  name: langgraph-api
spec:
  selector:
    app: langgraph-api
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: LoadBalancer
```

Deploy:

```bash
kubectl apply -f k8s-deployment.yaml
```

### Option 4: AWS Lambda (Serverless)

Use Mangum adapter:

```python
# lambda_handler.py
from mangum import Mangum
from api_wrapper import app

handler = Mangum(app)
```

Deploy with AWS SAM or Serverless Framework.

## Environment Variables

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional
MCP_SERVER_URL=http://localhost:3001
LOG_LEVEL=info
WORKERS=4
API_TITLE="MyCompany Chat API"
API_VERSION="1.0.0"
```

## Monitoring & Logging

### Add Logging

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Add Metrics (Prometheus)

```python
from prometheus_fastapi_instrumentator import Instrumentator

app = create_api_wrapper()
Instrumentator().instrument(app).expose(app)
```

### Add Tracing (OpenTelemetry)

```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = create_api_wrapper()
FastAPIInstrumentor.instrument_app(app)
```

## Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/chat")
@limiter.limit("10/minute")
async def chat(request: ChatRequest):
    ...
```

## Load Balancing

### Nginx Configuration

```nginx
upstream langgraph_backend {
    least_conn;
    server localhost:8001;
    server localhost:8002;
    server localhost:8003;
    server localhost:8004;
}

server {
    listen 80;
    server_name api.mycompany.com;

    location / {
        proxy_pass http://langgraph_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # WebSocket support
    location /ws {
        proxy_pass http://langgraph_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

## Testing

```bash
# Run health check
curl http://localhost:8000/health

# Test chat endpoint
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me all pods", "stream": false}'

# Load test with Apache Bench
ab -n 1000 -c 10 http://localhost:8000/health

# Load test with hey
hey -n 1000 -c 10 http://localhost:8000/health
```

## Security Checklist

- [ ] Enable API key authentication
- [ ] Restrict CORS to specific origins
- [ ] Use HTTPS in production (TLS/SSL)
- [ ] Implement rate limiting
- [ ] Add request validation
- [ ] Enable audit logging
- [ ] Set up monitoring and alerts
- [ ] Use environment variables for secrets
- [ ] Implement session timeout
- [ ] Add input sanitization

## Troubleshooting

### WebSocket Connection Issues

```javascript
// Check if WebSocket is supported
if (!window.WebSocket) {
    console.error('WebSocket not supported');
}

// Handle connection errors
ws.onerror = (error) => {
    console.error('WebSocket error:', error);
};
```

### CORS Errors

```python
# Ensure CORS is configured correctly
app = create_api_wrapper(
    allowed_origins=["https://your-frontend.com"]
)
```

### Memory Issues

```bash
# Increase worker memory
uvicorn api_wrapper:app --workers 4 --limit-max-requests 1000
```

## Support

For issues or questions:
1. Check API documentation: `http://localhost:8000/api/docs`
2. Review logs: `tail -f server.log`
3. Contact backend team

## Next Steps

1. ✅ Deploy API wrapper
2. ✅ Configure authentication
3. ✅ Test with frontend team
4. ✅ Set up monitoring
5. ✅ Enable rate limiting
6. ✅ Deploy to production
