"""
Comprehensive Query Agent - Handles multi-step comprehensive queries
Extracts IDs from search results and creates follow-up queries for complete information
"""
import json
from typing import Dict, Any, List
from cust_logger import logger


class ComprehensiveQueryAgent:
    """
    Handles comprehensive queries that need multi-step execution:
    1. Search for resource/incident by name to get ID
    2. Create follow-up plan with comprehensive tools using the extracted ID
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    async def analyze_and_expand(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze if the query needs expansion based on search results.
        If user asked for comprehensive info and we have search results, extract IDs and create follow-up plan.
        """
        try:
            user_query = state.get("user_query", "").lower()
            context_data = state.get("context_data", {})
            query_analysis = context_data.get("query_analysis", {})
            llm_analysis = query_analysis.get("llm_analysis", {})
            
            # Check if this is a comprehensive query
            comprehensive_keywords = [
                "everything", "all details", "all information", "complete", 
                "comprehensive", "tell me about", "full details", "tell me everything"
            ]
            is_comprehensive = any(keyword in user_query for keyword in comprehensive_keywords)
            
            if not is_comprehensive:
                logger.info("⏭️  Not a comprehensive query, skipping expansion")
                return state
            
            # Check if we have search results with IDs
            mcp_results = state.get("mcp_results", [])
            extracted_ids = self._extract_ids_from_results(mcp_results, llm_analysis)
            
            if not extracted_ids:
                logger.info("⏭️  No IDs found in search results, skipping expansion")
                return state
            
            # Check if we already executed comprehensive tools
            executed_tools = state.get("executed_tools", [])
            comprehensive_tools = [
                "get_resource_by_id", "get_resource_version", "get_resource_metadata",
                "get_changelog_by_resource", "get_resource_tickets", "get_notifications_by_resource",
                "get_incident_by_id", "get_incident_changelogs"
            ]
            
            already_comprehensive = any(tool in executed_tools for tool in comprehensive_tools)
            if already_comprehensive:
                logger.info("⏭️  Comprehensive tools already executed, skipping expansion")
                return state
            
            # Create follow-up query with the extracted ID
            logger.info(f"🔄 Comprehensive query detected with extracted IDs: {extracted_ids}")
            
            # Update state to indicate we need a follow-up comprehensive query
            state["needs_comprehensive_followup"] = True
            state["extracted_ids"] = extracted_ids
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Comprehensive query analysis failed: {e}")
            return state
    
    def _extract_ids_from_results(self, mcp_results: List[Dict], llm_analysis: Dict) -> Dict[str, Any]:
        """
        Extract resource/incident IDs from search results.
        Returns dict with resource_id, incident_id, etc.
        """
        extracted = {}
        
        try:
            for result in mcp_results:
                if not result.get("success"):
                    continue
                
                tool_name = result.get("tool_name", "")
                data = result.get("result", {})
                
                # Extract from search_resources
                if "search_resources" in tool_name:
                    resources = data.get("resources", [])
                    if resources and len(resources) > 0:
                        # Take the first matching resource
                        resource = resources[0]
                        resource_id = resource.get("id")
                        if resource_id:
                            extracted["resource_id"] = resource_id
                            extracted["resource_name"] = resource.get("resourceName")
                            logger.info(f"✅ Extracted resource_id: {resource_id} ({resource.get('resourceName')})")
                
                # Extract from search_incidents
                elif "search_incidents" in tool_name:
                    incidents = data.get("sample", []) or data.get("incidents", [])
                    if incidents and len(incidents) > 0:
                        incident = incidents[0]
                        incident_id = incident.get("id")
                        if incident_id:
                            extracted["incident_id"] = incident_id
                            extracted["incident_title"] = incident.get("title")
                            logger.info(f"✅ Extracted incident_id: {incident_id} ({incident.get('title')})")
            
            return extracted
            
        except Exception as e:
            logger.error(f"❌ ID extraction failed: {e}")
            return {}
    
    async def create_followup_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a comprehensive tool plan using the extracted IDs.
        This is called after initial search if needs_comprehensive_followup is True.
        """
        try:
            if not state.get("needs_comprehensive_followup"):
                return state
            
            extracted_ids = state.get("extracted_ids", {})
            if not extracted_ids:
                return state
            
            # Build comprehensive tool plan based on extracted IDs
            followup_tools = []
            
            if "resource_id" in extracted_ids:
                resource_id = extracted_ids["resource_id"]
                followup_tools.extend([
                    {"name": "get_resource_by_id", "parameters": {"resource_id": resource_id}},
                    {"name": "get_resource_version", "parameters": {"resource_id": resource_id}},
                    {"name": "get_resource_metadata", "parameters": {"resource_id": resource_id}},
                    {"name": "get_resource_tickets", "parameters": {"resource_id": resource_id}},
                    {"name": "get_changelog_by_resource", "parameters": {"resource_id": resource_id}},
                    {"name": "get_notifications_by_resource", "parameters": {"resource_id": resource_id}}
                ])
                logger.info(f"📋 Created comprehensive resource plan for ID: {resource_id}")
            
            if "incident_id" in extracted_ids:
                incident_id = extracted_ids["incident_id"]
                followup_tools.extend([
                    {"name": "get_incident_by_id", "parameters": {"incident_id": incident_id}},
                    {"name": "get_incident_changelogs", "parameters": {"incident_id": incident_id}}
                ])
                logger.info(f"📋 Created comprehensive incident plan for ID: {incident_id}")
            
            if followup_tools:
                # Add follow-up tools to the plan
                state["followup_tool_plan"] = followup_tools
                logger.info(f"✅ Follow-up plan created with {len(followup_tools)} tools")
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Follow-up plan creation failed: {e}")
            return state
