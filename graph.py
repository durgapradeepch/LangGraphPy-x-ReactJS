# Enhanced LangGraph with MCP tool integration and intelligent orchestration
import sys, os
from typing import Annotated, TypedDict
import asyncio

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from langchain_core.callbacks import adispatch_custom_event
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import START, END, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.checkpoint.memory import MemorySaver

from cust_logger import logger, set_files_message_color

# Import enhanced workflow components
from workflow import EnhancedLangGraphWorkflow
from utils.mcp_client import MCPClientManager
import config

set_files_message_color('MAGENTA')  # Set color for logging in this function

# loads and checks if env var exists before continuing to model invocation
load_dotenv()
env_var_key = "OPENAI_API_KEY"
model_path = os.getenv(env_var_key)

# If the API key is missing, log a fatal error and exit the application, no need to run LLM application without model!
if not model_path:
    logger.fatal(f"Fatal Error: The '{env_var_key}' environment variable is missing.")
    sys.exit(1)

# Initialize the ChatModel LLM
try:
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )
except Exception as e:
    logger.fatal(f"Fatal Error: Failed to initialize model: {e}")
    sys.exit(1)

# Initialize MCP Client Manager for enhanced workflow with configured server URL
mcp_client_manager = MCPClientManager(server_url=config.MCP_SERVER_URL)

# Initialize enhanced workflow
enhanced_workflow = EnhancedLangGraphWorkflow(
    mcp_client_manager, 
    mcp_server_url=config.MCP_SERVER_URL
)

# Keep original simple graph for backward compatibility (easter egg feature)
class GraphsState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

graph = StateGraph(GraphsState)

async def conditional_check(state: GraphsState, config: RunnableConfig):
    messages = state["messages"]
    msg = messages[-1].content
    keywords = ["LangChain", "langchain", "Langchain", "LangGraph", "Langgraph", "langgraph"]
    if any(keyword in msg for keyword in keywords):
        await adispatch_custom_event("on_easter_egg", True, config=config)
    pass

def _call_model(state: GraphsState, config: RunnableConfig):
    messages = state["messages"]
    response = llm.invoke(messages, config=config)
    return {"messages": [response]}

graph.add_node("modelNode", _call_model)
graph.add_node("conditional_check", conditional_check)
graph.add_edge(START, "conditional_check")
graph.add_edge("conditional_check", "modelNode")
graph.add_edge("modelNode", END)

memory = MemorySaver()
graph_runnable = graph.compile(checkpointer=memory)

# ===========================================================================================================
# Enhanced invoke function that supports both simple chat and MCP tool orchestration
import json
from datetime import datetime
from fastapi import WebSocket

async def invoke_our_graph(websocket: WebSocket, data: str, user_uuid: str, use_enhanced: bool = False):
    """
    Invoke graph - supports both simple chat and enhanced MCP orchestration
    
    Args:
        websocket: WebSocket connection
        data: User message
        user_uuid: User's conversation ID
        use_enhanced: If True, use enhanced workflow with MCP tools
    """
    
    # Layer 1: Semantic Router - Use LLM to decide if query needs tools
    # This replaces brittle keyword matching with intelligent semantic understanding
    # Benefits:
    # - Handles variations: "kaput", "stuck", "wonky" vs hardcoded "failed", "error"
    # - Context-aware: "python" (language?) vs "python pod" (infrastructure)
    # - Flexible: No need to maintain massive keyword lists
    from utils.llm_client import llm_client
    
    if use_enhanced:
        # Manually forced to use enhanced mode
        use_enhanced_mode = True
        logger.info(f"🎯 Enhanced mode manually enabled for: {data[:50]}...")
    else:
        # Ask the LLM Router to decide based on semantic understanding
        logger.info(f"🚦 Routing query through semantic LLM router...")
        use_enhanced_mode = await llm_client.should_use_tools(data)
    
    if use_enhanced_mode:
        # Use enhanced workflow with MCP tools
        try:
            logger.info(f"🚀 Using enhanced workflow for: {data[:50]}...")
            
            # Process through enhanced workflow with websocket for streaming
            result = await enhanced_workflow.process_query(data, user_uuid, websocket=websocket)
            
            # Send the enriched response metadata (streaming already happened during LLM generation)
            response_message = {
                "on_enhanced_response": {
                    "response": result.get("response", ""),
                    "query_analysis": result.get("query_analysis", {}),
                    "execution_summary": result.get("execution_summary", {}),
                    "forward_links": result.get("enrichment", {}).get("forward_links", []),
                    "recommendations": result.get("enrichment", {}).get("recommendations", [])
                }
            }
            
            # Note: Streaming already happened in real-time during LLM generation
            # No need for post-processing word chunks anymore
            
            # Send completion with metadata
            await websocket.send_text(json.dumps(response_message))
            await websocket.send_text(json.dumps({"on_chat_model_end": True}))
            
            logger.info(json.dumps({
                "timestamp": datetime.now().isoformat(),
                "uuid": user_uuid,
                "llm_method": "enhanced_workflow",
                "sent": result.get("response", "")[:100]
            }))
            
        except Exception as e:
            import traceback
            logger.error(f"❌ Enhanced workflow error: {e}")
            logger.error(f"❌ Traceback: {traceback.format_exc()}")
            # Fallback to simple mode
            await invoke_simple_mode(websocket, data, user_uuid)
    else:
        # Use simple chat mode
        await invoke_simple_mode(websocket, data, user_uuid)


async def invoke_simple_mode(websocket: WebSocket, data: str, user_uuid: str):
    """Original simple chat mode"""
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

