"""
Enhanced LangGraph Workflow
============================
Intelligent orchestration system with MCP tool integration.

This module provides a sophisticated workflow that:
- Routes user queries through specialized agent nodes
- Orchestrates MCP tool execution with real-time streaming
- Supports comprehensive follow-up queries with dependency detection
- Maintains conversation context across sessions
- Provides enriched responses with forward-link suggestions

Architecture:
    orchestrator_start → query_analysis → tool_execution → 
    comprehensive_check → comprehensive_followup → 
    response_enrichment → orchestrator_finish → END

Author: LangGraph Team
Version: 2.0.0
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

# Core imports
from core.state import ChatState, create_initial_state

# Agent imports
from agents import (
    OrchestratorAgent,
    QueryAnalysisAgent,
    ToolExecutionAgent,
    ResponseEnrichmentAgent,
    ComprehensiveQueryAgent,
)

# Utility imports
from utils import MCPClientManager

logger = logging.getLogger(__name__)


# ============================================================================
# MAIN WORKFLOW CLASS
# ============================================================================

class EnhancedLangGraphWorkflow:
    """
    Enhanced LangGraph workflow with intelligent MCP tool orchestration.
    
    This workflow implements a multi-agent system that:
    1. Analyzes incoming queries semantically
    2. Plans and executes MCP tools dynamically
    3. Performs comprehensive follow-up queries when needed
    4. Enriches responses with context and suggestions
    
    Attributes:
        mcp_client (MCPClientManager): Client for MCP tool execution
        mcp_server_url (str): URL of the MCP server
        orchestrator (OrchestratorAgent): Workflow orchestration agent
        query_analyzer (QueryAnalysisAgent): Query analysis agent
        tool_executor (ToolExecutionAgent): Tool execution agent
        response_enricher (ResponseEnrichmentAgent): Response enrichment agent
        comprehensive_query (ComprehensiveQueryAgent): Comprehensive query agent
        workflow (StateGraph): LangGraph state machine
        app: Compiled workflow application with checkpointer
    """
    
    def __init__(self, mcp_client_manager: MCPClientManager, mcp_server_url: str = "http://localhost:8080"):
        """
        Initialize the enhanced workflow.
        
        Args:
            mcp_client_manager: Manager for MCP client connections
            mcp_server_url: URL of the MCP server (default: http://localhost:8080)
        """
        self.mcp_client = mcp_client_manager
        self.mcp_server_url = mcp_server_url
        
        # Initialize specialized agents
        self.orchestrator = OrchestratorAgent()
        self.query_analyzer = QueryAnalysisAgent()
        self.tool_executor = ToolExecutionAgent(mcp_client_manager)
        self.response_enricher = ResponseEnrichmentAgent()
        self.comprehensive_query = ComprehensiveQueryAgent()
        
        # Build and compile workflow graph
        self.workflow = self._build_workflow_graph()
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)
        
        # WebSocket reference (set externally, not serialized)
        self._current_websocket = None
        
        logger.info("✅ Enhanced LangGraph Workflow initialized")
    
    # ========================================================================
    # WORKFLOW GRAPH CONSTRUCTION
    # ========================================================================
    
    def _build_workflow_graph(self) -> StateGraph:
        """
        Build the LangGraph state machine workflow.
        
        The workflow follows this path:
        1. orchestrator_start - Initialize workflow and load tools
        2. query_analysis - Analyze user intent and plan tools
        3. tool_execution - Execute planned MCP tools
        4. comprehensive_check - Determine if follow-up needed
        5. comprehensive_followup - Execute follow-up queries if needed
        6. response_enrichment - Enrich response with context
        7. orchestrator_finish - Finalize and update conversation history
        
        Returns:
            StateGraph: Configured workflow graph
        """
        workflow = StateGraph(ChatState)
        
        # Register all workflow nodes
        workflow.add_node("orchestrator_start", self._orchestrator_start_node)
        workflow.add_node("query_analysis", self._query_analysis_node)
        workflow.add_node("tool_execution", self._tool_execution_node)
        workflow.add_node("comprehensive_check", self._comprehensive_check_node)
        workflow.add_node("comprehensive_followup", self._comprehensive_followup_node)
        workflow.add_node("response_enrichment", self._response_enrichment_node)
        workflow.add_node("orchestrator_finish", self._orchestrator_finish_node)
        
        # Set entry point
        workflow.set_entry_point("orchestrator_start")
        
        # Define linear workflow path (sequential execution)
        workflow.add_edge("orchestrator_start", "query_analysis")
        workflow.add_edge("query_analysis", "tool_execution")
        workflow.add_edge("tool_execution", "comprehensive_check")
        workflow.add_edge("comprehensive_check", "comprehensive_followup")
        workflow.add_edge("comprehensive_followup", "response_enrichment")
        workflow.add_edge("response_enrichment", "orchestrator_finish")
        workflow.add_edge("orchestrator_finish", END)
        
        logger.debug("Workflow graph built with 7 nodes and 7 edges")
        return workflow
    
    # ========================================================================
    # WORKFLOW NODE IMPLEMENTATIONS
    # ========================================================================
    
    async def _orchestrator_start_node(self, state: ChatState) -> ChatState:
        """
        Initialize workflow and load available MCP tools.
        
        This node:
        - Loads available MCP tools from the server
        - Initializes workflow metadata
        - Sets up investigation depth tracking
        
        Args:
            state: Current chat state
            
        Returns:
            Updated state with tools and workflow status
        """
        logger.info("🎯 Orchestrator: Starting workflow")
        
        # Fetch available tools from MCP server
        client = await self.mcp_client.get_client()
        tools_response = await client.list_available_tools()
        available_tools = [tool.get("name") for tool in tools_response.get("tools", [])]
        tool_schemas = tools_response.get("tools", [])
        
        logger.info(f"📋 Loaded {len(available_tools)} MCP tools: {', '.join(available_tools[:5])}...")
        
        # Enrich state with tool information
        state_with_tools = {
            **state,
            "available_tools": available_tools,
            "tool_schemas": tool_schemas
        }
        
        # Run orchestrator logic
        updated_state = await self.orchestrator.orchestrate_workflow(state_with_tools)
        
        return {
            **updated_state,
            "workflow_status": "running",
            "investigation_depth": 1
        }
    
    async def _query_analysis_node(self, state: ChatState) -> ChatState:
        """
        Analyze user query and plan tool execution.
        
        This node:
        - Determines query intent and type
        - Plans which MCP tools to execute
        - Prepares tool parameters
        
        Args:
            state: Current chat state with user query
            
        Returns:
            Updated state with query analysis and tool plan
        """
        logger.info("🔍 Query Analysis: Analyzing user query")
        return await self.query_analyzer.analyze_query(state)
    
    async def _tool_execution_node(self, state: ChatState) -> ChatState:
        """
        Execute planned MCP tools.
        
        This node:
        - Executes tools from the tool plan sequentially
        - Sends real-time updates via WebSocket
        - Collects and stores tool execution results
        
        Args:
            state: Current chat state with tool plan
            
        Returns:
            Updated state with tool execution results
        """
        logger.info("🛠️ Tool Execution: Executing MCP tools")
        
        # Notify WebSocket about tool execution (if connected)
        if hasattr(self, '_current_websocket') and self._current_websocket:
            tool_plan = state.get("tool_plan", [])
            if tool_plan:
                import json
                tool_names = [tool.get("name", "Unknown") for tool in tool_plan]
                await self._current_websocket.send_text(json.dumps({
                    "on_tool_call": {
                        "tools": tool_names,
                        "count": len(tool_names)
                    }
                }))
        
        # Execute tools and return results
        return await self.tool_executor.execute_tools(state)
    
    async def _comprehensive_check_node(self, state: ChatState) -> ChatState:
        """
        Determine if comprehensive follow-up queries are needed.
        
        This node:
        - Analyzes tool results for entity IDs
        - Determines if additional detail queries needed
        - Prepares for follow-up execution
        
        Args:
            state: Current chat state with tool results
            
        Returns:
            Updated state with follow-up flags and extracted IDs
        """
        logger.info("🔍 Comprehensive Check: Analyzing if follow-up needed")
        updated_state = await self.comprehensive_query.analyze_and_expand(state)
        
        needs_followup = updated_state.get('needs_comprehensive_followup', False)
        extracted_ids = updated_state.get('extracted_ids', {})
        logger.info(f"🔍 Result: needs_followup={needs_followup}, ids={extracted_ids}")
        
        return updated_state
    
    async def _comprehensive_followup_node(self, state: ChatState) -> ChatState:
        """
        Execute comprehensive follow-up queries if needed.
        
        This node:
        - Checks if follow-up is needed
        - Creates follow-up tool plan
        - Executes follow-up tools
        - Merges results with original tool results
        
        Args:
            state: Current chat state with follow-up flags
            
        Returns:
            Updated state with follow-up results merged
        """
        # Check if follow-up is needed
        needs_followup = state.get("needs_comprehensive_followup", False)
        extracted_ids = state.get("extracted_ids", {})
        
        logger.info(f"🔍 Followup Check: needs={needs_followup}, ids={extracted_ids}")
        
        if not needs_followup:
            logger.info("⏭️  Comprehensive follow-up not needed, skipping")
            return state
        
        logger.info("🔄 Comprehensive Follow-up: Creating and executing follow-up plan")
        
        # Create follow-up plan
        state = await self.comprehensive_query.create_followup_plan(state)
        
        # Execute follow-up tools if plan exists
        followup_plan = state.get("followup_tool_plan", [])
        if not followup_plan:
            logger.info("⚠️ No follow-up plan created, skipping execution")
            return state
        
        # Temporarily replace tool_plan with followup_plan
        original_plan = state.get("tool_plan", [])
        state["tool_plan"] = followup_plan
        
        # Send WebSocket notification about follow-up tools
        if hasattr(self, '_current_websocket') and self._current_websocket:
            import json
            tool_names = [tool.get("name", "Unknown") for tool in followup_plan]
            await self._current_websocket.send_text(json.dumps({
                "on_tool_call": {
                    "tools": tool_names,
                    "count": len(tool_names),
                    "type": "comprehensive_followup"
                }
            }))
        
        # Execute follow-up tools
        logger.info(f"🔄 Executing {len(followup_plan)} comprehensive follow-up tools")
        state = await self.tool_executor.execute_tools(state)
        
        # Restore and merge plans
        state["tool_plan"] = original_plan + followup_plan
        
        # Clear follow-up flags
        state["needs_comprehensive_followup"] = False
        state.pop("followup_tool_plan", None)
        
        logger.info("✅ Comprehensive follow-up execution completed")
        return state
    
    async def _response_enrichment_node(self, state: ChatState) -> ChatState:
        """
        Enrich response with context and suggestions.
        
        This node:
        - Generates final natural language response
        - Adds forward-link suggestions
        - Provides recommendations
        - Streams response to WebSocket if connected
        
        Args:
            state: Current chat state with all tool results
            
        Returns:
            Updated state with enriched final response
        """
        logger.info("✨ Response Enrichment: Enriching response")
        
        # Inject non-serializable context for enrichment
        state_with_context = {**state}
        
        if hasattr(self, '_current_websocket') and self._current_websocket:
            state_with_context["_websocket_ref"] = self._current_websocket
        
        # Add MCP client for similarity search
        if hasattr(self, 'mcp_client') and self.mcp_client:
            client = await self.mcp_client.get_client()
            state_with_context["_mcp_client"] = client
        
        # Enrich response
        result = await self.response_enricher.enrich_response(state_with_context)
        
        # Remove non-serializable references
        result.pop("_websocket_ref", None)
        result.pop("_mcp_client", None)
        
        return result
    
    async def _orchestrator_finish_node(self, state: ChatState) -> ChatState:
        """
        Finalize workflow and update conversation history.
        
        This node:
        - Updates conversation history with current exchange
        - Manages history window (keeps last 10 messages)
        - Marks workflow as completed
        - Adds completion timestamp
        
        Args:
            state: Current chat state with final response
            
        Returns:
            Final state with updated history and completion status
        """
        logger.info("🎯 Orchestrator: Finalizing workflow")
        
        # Update conversation history
        conversation_history = state.get("conversation_history", []).copy()
        conversation_history.extend([
            {"role": "user", "content": state.get("user_query", "")},
            {"role": "assistant", "content": state.get("final_response", "")}
        ])
        
        # Keep only last 10 messages (5 exchanges) for context management
        if len(conversation_history) > 10:
            conversation_history = conversation_history[-10:]
        
        # Finalize state
        final_state = {
            **state,
            "conversation_history": conversation_history,
            "workflow_status": "completed",
            "completion_timestamp": datetime.now().isoformat()
        }
        
        logger.info("✅ Workflow completed successfully")
        return final_state
    
    # ========================================================================\n    # MAIN PROCESSING METHODS
    # ========================================================================
    
    async def process_query(self, user_query: str, session_id: Optional[str] = None, websocket=None) -> Dict[str, Any]:
        """
        Process a user query through the enhanced workflow.
        
        This is the main entry point for query processing. It:
        - Manages conversation sessions with checkpointing
        - Preserves conversation history across interactions
        - Executes the full workflow graph
        - Returns formatted response with metadata
        
        Args:
            user_query: The user's natural language query
            session_id: Optional session ID for conversation continuity
            websocket: Optional WebSocket for streaming responses
            
        Returns:
            Dict containing response, analysis, and execution details
        """
        try:
            logger.info(f"🚀 Processing: '{user_query}'")
            
            # Store websocket separately (not in state - can't be serialized)
            self._current_websocket = websocket
            
            # Determine the thread_id for this conversation
            thread_id = session_id or str(uuid.uuid4())
            thread_config = {"configurable": {"thread_id": thread_id}}
            
            # Try to get existing state from checkpointer to preserve conversation_history
            existing_state = None
            try:
                existing_state = await self.app.aget_state(thread_config)
                if existing_state and existing_state.values:
                    logger.info(f"📚 Found existing conversation state for thread: {thread_id}")
                    # Check if there's conversation history
                    conv_history = existing_state.values.get("conversation_history", [])
                    if conv_history:
                        logger.info(f"💬 Loaded {len(conv_history)} previous messages from conversation history")
            except Exception as e:
                logger.debug(f"No existing state found (new conversation): {e}")
            
            # Create initial state
            initial_state = create_initial_state(user_query, thread_id)
            
            # If we have existing conversation history, preserve it
            if existing_state and existing_state.values:
                existing_history = existing_state.values.get("conversation_history", [])
                if existing_history:
                    initial_state["conversation_history"] = existing_history
                    logger.info(f"✅ Preserved {len(existing_history)} messages from previous conversation")
            
            # Run the workflow
            result = await self.app.ainvoke(
                initial_state,
                config=thread_config
            )
            
            # Format response
            response = self._format_response(result)
            
            logger.info(f"✅ Processing completed successfully")
            return response
            
        except Exception as e:
            logger.error(f"❌ Query processing failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "response": "I encountered an error while processing your request. Please try again.",
                "details": {}
            }
    
    # ========================================================================
    # RESPONSE FORMATTING
    # ========================================================================
    
    def _format_response(self, final_state: ChatState) -> Dict[str, Any]:
        """
        Format the final workflow response.
        
        Extracts key information from the final state and structures it
        for API response or further processing.
        
        Args:
            final_state: Final chat state after workflow completion
            
        Returns:
            Formatted response dictionary with:
            - success: Workflow completion status
            - response: Final natural language response
            - query_analysis: Query type, intent, and confidence
            - execution_summary: Tools executed and success rate
            - enrichment: Forward links and recommendations
            - session_info: Session tracking information
        """
        return {
            "success": final_state.get("workflow_status") == "completed",
            "response": final_state.get("final_response", "Analysis completed"),
            "query_analysis": {
                "query_type": final_state.get("query_type"),
                "intent": final_state.get("intent"),
                "confidence_score": final_state.get("confidence_score", 0)
            },
            "execution_summary": {
                "tools_executed": len(final_state.get("executed_tools", [])),
                "success_rate": self._calculate_success_rate(final_state)
            },
            "enrichment": final_state.get("enrichment_data", {}),
            "session_info": {
                "session_id": final_state.get("session_id"),
                "request_id": final_state.get("request_id"),
                "timestamp": final_state.get("completion_timestamp")
            }
        }
    
    def _calculate_success_rate(self, state: ChatState) -> float:
        """
        Calculate tool execution success rate.
        
        Args:
            state: Chat state with tool execution results
            
        Returns:
            Success rate as float (0.0 to 1.0)
        """
        mcp_results = state.get("mcp_results", [])
        if not mcp_results:
            return 0.0
        
        successful = sum(1 for result in mcp_results if result.get("success"))
        return successful / len(mcp_results)
