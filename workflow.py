"""
Enhanced LangGraph Workflow - Intelligent orchestration with MCP tools
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from state import ChatState, create_initial_state
from orchestrator import OrchestratorAgent
from agents.query_analysis_agent import QueryAnalysisAgent
from agents.tool_execution_agent import ToolExecutionAgent
from agents.response_enrichment_agent import ResponseEnrichmentAgent
from agents.comprehensive_query_agent import ComprehensiveQueryAgent
from utils.mcp_client import MCPClientManager

logger = logging.getLogger(__name__)


class EnhancedLangGraphWorkflow:
    """
    Enhanced LangGraph workflow with intelligent MCP tool orchestration
    """
    
    def __init__(self, mcp_client_manager: MCPClientManager, mcp_server_url: str = "http://localhost:8080"):
        self.mcp_client = mcp_client_manager
        self.mcp_server_url = mcp_server_url
        
        # Initialize agents
        self.orchestrator = OrchestratorAgent()
        self.query_analyzer = QueryAnalysisAgent()
        self.tool_executor = ToolExecutionAgent(mcp_client_manager)
        self.response_enricher = ResponseEnrichmentAgent()
        self.comprehensive_query = ComprehensiveQueryAgent()
        
        # Build the workflow graph
        self.workflow = self._build_workflow_graph()
        
        # Compile with memory checkpointer
        self.memory = MemorySaver()
        self.app = self.workflow.compile(checkpointer=self.memory)
    
    def _build_workflow_graph(self) -> StateGraph:
        """Build the LangGraph state machine workflow"""
        
        # Create the workflow graph
        workflow = StateGraph(ChatState)
        
        # Add nodes for each processing stage
        workflow.add_node("orchestrator_start", self._orchestrator_start_node)
        workflow.add_node("query_analysis", self._query_analysis_node)
        workflow.add_node("tool_execution", self._tool_execution_node)
        workflow.add_node("comprehensive_check", self._comprehensive_check_node)
        workflow.add_node("comprehensive_followup", self._comprehensive_followup_node)
        workflow.add_node("response_enrichment", self._response_enrichment_node)
        workflow.add_node("orchestrator_finish", self._orchestrator_finish_node)
        
        # Set entry point
        workflow.set_entry_point("orchestrator_start")
        
        # Define the workflow path with conditional comprehensive query handling
        workflow.add_edge("orchestrator_start", "query_analysis")
        workflow.add_edge("query_analysis", "tool_execution")
        workflow.add_edge("tool_execution", "comprehensive_check")
        workflow.add_edge("comprehensive_check", "comprehensive_followup")
        workflow.add_edge("comprehensive_followup", "response_enrichment")
        workflow.add_edge("response_enrichment", "orchestrator_finish")
        workflow.add_edge("orchestrator_finish", END)
        
        return workflow
    
    # Node Implementations
    
    async def _orchestrator_start_node(self, state: ChatState) -> ChatState:
        """Orchestrator initialization"""
        logger.info("🎯 Orchestrator: Starting workflow")
        
        # Get available tools from MCP client
        client = await self.mcp_client.get_client()
        tools_response = await client.list_available_tools()
        available_tools = [tool.get("name") for tool in tools_response.get("tools", [])]
        tool_schemas = tools_response.get("tools", [])  # Store full schemas
        logger.info(f"📋 Loaded {len(available_tools)} available MCP tools")
        
        # Add tools to state
        state_with_tools = {
            **state,
            "available_tools": available_tools,
            "tool_schemas": tool_schemas  # Add full schemas
        }
        
        updated_state = await self.orchestrator.orchestrate_workflow(state_with_tools)
        
        return {
            **updated_state,
            "workflow_status": "running",
            "investigation_depth": 1
        }
    
    async def _query_analysis_node(self, state: ChatState) -> ChatState:
        """Query analysis"""
        logger.info("🔍 Query Analysis: Analyzing user query")
        return await self.query_analyzer.analyze_query(state)
    
    async def _tool_execution_node(self, state: ChatState) -> ChatState:
        """Tool execution"""
        logger.info("🛠️ Tool Execution: Executing MCP tools")
        
        # Send tool execution notification to websocket if available
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
        
        return await self.tool_executor.execute_tools(state)
    
    async def _comprehensive_check_node(self, state: ChatState) -> ChatState:
        """Check if comprehensive follow-up is needed"""
        logger.info("🔍 Comprehensive Check: Analyzing if follow-up needed")
        updated_state = await self.comprehensive_query.analyze_and_expand(state)
        logger.info(f"🔍 Comprehensive Check Result: needs_followup={updated_state.get('needs_comprehensive_followup', False)}, extracted_ids={updated_state.get('extracted_ids', {})}")
        return updated_state
    
    async def _comprehensive_followup_node(self, state: ChatState) -> ChatState:
        """Execute comprehensive follow-up tools if needed"""
        
        # Check if follow-up is actually needed
        needs_followup = state.get("needs_comprehensive_followup", False)
        extracted_ids = state.get("extracted_ids", {})
        logger.info(f"🔍 Followup Node Check: needs_followup={needs_followup}, extracted_ids={extracted_ids}")
        logger.info(f"🔍 Full state keys: {list(state.keys())}")
        
        if not needs_followup:
            logger.info("⏭️  Comprehensive follow-up not needed, skipping")
            return state
        
        logger.info("🔄 Comprehensive Follow-up: Creating and executing follow-up plan")
        
        # Create follow-up plan
        state = await self.comprehensive_query.create_followup_plan(state)
        
        # Execute the follow-up tools
        followup_plan = state.get("followup_tool_plan", [])
        if followup_plan:
            # Temporarily replace tool_plan with followup_plan
            original_plan = state.get("tool_plan", [])
            state["tool_plan"] = followup_plan
            
            # Send notification about follow-up tools
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
            
            # Execute the follow-up tools
            logger.info(f"🔄 Executing {len(followup_plan)} comprehensive follow-up tools")
            state = await self.tool_executor.execute_tools(state)
            
            # Restore original plan (now with additional results)
            state["tool_plan"] = original_plan + followup_plan
            
            # Clear follow-up flags
            state["needs_comprehensive_followup"] = False
            state.pop("followup_tool_plan", None)
            
            logger.info("✅ Comprehensive follow-up execution completed")
        
        return state
    
    async def _response_enrichment_node(self, state: ChatState) -> ChatState:
        """Response enrichment"""
        logger.info("✨ Response Enrichment: Enriching response")
        
        # Inject websocket reference if available (as non-serializable context)
        if hasattr(self, '_current_websocket') and self._current_websocket:
            state_with_ws = {**state, "_websocket_ref": self._current_websocket}
            result = await self.response_enricher.enrich_response(state_with_ws)
            # Remove websocket ref before returning (don't serialize it)
            if "_websocket_ref" in result:
                del result["_websocket_ref"]
            return result
        else:
            return await self.response_enricher.enrich_response(state)
    
    async def _orchestrator_finish_node(self, state: ChatState) -> ChatState:
        """Orchestrator finalization"""
        logger.info("🎯 Orchestrator: Finalizing workflow")
        
        # Update conversation history with current interaction
        conversation_history = state.get("conversation_history", []).copy()
        conversation_history.append({
            "role": "user",
            "content": state.get("user_query", "")
        })
        conversation_history.append({
            "role": "assistant", 
            "content": state.get("final_response", "")
        })
        
        # Keep only last 10 messages (5 exchanges) to avoid context overflow
        if len(conversation_history) > 10:
            conversation_history = conversation_history[-10:]
        
        final_state = {
            **state,
            "conversation_history": conversation_history,
            "workflow_status": "completed",
            "completion_timestamp": datetime.now().isoformat()
        }
        
        return final_state
    
    # Main Processing Method
    
    async def process_query(self, user_query: str, session_id: str = None, websocket=None) -> Dict[str, Any]:
        """
        Process a user query through the enhanced workflow
        
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
    
    def _format_response(self, final_state: ChatState) -> Dict[str, Any]:
        """Format the final response"""
        
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
        """Calculate success rate for tool execution"""
        mcp_results = state.get("mcp_results", [])
        if not mcp_results:
            return 0.0
        
        successful = sum(1 for result in mcp_results if result.get("success"))
        return successful / len(mcp_results)
