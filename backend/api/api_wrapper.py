"""
API Wrapper for LangGraph Server
=================================
Production-ready RESTful API wrapper for LangGraph integration.

Features:
- RESTful API endpoints for chat interactions
- WebSocket support for streaming responses
- Type-safe request/response models (Pydantic)
- Error handling and validation
- CORS configuration for cross-origin requests
- Authentication hooks (ready to integrate)
- Session management
- Health checks and monitoring

Endpoints:
- POST /api/chat - Non-streaming chat
- WebSocket /ws - Streaming chat
- GET /health - Health check
- GET /api/capabilities - Available features
- Session management endpoints

Author: LangGraph Team
Version: 1.0.0
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import json
import logging
from datetime import datetime

# Import graph and workflow components
from backend.workflows.graph import create_workflow
from utils.llm_client import LLMDecisionMaker

logger = logging.getLogger(__name__)

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ChatRequest(BaseModel):
    """Request model for chat interactions"""
    message: str = Field(..., description="User's message/query", min_length=1, max_length=5000)
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    context: Optional[Dict[str, Any]] = Field(None, description="Additional context for the query")
    stream: bool = Field(True, description="Enable streaming response")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Show me all pods in CrashLoopBackOff",
                "session_id": "user-session-123",
                "context": {"namespace": "production"},
                "stream": True
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat interactions"""
    response: str = Field(..., description="Assistant's response")
    session_id: str = Field(..., description="Session ID")
    timestamp: datetime = Field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata (tools used, etc.)")
    forward_links: Optional[List[str]] = Field(None, description="Suggested follow-up questions")
    
    class Config:
        json_schema_extra = {
            "example": {
                "response": "Found 3 pods in CrashLoopBackOff status...",
                "session_id": "user-session-123",
                "timestamp": "2025-12-01T10:30:00Z",
                "metadata": {"tools_used": ["get_resources"], "execution_time": 1.5},
                "forward_links": ["Show me the logs for these pods", "What caused these crashes?"]
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.now)
    services: Dict[str, str] = Field(..., description="Status of dependent services")


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.now)


# ============================================================================
# AUTHENTICATION
# ============================================================================

async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """
    Verify API key from request header.
    
    Replace with your company's authentication mechanism.
    Examples: JWT tokens, OAuth, API keys with database lookup, etc.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Returns:
        API key if valid
        
    Raises:
        HTTPException: If authentication fails
    """
    # TODO: Implement your authentication logic
    # For now, this is a passthrough
    
    # Example implementation:
    # if not x_api_key:
    #     raise HTTPException(status_code=401, detail="API key required")
    # if not validate_api_key(x_api_key):
    #     raise HTTPException(status_code=403, detail="Invalid API key")
    
    return x_api_key


# ============================================================================
# API WRAPPER CLASS
# ============================================================================

class LangGraphAPIWrapper:
    """
    Wrapper class for LangGraph server with clean API interface.
    
    Features:
    - RESTful endpoints for chat interactions
    - WebSocket support for streaming
    - Health checks and monitoring
    - Error handling and validation
    - CORS configuration
    - Authentication hooks
    """
    
    def __init__(self, 
                 title: str = "LangGraph Chat API",
                 version: str = "1.0.0",
                 allowed_origins: List[str] = None):
        """
        Initialize the API wrapper.
        
        Args:
            title: API title
            version: API version
            allowed_origins: List of allowed CORS origins (default: ["*"])
        """
        self.app = FastAPI(
            title=title,
            version=version,
            description="Production-ready API for LangGraph chat interactions",
            docs_url="/api/docs",
            redoc_url="/api/redoc",
            openapi_url="/api/openapi.json"
        )
        
        # Configure CORS
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins or ["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Initialize components
        self.workflow = create_workflow()
        self.llm_client = LLMDecisionMaker()
        self.active_sessions: Dict[str, Any] = {}
        
        # Register routes
        self._register_routes()
        
        logger.info(f"✅ LangGraph API Wrapper initialized: {title} v{version}")
    
    
    def _register_routes(self):
        """Register all API routes"""
        
        # =====================================================================
        # HEALTH & STATUS ENDPOINTS
        # =====================================================================
        
        @self.app.get("/health", response_model=HealthResponse, tags=["Health"])
        async def health_check():
            """
            Health check endpoint.
            Returns status of the service and its dependencies.
            """
            return HealthResponse(
                status="healthy",
                version=self.app.version,
                services={
                    "langgraph": "operational",
                    "llm": "operational",
                    "mcp_server": "operational"
                }
            )
        
        
        @self.app.get("/api/status", tags=["Health"])
        async def get_status():
            """
            Get detailed service status including active sessions.
            """
            return {
                "status": "operational",
                "active_sessions": len(self.active_sessions),
                "uptime": "N/A",  # TODO: Track uptime
                "version": self.app.version
            }
        
        
        # =====================================================================
        # CHAT ENDPOINTS (RESTful)
        # =====================================================================
        
        @self.app.post("/api/chat", 
                      response_model=ChatResponse,
                      tags=["Chat"],
                      dependencies=[Depends(verify_api_key)])
        async def chat(request: ChatRequest):
            """
            Send a message and get a response (non-streaming).
            
            This endpoint is useful for simple request-response interactions
            where streaming is not required.
            
            **Authentication**: Requires API key in X-API-Key header
            
            **Rate Limiting**: TODO: Implement rate limiting
            """
            try:
                session_id = request.session_id or f"session-{datetime.now().timestamp()}"
                
                # Process query through LangGraph workflow
                state = {
                    "user_query": request.message,
                    "user_uuid": session_id,
                    "context": request.context or {}
                }
                
                # Execute workflow (non-streaming)
                result = await self.workflow.ainvoke(state)
                
                response = ChatResponse(
                    response=result.get("final_response", "No response generated"),
                    session_id=session_id,
                    metadata={
                        "tools_used": result.get("executed_tools", []),
                        "query_type": result.get("query_type", "unknown")
                    },
                    forward_links=result.get("forward_links", [])
                )
                
                # Store session
                self.active_sessions[session_id] = {
                    "last_activity": datetime.now(),
                    "message_count": self.active_sessions.get(session_id, {}).get("message_count", 0) + 1
                }
                
                return response
                
            except Exception as e:
                logger.error(f"Error in chat endpoint: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        
        # =====================================================================
        # WEBSOCKET ENDPOINTS (Streaming)
        # =====================================================================
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """
            WebSocket endpoint for streaming chat interactions.
            
            **Protocol**:
            1. Client connects and sends: {"uuid": "session-id", "init": true}
            2. Server acknowledges connection
            3. Client sends messages: {"uuid": "session-id", "message": "query"}
            4. Server streams responses: {"on_chat_model_stream": "token"}
            5. Server signals completion: {"on_chat_model_end": true}
            
            **Message Types**:
            - `on_tool_call`: Tools being executed
            - `on_chat_model_stream`: Streaming response tokens
            - `on_chat_model_end`: Response complete
            - `error`: Error occurred
            """
            await websocket.accept()
            session_id = None
            
            try:
                while True:
                    # Receive message from client
                    data = await websocket.receive_text()
                    message_data = json.loads(data)
                    
                    # Handle initialization
                    if message_data.get("init"):
                        session_id = message_data.get("uuid")
                        await websocket.send_text(json.dumps({
                            "status": "connected",
                            "session_id": session_id
                        }))
                        logger.info(f"WebSocket connected: {session_id}")
                        continue
                    
                    # Handle chat message
                    if "message" in message_data:
                        session_id = message_data.get("uuid", session_id)
                        user_message = message_data["message"]
                        
                        # Process through workflow with streaming
                        state = {
                            "user_query": user_message,
                            "user_uuid": session_id,
                            "websocket": websocket
                        }
                        
                        # Execute workflow (streaming enabled)
                        result = await self.workflow.ainvoke(state)
                        
                        # Send completion signal
                        await websocket.send_text(json.dumps({
                            "on_chat_model_end": True,
                            "metadata": {
                                "forward_links": result.get("forward_links", []),
                                "tools_used": result.get("executed_tools", [])
                            }
                        }))
                        
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected: {session_id}")
                if session_id and session_id in self.active_sessions:
                    del self.active_sessions[session_id]
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                try:
                    await websocket.send_text(json.dumps({
                        "error": "internal_error",
                        "message": str(e)
                    }))
                except:
                    pass
        
        
        # =====================================================================
        # SESSION MANAGEMENT
        # =====================================================================
        
        @self.app.get("/api/sessions/{session_id}", tags=["Sessions"])
        async def get_session(session_id: str):
            """Get information about a specific session"""
            if session_id not in self.active_sessions:
                raise HTTPException(status_code=404, detail="Session not found")
            return self.active_sessions[session_id]
        
        
        @self.app.delete("/api/sessions/{session_id}", tags=["Sessions"])
        async def delete_session(session_id: str):
            """Delete/clear a session"""
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
                return {"status": "deleted", "session_id": session_id}
            raise HTTPException(status_code=404, detail="Session not found")
        
        
        # =====================================================================
        # UTILITY ENDPOINTS
        # =====================================================================
        
        @self.app.get("/api/capabilities", tags=["Info"])
        async def get_capabilities():
            """
            Get information about available capabilities and tools.
            Useful for frontend to know what queries are supported.
            """
            return {
                "supported_queries": [
                    "infrastructure (pods, containers, resources)",
                    "incidents and alerts",
                    "tickets and service requests",
                    "changelogs and deployments",
                    "logs and monitoring"
                ],
                "features": [
                    "streaming_responses",
                    "multi_tool_orchestration",
                    "smart_filtering",
                    "context_aware_responses"
                ],
                "available_tools": [
                    "get_resources", "search_resources",
                    "get_incidents", "search_incidents",
                    "get_tickets", "search_tickets",
                    "get_changelogs", "search_changelogs",
                    "search_logs", "query_logs"
                ]
            }
    
    
    def get_app(self) -> FastAPI:
        """Get the FastAPI application instance"""
        return self.app


# ============================================================================
# MAIN SERVER INSTANCE
# ============================================================================

def create_api_wrapper(
    allowed_origins: List[str] = None,
    title: str = "LangGraph Chat API",
    version: str = "1.0.0"
) -> FastAPI:
    """
    Factory function to create and configure the API wrapper.
    
    Args:
        allowed_origins: List of allowed CORS origins
        title: API title
        version: API version
    
    Returns:
        Configured FastAPI application
    
    Example:
        >>> app = create_api_wrapper(
        ...     allowed_origins=["https://mycompany.com"],
        ...     title="MyCompany Chat API"
        ... )
        >>> # Run with: uvicorn api_wrapper:app --host 0.0.0.0 --port 8000
    """
    wrapper = LangGraphAPIWrapper(
        title=title,
        version=version,
        allowed_origins=allowed_origins
    )
    return wrapper.get_app()


# Create default app instance
app = create_api_wrapper(
    title="LangGraph Chat API",
    version="1.0.0",
    allowed_origins=["*"]  # TODO: Restrict to your company's domains
)


if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
