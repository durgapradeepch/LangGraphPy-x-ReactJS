"""
Tool Execution Agent - Executes MCP tools based on the plan
"""

import logging
from typing import Dict, Any

from core.state import ChatState, add_mcp_result
from utils.mcp_client import MCPClientManager

logger = logging.getLogger(__name__)


class ToolExecutionAgent:
    """
    Agent responsible for executing MCP tools
    """
    
    def __init__(self, mcp_client_manager: MCPClientManager):
        self.name = "ToolExecutionAgent"
        self.mcp_client = mcp_client_manager
        self.max_retries = 2
    
    async def execute_tools(self, state: ChatState) -> ChatState:
        """Execute tools according to the plan"""
        
        try:
            # Skip tool execution for conversational queries
            if state.get("query_type") == "conversational":
                logger.info("💬 Skipping tool execution for conversational query")
                return {
                    **state,
                    "workflow_status": "completed",
                    "current_agent": self.name
                }
            
            tool_plan = state.get("tool_plan", [])
            logger.info(f"🛠️ Executing {len(tool_plan)} tools")
            
            # Execute tools according to plan
            current_state = state
            for tool_info in tool_plan:
                tool_result = await self._execute_single_tool_with_retry(
                    tool_info,
                    current_state
                )
                
                # Add result to state
                current_state = add_mcp_result(
                    current_state,
                    tool_info["name"],
                    tool_result,
                    self.name
                )
            
            # Calculate execution statistics
            mcp_results = current_state.get("mcp_results", [])
            success_count = len([r for r in mcp_results if r.get("success")])
            success_rate = success_count / len(mcp_results) if mcp_results else 0
            
            logger.info(f"✅ Tool execution completed: {success_rate:.2%} success rate")
            
            return {
                **current_state,
                "current_agent": self.name
            }
            
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {str(e)}")
            return {
                **state,
                "error_count": state.get("error_count", 0) + 1,
                "workflow_status": "degraded"
            }
    
    async def _execute_single_tool_with_retry(self, tool_info: Dict[str, Any], state: ChatState) -> Dict[str, Any]:
        """Execute a single tool with retry logic"""
        
        tool_name = tool_info.get("name")
        parameters = tool_info.get("parameters", {})
        
        # Validate required parameters before attempting execution
        if not self._validate_parameters(tool_name, parameters):
            logger.error(f"❌ Tool {tool_name} has invalid or missing required parameters: {parameters}")
            return {
                "success": False,
                "error": f"Missing or invalid required parameters for {tool_name}",
                "tool_name": tool_name
            }
        
        for attempt in range(self.max_retries):
            try:
                logger.info(f"🔧 Executing {tool_name} (attempt {attempt + 1}/{self.max_retries})")
                
                # Get MCP client for this session
                client = await self.mcp_client.get_client(state.get("session_id", "default"))
                
                # Execute the tool
                result = await client.execute_tool(tool_name, parameters)
                
                return result
                
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"⚠️ Tool {tool_name} attempt {attempt + 1} failed: {str(e)}, retrying...")
                else:
                    logger.error(f"❌ Tool {tool_name} failed after {self.max_retries} attempts: {str(e)}")
                    return {
                        "success": False,
                        "error": str(e),
                        "tool_name": tool_name
                    }
    
    def _validate_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        """Validate tool parameters - check for None, undefined, or empty required params"""
        
        # Tools that require resource_id as integer
        resource_id_tools = [
            "get_resource_by_id", "get_resource_tickets", "get_resource_version",
            "get_resource_metadata", "get_changelog_by_resource", 
            "get_changelog_list_by_resource", "get_notifications_by_resource"
        ]
        
        if tool_name in resource_id_tools:
            resource_id = parameters.get("resource_id")
            if resource_id is None or resource_id == "undefined" or resource_id == "":
                logger.warning(f"⚠️ {tool_name} missing valid resource_id: {resource_id}")
                return False
        
        # Tools that require incident_id
        incident_id_tools = ["get_incident_by_id", "get_incident_changelogs", "get_incident_curated"]
        
        if tool_name in incident_id_tools:
            incident_id = parameters.get("incident_id")
            if incident_id is None or incident_id == "undefined" or incident_id == "":
                logger.warning(f"⚠️ {tool_name} missing valid incident_id: {incident_id}")
                return False
        
        # Tools that require ticket_id
        if tool_name == "get_ticket_by_id":
            ticket_id = parameters.get("ticket_id")
            if ticket_id is None or ticket_id == "undefined" or ticket_id == "":
                logger.warning(f"⚠️ {tool_name} missing valid ticket_id: {ticket_id}")
                return False
        
        # Tools that require query parameter
        query_tools = ["search_incidents", "search_resources", "search_tickets", "query_logs", "query_metrics"]
        
        if tool_name in query_tools:
            query = parameters.get("query")
            if query is None or query == "undefined" or query == "":
                logger.warning(f"⚠️ {tool_name} missing valid query: {query}")
                return False
        
        return True
