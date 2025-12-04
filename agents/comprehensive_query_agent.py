"""
Comprehensive Query Agent - Handles multi-step comprehensive queries
Extracts IDs from search results and creates follow-up queries for complete information
"""
import json
from typing import Dict, Any, List

from core.logger import logger


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
        Analyze if the query needs expansion based on:
        1. Query analysis (comprehensive flag)
        2. Scope (single item queries benefit from comprehensive data)
        3. Search results (if we found an ID, we can get complete details)
        """
        try:
            user_query = state.get("user_query", "").lower()
            context_data = state.get("context_data", {})
            query_analysis = context_data.get("query_analysis", {})
            llm_analysis = query_analysis.get("llm_analysis", {})
            
            # Check multiple signals for comprehensive intent
            is_comprehensive = llm_analysis.get("comprehensive", False)
            scope = llm_analysis.get("scope", "")
            intent = llm_analysis.get("intent", "").lower()
            is_multi_entity = llm_analysis.get("multi_entity", False)
            
            # Comprehensive signals
            comprehensive_keywords = [
                "everything", "all details", "all information", "complete", 
                "comprehensive", "tell me about", "full details", "tell me everything",
                "get details", "full status", "complete info"
            ]
            has_comprehensive_keyword = any(keyword in user_query for keyword in comprehensive_keywords)
            
            # 🔗 Cross-entity linking signals - queries that ask for relationships
            cross_entity_keywords = [
                "and their", "and its", "with their", "with its",
                "related", "linked", "associated", "affected",
                "along with", "together with"
            ]
            has_cross_entity_keyword = any(keyword in user_query for keyword in cross_entity_keywords)
            
            # Intent signals - "get details", "tell me about" often want comprehensive data
            detailed_intent_keywords = ["get details", "tell me about", "full", "complete", "all"]
            wants_details = any(keyword in intent for keyword in detailed_intent_keywords)
            
            # Decide if we need comprehensive followup
            should_expand = (
                is_comprehensive or 
                has_comprehensive_keyword or 
                (scope == "single" and wants_details) or
                (is_multi_entity and has_cross_entity_keyword)  # 🔗 NEW: Multi-entity with cross-links
            )
            
            if not should_expand:
                logger.info(f"⏭️  Not a comprehensive query (comprehensive={is_comprehensive}, scope={scope}, intent={intent}, multi_entity={is_multi_entity})")
                return state
            
            # Check if we have search results with IDs
            mcp_results = state.get("mcp_results", [])
            extracted_ids = self._extract_ids_from_results(mcp_results, llm_analysis)
            
            if not extracted_ids:
                logger.info("⏭️  No IDs found in search results, skipping expansion")
                return state
            
            # Log the type of expansion detected
            has_cross_links = "linked_resource_ids" in extracted_ids or "linked_incident_ids" in extracted_ids
            if has_cross_links:
                logger.info(f"🔗 Cross-entity linking detected! Will fetch linked entities.")
            else:
                logger.info(f"📋 Single-entity comprehensive query detected.")
            
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
            logger.info(f"🔄 Comprehensive query detected (comprehensive={is_comprehensive}, scope={scope}) with IDs: {extracted_ids}")
            
            # Update state to indicate we need a follow-up comprehensive query
            state["needs_comprehensive_followup"] = True
            state["extracted_ids"] = extracted_ids
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Comprehensive query analysis failed: {e}")
            return state
    
    def _extract_ids_from_results(self, mcp_results: List[Dict], llm_analysis: Dict) -> Dict[str, Any]:
        """
        Extract resource/incident IDs from search results AND cross-entity references.
        Returns dict with resource_id, incident_id, linked_resources, linked_incidents, etc.
        
        Cross-Entity Linking:
        - Incidents → resource_mapping array → Linked resources
        - Resources → Can link to changelogs, tickets, notifications
        - Tickets → resource_id, incident_id → Linked entities
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
                
                # Extract from search_incidents - including cross-entity resource links
                elif "search_incidents" in tool_name:
                    incidents = data.get("sample", []) or data.get("incidents", [])
                    if incidents and len(incidents) > 0:
                        incident = incidents[0]
                        incident_id = incident.get("id")
                        if incident_id:
                            extracted["incident_id"] = incident_id
                            extracted["incident_title"] = incident.get("title")
                            logger.info(f"✅ Extracted incident_id: {incident_id} ({incident.get('title')})")
                        
                        # 🔗 CROSS-ENTITY LINKING: Extract linked resource IDs from incident
                        resource_mapping = incident.get("resource_mapping", [])
                        if resource_mapping and isinstance(resource_mapping, list):
                            # Store linked resource IDs for follow-up queries
                            extracted["linked_resource_ids"] = resource_mapping
                            logger.info(f"🔗 Cross-entity link: Incident {incident_id} → Resources {resource_mapping}")
                
                # Extract from search_tickets - including cross-entity links
                elif "search_tickets" in tool_name or "ticket" in tool_name.lower():
                    tickets = data.get("tickets", [])
                    if tickets and len(tickets) > 0:
                        ticket = tickets[0]
                        ticket_id = ticket.get("id")
                        if ticket_id:
                            extracted["ticket_id"] = ticket_id
                            logger.info(f"✅ Extracted ticket_id: {ticket_id}")
                        
                        # 🔗 CROSS-ENTITY LINKING: Extract linked resource/incident from ticket
                        if ticket.get("resourceId"):
                            if "linked_resource_ids" not in extracted:
                                extracted["linked_resource_ids"] = []
                            extracted["linked_resource_ids"].append(ticket.get("resourceId"))
                            logger.info(f"🔗 Cross-entity link: Ticket {ticket_id} → Resource {ticket.get('resourceId')}")
                        
                        if ticket.get("incidentId"):
                            if "linked_incident_ids" not in extracted:
                                extracted["linked_incident_ids"] = []
                            extracted["linked_incident_ids"].append(ticket.get("incidentId"))
                            logger.info(f"🔗 Cross-entity link: Ticket {ticket_id} → Incident {ticket.get('incidentId')}")
            
            return extracted
            
        except Exception as e:
            logger.error(f"❌ ID extraction failed: {e}")
            return {}
    
    async def create_followup_plan(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a comprehensive tool plan using the extracted IDs.
        This is called after initial search if needs_comprehensive_followup is True.
        
        Supports both:
        1. Single-entity comprehensive (e.g., "everything about resource X")
        2. Cross-entity linking (e.g., "incidents and their affected resources")
        """
        try:
            if not state.get("needs_comprehensive_followup"):
                return state
            
            extracted_ids = state.get("extracted_ids", {})
            if not extracted_ids:
                return state
            
            # Build comprehensive tool plan based on extracted IDs
            followup_tools = []
            
            # Single-entity comprehensive resource query
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
            
            # Single-entity comprehensive incident query
            if "incident_id" in extracted_ids:
                incident_id = extracted_ids["incident_id"]
                followup_tools.extend([
                    {"name": "get_incident_by_id", "parameters": {"incident_id": incident_id}},
                    {"name": "get_incident_changelogs", "parameters": {"incident_id": incident_id}}
                ])
                logger.info(f"📋 Created comprehensive incident plan for ID: {incident_id}")
            
            # 🔗 CROSS-ENTITY LINKING: Linked resource IDs from incidents/tickets
            if "linked_resource_ids" in extracted_ids:
                linked_resources = extracted_ids["linked_resource_ids"]
                # Limit to first 5 resources to avoid overwhelming the system
                for resource_id in linked_resources[:5]:
                    followup_tools.append({
                        "name": "get_resource_by_id", 
                        "parameters": {"resource_id": resource_id}
                    })
                logger.info(f"🔗 Cross-entity plan: Fetching {len(linked_resources[:5])} linked resources")
            
            # 🔗 CROSS-ENTITY LINKING: Linked incident IDs from tickets
            if "linked_incident_ids" in extracted_ids:
                linked_incidents = extracted_ids["linked_incident_ids"]
                # Limit to first 5 incidents
                for incident_id in linked_incidents[:5]:
                    followup_tools.append({
                        "name": "get_incident_by_id",
                        "parameters": {"incident_id": incident_id}
                    })
                logger.info(f"🔗 Cross-entity plan: Fetching {len(linked_incidents[:5])} linked incidents")
            
            if followup_tools:
                # Add follow-up tools to the plan
                state["followup_tool_plan"] = followup_tools
                logger.info(f"✅ Follow-up plan created with {len(followup_tools)} tools")
            
            return state
            
        except Exception as e:
            logger.error(f"❌ Follow-up plan creation failed: {e}")
            return state
