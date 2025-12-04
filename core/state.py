"""
State management for LangGraph workflow with MCP tool integration
"""

import uuid
from typing import TypedDict, Optional, Dict, Any, List
from datetime import datetime


class ChatState(TypedDict):
    """Complete state structure for the chat orchestration workflow"""
    
    # Request metadata
    user_query: str
    session_id: str
    request_id: str
    timestamp: str
    
    # Query analysis
    query_type: str  # "incident_analysis", "exploration", "root_cause", "conversational"
    intent: str
    entities: List[Dict[str, Any]]
    confidence_score: float
    specificity_level: str  # "low", "medium", "high"
    query_analysis: Optional[Dict[str, Any]]
    
    # Tool planning and execution
    available_tools: List[str]
    tool_plan: List[Dict[str, Any]]  # [{"name": str, "parameters": Dict}]
    execution_plan: Optional[Dict[str, Any]]
    execution_strategy: str  # "single", "sequential", "parallel"
    executed_tools: List[str]
    current_tool_index: int
    
    # Multi-query execution
    multi_query_results: Dict[str, Any]
    aggregated_context: Dict[str, Any]
    sub_query_id: Optional[str]
    
    # MCP results
    mcp_results: List[Dict[str, Any]]
    
    # Context and metadata
    context_data: Dict[str, Any]
    conversation_history: List[Dict[str, str]]  # Previous user/assistant messages
    
    # Analysis results
    incident_analysis: Optional[Dict[str, Any]]
    root_cause_analysis: Optional[Dict[str, Any]]
    timeline_data: Optional[List[Dict[str, Any]]]
    
    # Response construction
    enrichment_data: Dict[str, Any]
    forward_links: List[str]
    annotations: List[str]
    final_response: str
    
    # Orchestration metadata
    workflow_status: str  # "running", "completed", "failed", "paused"
    current_agent: str
    error_count: int
    retry_attempts: int
    
    # Quality and confidence tracking
    data_quality_score: float
    response_completeness: float
    investigation_depth: int
    
    # Comprehensive query handling
    needs_comprehensive_followup: bool
    extracted_ids: Dict[str, Any]
    followup_tool_plan: List[Dict[str, Any]]
    
    completion_timestamp: Optional[str]
    multi_query_summary: Optional[Dict[str, Any]]


def create_initial_state(user_query: str, session_id: Optional[str] = None) -> ChatState:
    """Create initial state for a new chat request"""
    
    if not session_id:
        session_id = str(uuid.uuid4())
    
    return {
        # Request metadata
        "user_query": user_query,
        "session_id": session_id,
        "request_id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(),
        
        # Query analysis
        "query_type": "general",
        "intent": "unknown",
        "entities": [],
        "confidence_score": 0.0,
        "specificity_level": "medium",
        "query_analysis": None,
        
        # Tool planning and execution
        "available_tools": [],
        "tool_plan": [],
        "execution_plan": None,
        "execution_strategy": "single",
        "executed_tools": [],
        "current_tool_index": 0,
        
        # Multi-query execution
        "multi_query_results": {},
        "aggregated_context": {},
        "sub_query_id": None,
        
        # MCP results
        "mcp_results": [],
        
        # Context and metadata
        "context_data": {},
        "conversation_history": [],
        
        # Analysis results
        "incident_analysis": None,
        "root_cause_analysis": None,
        "timeline_data": None,
        
        # Response construction
        "enrichment_data": {},
        "forward_links": [],
        "annotations": [],
        "final_response": "",
        
        # Orchestration metadata
        "workflow_status": "initialized",
        "current_agent": "orchestrator",
        "error_count": 0,
        "retry_attempts": 0,
        
        # Quality and confidence tracking
        "data_quality_score": 0.0,
        "response_completeness": 0.0,
        "investigation_depth": 0,
        
        # Comprehensive query handling
        "needs_comprehensive_followup": False,
        "extracted_ids": {},
        "followup_tool_plan": [],
        
        "completion_timestamp": None,
        "multi_query_summary": None
    }


def update_state_context(state: ChatState, key: str, value: Any) -> ChatState:
    """Update context data in state"""
    updated_state = state.copy()
    if "context_data" not in updated_state:
        updated_state["context_data"] = {}
    updated_state["context_data"][key] = value
    return updated_state


def add_mcp_result(state: ChatState, tool_name: str, result: Any, agent_name: str) -> ChatState:
    """Add MCP tool result to state"""
    updated_state = state.copy()
    
    mcp_result = {
        "tool_name": tool_name,
        "result": result,
        "success": result.get("success", False) if isinstance(result, dict) else True,
        "timestamp": datetime.now().isoformat(),
        "agent": agent_name
    }
    
    if "mcp_results" not in updated_state or updated_state["mcp_results"] is None:
        updated_state["mcp_results"] = []
    
    updated_state["mcp_results"].append(mcp_result)
    
    # Update executed tools list
    if "executed_tools" not in updated_state or updated_state["executed_tools"] is None:
        updated_state["executed_tools"] = []
    
    if tool_name not in updated_state["executed_tools"]:
        updated_state["executed_tools"].append(tool_name)
    
    return updated_state


def calculate_state_health(state: ChatState) -> Dict[str, Any]:
    """Calculate overall state health metrics"""
    
    mcp_results = state.get("mcp_results", [])
    total_tools = len(mcp_results)
    successful_tools = sum(1 for r in mcp_results if r.get("success", False))
    
    return {
        "tool_success_rate": successful_tools / total_tools if total_tools > 0 else 0.0,
        "error_count": state.get("error_count", 0),
        "workflow_status": state.get("workflow_status", "unknown"),
        "investigation_depth": state.get("investigation_depth", 0),
        "data_quality_score": state.get("data_quality_score", 0.0)
    }
