"""
LangGraph Application Entry Point
==================================
Main graph orchestration with dual-mode routing:
1. Simple chat mode - Direct LLM interaction (easter egg feature)
2. Enhanced mode - Full MCP tool orchestration with multi-agent workflow

Routing Logic:
- Uses semantic LLM router to determine if query needs tools
- Routes to appropriate mode based on query complexity
- Supports streaming responses via WebSocket

Author: LangGraph Team
Version: 2.0.0
"""

import sys
import os
from typing import Annotated, TypedDict
import asyncio
import json
from datetime import datetime

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.callbacks import adispatch_custom_event
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.checkpoint.memory import MemorySaver
from fastapi import WebSocket

# Core imports
from core.logger import logger, set_files_message_color
from core import config

# Workflow imports (from same directory)
from .workflow import EnhancedLangGraphWorkflow
from utils import MCPClientManager, llm_client

set_files_message_color('MAGENTA')

# ============================================================================
# ENVIRONMENT SETUP
# ============================================================================

# Load environment variables
load_dotenv()
env_var_key = "OPENAI_API_KEY"
model_path = os.getenv(env_var_key)

# Validate API key presence
if not model_path:
    logger.fatal(f"Fatal Error: '{env_var_key}' environment variable is missing.")
    sys.exit(1)

# ============================================================================
# LLM INITIALIZATION
# ============================================================================

# Initialize OpenAI ChatModel
try:
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )
    logger.info("✅ ChatOpenAI model initialized: gpt-4o")
except Exception as e:
    logger.fatal(f"Fatal Error: Failed to initialize model: {e}")
    sys.exit(1)

# ============================================================================
# MCP CLIENT & WORKFLOW INITIALIZATION
# ============================================================================

# Initialize MCP Client Manager
mcp_client_manager = MCPClientManager(server_url=config.MCP_SERVER_URL)

# Initialize Enhanced Workflow
enhanced_workflow = EnhancedLangGraphWorkflow(
    mcp_client_manager, 
    mcp_server_url=config.MCP_SERVER_URL
)

logger.info("✅ Enhanced workflow initialized")

# ============================================================================
# SIMPLE CHAT GRAPH (Easter Egg Feature)
# ============================================================================

class GraphsState(TypedDict):
    """State for simple chat mode."""
    messages: Annotated[list[AnyMessage], add_messages]

# Build simple graph
graph = StateGraph(GraphsState)

async def conditional_check(state: GraphsState, config: RunnableConfig):
    """
    Check for easter egg keywords in user message.
    
    Triggers easter egg event if keywords like 'LangChain', 'LangGraph' detected.
    """
    messages = state["messages"]
    msg = messages[-1].content
    keywords = ["LangChain", "langchain", "Langchain", "LangGraph", "Langgraph", "langgraph"]
    if any(keyword in msg for keyword in keywords):
        await adispatch_custom_event("on_easter_egg", True, config=config)

def _call_model(state: GraphsState, config: RunnableConfig):
    """
    Call LLM model with current messages.
    
    Simple direct LLM call without tool orchestration.
    """
    messages = state["messages"]
    response = llm.invoke(messages, config=config)
    return {"messages": [response]}

# Configure simple graph
graph.add_node("modelNode", _call_model)
graph.add_node("conditional_check", conditional_check)
graph.add_edge(START, "conditional_check")
graph.add_edge("conditional_check", "modelNode")
graph.add_edge("modelNode", END)

# Compile simple graph with memory
memory = MemorySaver()
graph_runnable = graph.compile(checkpointer=memory)

logger.info("✅ Simple chat graph initialized")

# ============================================================================
# SEMANTIC ROUTING & QUERY PROCESSING
# ============================================================================

async def invoke_our_graph(websocket: WebSocket, data: str, user_uuid: str, use_enhanced: bool = False):
    """
    Main routing function - directs queries to appropriate processing mode.
    
    Routing Strategy:
    1. If use_enhanced=True, force enhanced mode (manual override)
    2. Otherwise, use semantic LLM router to decide based on query content
    3. Route to enhanced mode if tools needed, simple mode otherwise
    
    Enhanced Mode:
    - Full MCP tool orchestration
    - Multi-agent workflow
    - Comprehensive query handling
    - Real-time streaming via WebSocket
    
    Simple Mode:
    - Direct LLM interaction
    - No tool execution
    - Basic streaming
    
    Args:
        websocket: WebSocket connection for streaming responses
        data: User's natural language query
        user_uuid: User session identifier
        use_enhanced: Manual override to force enhanced mode
    """
    # Layer 1: Semantic Router - Use LLM to decide if query needs tools
    # This replaces brittle keyword matching with intelligent semantic understanding
    # Benefits:
    # - Handles variations: "kaput", "stuck", "wonky" vs hardcoded "failed", "error"
    # - Context-aware: "python" (language?) vs "python pod" (infrastructure)
    # - Flexible: No need to maintain massive keyword lists
    
    # Determine routing mode
    if use_enhanced:
        # Manual override to enhanced mode
        use_enhanced_mode = True
        logger.info(f"🎯 Enhanced mode manually enabled for: {data[:50]}...")
    else:
        # Use semantic LLM router for intelligent decision
        logger.info("🚦 Routing query through semantic LLM router...")
        use_enhanced_mode = await llm_client.should_use_tools(data)
        logger.info(f"🚦 Router decision: use_enhanced={use_enhanced_mode}")
    
    # Route to appropriate processing mode
    if use_enhanced_mode:
        # Enhanced workflow with MCP tools
        await invoke_enhanced_mode(websocket, data, user_uuid)
    else:
        # Simple chat mode
        await invoke_simple_mode(websocket, data, user_uuid)


async def invoke_enhanced_mode(websocket: WebSocket, data: str, user_uuid: str):
    """
    Process query using enhanced workflow with MCP tools.
    
    This mode:
    - Executes full multi-agent workflow
    - Uses MCP tools for data retrieval
    - Provides comprehensive responses
    - Streams results in real-time
    - Sends metadata on completion
    
    Args:
        websocket: WebSocket connection for streaming
        data: User query
        user_uuid: User session ID
    """
    try:
        logger.info(f"🚀 Using enhanced workflow for: {data[:50]}...")
            
        # Process through enhanced workflow with streaming
        result = await enhanced_workflow.process_query(data, user_uuid, websocket=websocket)
        
        # Send enriched response metadata
        response_message = {
            "on_enhanced_response": {
                "response": result.get("response", ""),
                "query_analysis": result.get("query_analysis", {}),
                "execution_summary": result.get("execution_summary", {}),
                "forward_links": result.get("enrichment", {}).get("forward_links", []),
                "recommendations": result.get("enrichment", {}).get("recommendations", [])
            }
        }
        
        # Send completion (streaming already happened during LLM generation)
        try:
            await websocket.send_text(json.dumps(response_message))
            await websocket.send_text(json.dumps({"on_chat_model_end": True}))
            
            logger.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": user_uuid,
                "llm_method": "enhanced_workflow",
                "sent": result.get("response", "")[:100]
            }))
        except Exception as ws_error:
            # WebSocket closed - log but don't fail
            logger.warning(f"⚠️ WebSocket closed during completion: {ws_error}")
        
    except Exception as e:
        import traceback
        logger.error(f"❌ Enhanced workflow error: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        
        # Attempt to send error
        try:
            await websocket.send_text(json.dumps({"error": str(e)}))
        except:
            pass


async def invoke_simple_mode(websocket: WebSocket, data: str, user_uuid: str):
    """
    Process query using simple chat mode (direct LLM).
    
    This mode:
    - Direct LLM interaction without tools
    - Basic streaming
    - Easter egg detection
    - Lightweight and fast
    
    Args:
        websocket: WebSocket connection for streaming
        data: User query
        user_uuid: User session ID
    """
    initial_input = {"messages": data}
    thread_config = {"configurable": {"thread_id": user_uuid}}
    final_text = ""

    async for event in graph_runnable.astream_events(initial_input, thread_config, version="v2"):
        kind = event["event"]

        if kind == "on_chat_model_stream":
            addition = event["data"]["chunk"].content
            final_text += addition
            if addition:
                message = json.dumps({"on_chat_model_stream": addition})
                await websocket.send_text(message)

        elif kind == "on_chat_model_end":
            message = json.dumps({"on_chat_model_end": True})
            logger.info(json.dumps({"timestamp": datetime.now().isoformat(), "uuid": user_uuid, "llm_method": kind, "sent": final_text}))
            await websocket.send_text(message)

        elif kind == "on_custom_event":
            message = json.dumps({event["name"]: event["data"]})
            logger.info(json.dumps({"timestamp": datetime.now().isoformat(), "uuid": user_uuid, "llm_method": kind, "sent": message}))
            await websocket.send_text(message)

