"""
LLM Client for dynamic decision making throughout the LangGraph workflow
"""

import os
import logging
import json
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class LLMDecisionMaker:
    """
    Centralized LLM client for all decision making in the workflow
    """
    
    def __init__(self):
        # Initialize OpenAI client
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model_name = os.getenv("LLM_MODEL", "gpt-4o")
        self.temperature = 0.1
        
        if self.api_key:
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=2000
            )
            logger.info(f"✅ LLM client initialized with model: {self.model_name}")
        else:
            self.llm = None
            logger.warning("⚠️ No OpenAI API key found - using fallback logic")
    
    def _extract_json_from_response(self, content: str) -> str:
        """Extract JSON from LLM response that might be wrapped in markdown code blocks"""
        content = content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        
        if content.endswith("```"):
            content = content[:-3]
        
        return content.strip()
    
    async def analyze_query_intent(self, user_query: str, available_tools: List[str]) -> Dict[str, Any]:
        """Analyze user query to determine intent and extract entities"""
        
        if not self.llm:
            return self._fallback_query_analysis(user_query)
        
        system_prompt = f"""You are a query analysis expert. Analyze the user's query and extract:
1. Query type: incident_analysis, exploration, root_cause, infrastructure_query, or conversational
2. Intent: what the user wants to accomplish
3. Entities: specific items mentioned (resource IDs, timestamps, severity levels)
4. Search terms: extract key terms for flexible searching (extract service names, application names, keywords)
5. Confidence score (0-1)
6. Specificity level: low, medium, or high
7. Whether this is a multi-part query with multiple sub-questions

Available tools: {{', '.join(available_tools)}}

IMPORTANT QUERY TYPE DETECTION:
- infrastructure_query: Questions about actual infrastructure state (pods, containers, VMs, databases, networks)
  Examples: "show pods in CrashLoopBackOff", "list all running containers", "what resources are down"
  → These require tools like get_resources, search_resources to fetch REAL data
- exploration: General browsing ("show me incidents", "list tickets")
- incident_analysis: Investigating specific outages or problems
- root_cause: "Why did X fail?", "What caused the outage?"
- conversational: Greetings, thanks, unclear questions

CRITICAL: For infrastructure queries, the user wants REAL data from your system, NOT generic instructions!

IMPORTANT: Extract search terms intelligently with AGGRESSIVE variations:
- For "pods in CrashLoopBackOff", extract: ["pod", "crashloopbackoff", "crash", "failed", "error"]
- For "Mit-runtime-api-services", extract: ["runtime", "api", "services", "runtime-api", "aws", "aws-api", "runtime-aws"]
- For "Shopping 3 website", extract: ["shopping", "shopping 3", "website", "shopping3"]
- For "Acme-Cart", extract: ["acme", "cart", "acme-cart", "acmecart"]
- Break hyphenated/compound names into ALL parts: "Mit-runtime-api" → ["runtime", "api", "runtime-api"]
- Include partial matches: "runtime-api" should also try "runtime", "api" individually
- Remove common words: "the", "incident", "about", "on", "describe", "show", "tell", "mit", "acme" (company prefixes)
- Focus on SERVICE names, not company prefixes

Respond ONLY with valid JSON in this exact format:
{{
    "query_type": "incident_analysis|exploration|root_cause|infrastructure_query|conversational",
    "intent": "brief description",
    "entities": [{{"type": "resource", "value": "id"}}],
    "search_terms": ["term1", "term2", "term3"],
    "confidence_score": 0.8,
    "specificity_level": "low|medium|high",
    "is_multi_part": true|false,
    "sub_queries": ["sub-query1", "sub-query2"]
}}"""
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this query: {user_query}"}
            ]
            
            response = self.llm.invoke(messages)
            content = response.content
            
            json_str = self._extract_json_from_response(content)
            analysis = json.loads(json_str)
            
            logger.info(f"🔍 Query analyzed: {analysis.get('query_type')} with confidence {analysis.get('confidence_score')}")
            return analysis
            
        except Exception as e:
            logger.error(f"❌ Query analysis failed: {str(e)}")
            return self._fallback_query_analysis(user_query)
    
    async def plan_tool_sequence(self, query_analysis: Dict[str, Any], tool_schemas: List[Dict[str, Any]], 
                               context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Plan the sequence of tools to execute based on query analysis"""
        
        if not self.llm:
            return self._fallback_tool_planning(query_analysis, [t.get("name") for t in tool_schemas])
        
        # Format tool schemas for the prompt
        tools_info = []
        for tool in tool_schemas:
            tool_desc = f"- **{tool['name']}**: {tool.get('description', '')}"
            if 'inputSchema' in tool and 'properties' in tool['inputSchema']:
                params = tool['inputSchema']['properties']
                required_params = tool['inputSchema'].get('required', [])
                param_details = []
                for param_name, param_info in params.items():
                    param_type = param_info.get('type', 'any')
                    param_desc = param_info.get('description', '')
                    required_marker = " [REQUIRED]" if param_name in required_params else " [OPTIONAL]"
                    param_details.append(f"    * {param_name} ({param_type}){required_marker}: {param_desc}")
                if param_details:
                    tool_desc += "\n  Parameters:\n" + "\n".join(param_details)
            tools_info.append(tool_desc)
        
        tools_with_schemas = '\n'.join(tools_info)
        
        system_prompt = f"""You are a tool execution planner. Based on the query analysis, create a plan of tools to execute.

IMPORTANT: 
1. Use the EXACT parameter names shown in the tool schemas below!
2. Only include REQUIRED parameters - omit OPTIONAL ones unless specifically needed
3. Match parameter types exactly (string, integer, object, array)

Available tools:
{tools_with_schemas}

Query Analysis: {json.dumps(query_analysis)}

CRITICAL: INFRASTRUCTURE QUERIES require fetching REAL data!
If query_type is "infrastructure_query" (e.g., "show pods in CrashLoopBackOff", "list containers"), 
you MUST use tools to query actual resources:
- get_resources: List all resources, optionally filter by resource_type
- search_resources: Search resources by name/keyword (e.g., search for "pod" or specific pod names)
- get_resource_by_id: Get specific resource details if resource_id is known

DO NOT provide generic instructions! Users want ACTUAL data from their infrastructure.

CRITICAL TOOL DISAMBIGUATION:
**LOGS vs CHANGELOGS vs INCIDENTS vs RESOURCES - Choose the RIGHT tool:**
- "search logs", "log entries", "log messages", "system logs", "application logs", "error logs"
  → Use LOG tools: search_logs, query_logs (for VictoriaLogs - raw log data)
- "changes", "deployments", "configuration changes", "IAM changes", "RBAC changes", "what changed", "modifications"
  → Use CHANGELOG tools: search_changelogs, get_changelog_by_resource (for change tracking)
- "incidents", "outages", "downtime", "service down", "alerts", "problems"
  → Use INCIDENT tools: search_incidents, get_incidents (for incident management)
- "pods", "containers", "VMs", "databases", "resources", "infrastructure", "show X resources"
  → Use RESOURCE tools: get_resources, search_resources (for infrastructure inventory)

**Key distinction**: 
- "logs" = raw log entries from VictoriaLogs (use search_logs)
- "changelogs" = configuration/deployment change records (use search_changelogs)
- "incidents" = service outage/problem records (use search_incidents)
- "resources/infrastructure" = actual assets like pods, VMs, databases (use get_resources, search_resources)

CRITICAL SEARCH STRATEGY:
1. Use search_terms from query_analysis for flexible matching
2. For INFRASTRUCTURE queries:
   - get_resources with resource_type filter if type mentioned (e.g., "Container", "VM")
   - search_resources with query parameter to find specific resources by name/keyword
   - Filter results by status, health, or other attributes
3. For LOG searches:
   - search_logs with search_text parameter for simple text searches
   - query_logs with query parameter for complex LogSQL queries
4. For incident searches, try multiple approaches:
   - search_incidents with query parameter using search_terms
   - get_incidents to list all, then filter by search_terms
   - If specific incident ID mentioned, use get_incident_by_id
5. For changelog searches with filters:
   - search_changelogs with severity/provider_key/description
   - search_changelogs_by_event_type for deployment/configuration type filtering
   - get_changelog_by_resource for specific resource's change history
6. Use partial matches and fuzzy search when exact match fails
7. Extract key words: "Mit-runtime-api-services" → search for "runtime", "api", "mit"

Return a JSON array of tools with parameters in this exact format:
[
    {{"name": "tool_name", "parameters": {{"param": "value"}}}},
    {{"name": "another_tool", "parameters": {{}}}}
]

For infrastructure queries about pods/containers:
[
    {{"name": "get_resources", "parameters": {{"resource_type": "Workload"}}}},
    {{"name": "search_resources", "parameters": {{"query": "pod crash"}}}}
]

For incident queries, ALWAYS include search_terms in parameters:
[
    {{"name": "search_incidents", "parameters": {{"query": "space-separated search terms from search_terms array"}}}},
    {{"name": "get_incidents", "parameters": {{}}}}
]

For audit/comprehensive queries (e.g., "audit changes", "show all deployments and who made them"):
[
    {{"name": "get_changelogs", "parameters": {{}}}},
    {{"name": "search_changelogs_by_event_type", "parameters": {{"event_type": "deployment"}}}},
    {{"name": "query_nodes", "parameters": {{"label": "User"}}}}
]

For resource deep-dive queries (e.g., "tell me everything about resource X"):
[
    {{"name": "get_resource_by_id", "parameters": {{"resource_id": X}}}},
    {{"name": "get_resource_metadata", "parameters": {{"resource_id": X}}}},
    {{"name": "get_changelog_by_resource", "parameters": {{"resource_id": X}}}},
    {{"name": "get_notifications_by_resource", "parameters": {{"resource_id": X}}}}
]

Consider:
1. Tool dependencies and execution order
2. Required vs optional parameters  
3. Use search_terms for fuzzy/partial matching
4. For comprehensive queries, plan MULTIPLE tools to get complete picture
5. Context from previous executions: {json.dumps(context) if context else 'None'}"""
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Create the tool execution plan."}
            ]
            
            response = self.llm.invoke(messages)
            content = response.content
            
            json_str = self._extract_json_from_response(content)
            tool_plan = json.loads(json_str)
            
            logger.info(f"📋 Tool plan created: {len(tool_plan)} tools planned")
            return tool_plan
            
        except Exception as e:
            logger.error(f"❌ Tool planning failed: {str(e)}")
            return self._fallback_tool_planning(query_analysis, available_tools)
    
    def _extract_nested_value(self, obj: Any, *paths) -> Any:
        """
        Safely extract nested values from object using multiple possible paths.
        Returns first found value or "Unknown".
        Example: _extract_nested_value(data, "metadata.status.phase", "status", "resourceStatus")
        """
        for path in paths:
            try:
                value = obj
                for key in path.split('.'):
                    if isinstance(value, dict):
                        value = value.get(key)
                    else:
                        value = None
                        break
                if value is not None and value != "":
                    return value
            except (KeyError, TypeError, AttributeError):
                continue
        return "Unknown"
    
    def _preprocess_tool_result(self, result: Dict[str, Any], tool_name: str, search_terms: List[str] = None) -> Dict[str, Any]:
        """Pre-process complex nested data structures for better LLM consumption"""
        
        if search_terms is None:
            search_terms = []
        
        logger.info(f"🔧 Preprocessing tool: {tool_name}, result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
        
        # Helper function to calculate fuzzy match score
        def calculate_match_score(text: str, terms: List[str]) -> int:
            if not terms or not text:
                return 0
            text_lower = text.lower()
            score = 0
            for term in terms:
                term_lower = term.lower()
                # Exact match gets 3 points
                if term_lower in text_lower:
                    score += 3
                # Partial match (term is part of a word) gets 1 point
                elif any(term_lower in word for word in text_lower.split()):
                    score += 1
            return score
        
        # Handle log data (from search_logs, query_logs) - CRITICAL: these can return 1000s of logs
        if "log" in tool_name.lower() and "logs" in result:
            logs_data = result.get("logs")
            if logs_data and isinstance(logs_data, list):
                logger.info(f"📋 Found {len(logs_data)} logs")
                
                # Apply fuzzy matching if search_terms provided
                if search_terms:
                    logger.info(f"🔍 Applying fuzzy matching to logs with terms: {search_terms}")
                    scored_logs = []
                    for log in logs_data:
                        msg = str(log.get("_msg") or log.get("message") or "")
                        service = str(log.get("object") or log.get("labels.type") or "")
                        search_text = f"{msg} {service}"
                        score = calculate_match_score(search_text, search_terms)
                        scored_logs.append((score, log))
                    
                    # Sort by score and take top 20
                    scored_logs.sort(key=lambda x: x[0], reverse=True)
                    logs_data = [log for score, log in scored_logs[:20]]
                    logger.info(f"🎯 After fuzzy matching, top log scores: {[score for score, _ in scored_logs[:20]]}")
                else:
                    logs_data = logs_data[:20]
                
                logger.info(f"✅ Processing {len(logs_data)} logs")
                simplified_logs = []
                for log in logs_data:
                    simplified = {
                        "time": log.get("_time") or log.get("_ts") or "Unknown",
                        "level": log.get("msg.logs.level") or log.get("labels.level") or "Unknown",
                        "msg": str(log.get("_msg") or log.get("message") or "")[:150],
                        "service": log.get("object") or log.get("labels.type") or "Unknown",
                        "stream": log.get("_stream") or "Unknown"
                    }
                    simplified_logs.append(simplified)
                
                return {
                    "query": result.get("query", result.get("search_text", "N/A")),
                    "total_count": result.get("total_count", result.get("count", len(result.get("logs", [])))),
                    "returned": len(simplified_logs),
                    "logs": simplified_logs,
                    "note": f"Showing top {len(simplified_logs)} logs" + (" (fuzzy matched)" if search_terms else "")
                }
        
        # Handle ticket data (from get_tickets, search_tickets_by_*, search_tickets)
        if "ticket" in tool_name.lower():
            tickets_data = result.get("sample") or result.get("tickets")
            if tickets_data and isinstance(tickets_data, list):
                logger.info(f"🎫 Found {len(tickets_data)} tickets")
                
                # Apply fuzzy matching if search_terms provided
                if search_terms:
                    logger.info(f"🔍 Applying fuzzy matching to tickets with terms: {search_terms}")
                    scored_tickets = []
                    for ticket in tickets_data:
                        title = str(ticket.get("title", ""))
                        description = str(ticket.get("description", ""))
                        search_text = f"{title} {description}"
                        score = calculate_match_score(search_text, search_terms)
                        scored_tickets.append((score, ticket))
                    
                    # Sort by score and take top 5
                    scored_tickets.sort(key=lambda x: x[0], reverse=True)
                    tickets_data = [ticket for score, ticket in scored_tickets[:5]]
                    logger.info(f"🎯 After fuzzy matching, top ticket scores: {[score for score, _ in scored_tickets[:5]]}")
                else:
                    tickets_data = tickets_data[:5]
                
                logger.info(f"✅ Processing {len(tickets_data)} tickets")
                simplified_tickets = []
                for ticket in tickets_data:
                    simplified = {
                        "id": ticket.get("id", "Unknown"),
                        "ticket_ref": ticket.get("sourceRef", "Unknown"),
                        "title": str(ticket.get("title", ""))[:100],
                        "description": str(ticket.get("description", ""))[:150],
                        "status": ticket.get("status", "Unknown"),
                        "priority": ticket.get("priority", "Unknown"),
                        "type": ticket.get("type", "Unknown"),
                        "project": ticket.get("project", "Unknown"),
                        "source": ticket.get("source", "Unknown")
                    }
                    simplified_tickets.append(simplified)
                
                return {
                    "count": result.get("count", len(result.get("tickets", []))),
                    "returned": len(simplified_tickets),
                    "tickets": simplified_tickets,
                    "note": f"Showing top {len(simplified_tickets)} tickets" + (" (fuzzy matched)" if search_terms else "")
                }
        
        # Handle incident data
        if "incident" in tool_name.lower():
            incidents_data = result.get("sample") or result.get("incidents")
            if incidents_data and isinstance(incidents_data, list):
                logger.info(f"🚨 Found {len(incidents_data)} incidents")
                
                # Apply fuzzy matching if search_terms provided
                if search_terms:
                    logger.info(f"🔍 Applying fuzzy matching with terms: {search_terms}")
                    scored_incidents = []
                    for incident in incidents_data:
                        title = str(incident.get("title", ""))
                        description = str(incident.get("description", ""))
                        search_text = f"{title} {description}"
                        score = calculate_match_score(search_text, search_terms)
                        scored_incidents.append((score, incident))
                    
                    # Sort by score (highest first) and take top 10
                    scored_incidents.sort(key=lambda x: x[0], reverse=True)
                    incidents_data = [inc for score, inc in scored_incidents[:10]]
                    logger.info(f"🎯 After fuzzy matching, top incident scores: {[score for score, _ in scored_incidents[:10]]}")
                else:
                    # No search terms, just take first 10
                    incidents_data = incidents_data[:10]
                
                logger.info(f"✅ Processing {len(incidents_data)} incidents")
                simplified_incidents = []
                for incident in incidents_data:
                    simplified_incidents.append({
                        "id": incident.get("id", "Unknown"),
                        "title": str(incident.get("title", ""))[:120],
                        "description": str(incident.get("description", ""))[:150],
                        "severity": incident.get("severity", "Unknown"),
                        "status": incident.get("status", "Unknown"),
                        "triggered_by": incident.get("triggeredBy", "Unknown"),
                        "source": incident.get("source", "Unknown"),
                        "created_at": incident.get("createdAt", "Unknown"),
                        "updated_at": incident.get("updatedAt", "Unknown")
                    })
                return {
                    "count": result.get("count", len(result.get("incidents", []))),
                    "returned": len(simplified_incidents),
                    "incidents": simplified_incidents,
                    "note": f"Showing top {len(simplified_incidents)} incidents" + (" (fuzzy matched)" if search_terms else "")
                }
        
        # Handle changelog data
        if "changelog" in tool_name.lower():
            changelogs_data = result.get("sample") or result.get("changelogs") or result.get("data")
            if changelogs_data and isinstance(changelogs_data, list):
                logger.info(f"📝 Found {len(changelogs_data)} changelogs")
                
                # Apply fuzzy matching if search_terms provided
                if search_terms:
                    logger.info(f"🔍 Applying fuzzy matching to changelogs with terms: {search_terms}")
                    scored_changelogs = []
                    for changelog in changelogs_data:
                        desc = changelog.get("display") or changelog.get("description") or ""
                        if isinstance(desc, dict):
                            desc = desc.get("description") or desc.get("title") or str(desc)
                        event_type = changelog.get("eventType") or changelog.get("derivedType") or ""
                        source = changelog.get("source") or ""
                        search_text = f"{desc} {event_type} {source}"
                        score = calculate_match_score(search_text, search_terms)
                        scored_changelogs.append((score, changelog))
                    
                    # Sort by score and take top 10
                    scored_changelogs.sort(key=lambda x: x[0], reverse=True)
                    changelogs_data = [changelog for score, changelog in scored_changelogs[:10]]
                    logger.info(f"🎯 After fuzzy matching, top changelog scores: {[score for score, _ in scored_changelogs[:10]]}")
                else:
                    changelogs_data = changelogs_data[:10]
                
                logger.info(f"✅ Processing {len(changelogs_data)} changelogs")
                simplified_changelogs = []
                for changelog in changelogs_data:
                    # Extract description from display or description field
                    desc = changelog.get("display") or changelog.get("description") or ""
                    if isinstance(desc, dict):
                        desc = desc.get("description") or desc.get("title") or str(desc)
                    
                    simplified_changelogs.append({
                        "id": changelog.get("id", "Unknown"),
                        "event_type": changelog.get("eventType") or changelog.get("derivedType") or "Unknown",
                        "category": changelog.get("eventCategory", "Unknown"),
                        "description": str(desc)[:150] if desc else "No description",
                        "severity": changelog.get("severity", "Unknown"),
                        "timestamp": changelog.get("triggeredAt") or changelog.get("createdAt") or "Unknown",
                        "source": changelog.get("source") or "Unknown",
                        "region": changelog.get("region") or "Unknown",
                        "is_human": changelog.get("isActorHuman", False)
                    })
                return {
                    "count": result.get("count", len(result.get("changelogs", []))),
                    "returned": len(simplified_changelogs),
                    "changelogs": simplified_changelogs,
                    "note": f"Showing top {len(simplified_changelogs)} changelogs" + (" (fuzzy matched)" if search_terms else "")
                }
        
        # Handle notification data
        if "notification" in tool_name.lower():
            notifications_data = result.get("sample") or result.get("notifications")
            if notifications_data and isinstance(notifications_data, list):
                logger.info(f"🔔 Found {len(notifications_data)} notifications, limiting to 10")
                simplified_notifications = []
                for notification in notifications_data[:10]:
                    simplified_notifications.append({
                        "id": self._extract_nested_value(notification, "id"),
                        "message": str(self._extract_nested_value(notification, "message", "title"))[:150],
                        "severity": self._extract_nested_value(notification, "severity", "priority", "level"),
                        "timestamp": self._extract_nested_value(notification, "timestamp", "createdAt", "sentAt"),
                        "source": self._extract_nested_value(notification, "source", "origin"),
                        "target": str(self._extract_nested_value(notification, "target", "recipients"))[:80]
                    })
                logger.info(f"✅ Simplified {len(simplified_notifications)} notifications")
                return {
                    "count": result.get("count", len(notifications_data)),
                    "returned": len(simplified_notifications),
                    "notifications": simplified_notifications,
                    "note": f"Showing first {len(simplified_notifications)} notifications"
                }
        
        # Handle resource data - heavily filter and limit to relevant fields only
        if "resource" in tool_name.lower():
            resources_data = result.get("resources") or result.get("sample")
            if resources_data and isinstance(resources_data, list):
                logger.info(f"📦 Found {len(resources_data)} resources, filtering and limiting")
                simplified_resources = []
                
                for resource in resources_data[:100]:  # Process max 100 resources
                    # Extract using helper for robustness
                    resource_name = self._extract_nested_value(resource, "resourceName", "name")
                    resource_type = self._extract_nested_value(resource, "resourceType", "type")
                    resource_subtype = self._extract_nested_value(resource, "resourceSubType", "subType", "kind")
                    
                    # Get status - try multiple paths
                    phase = self._extract_nested_value(
                        resource,
                        "metadata.status.phase",
                        "status.phase", 
                        "resourceStatus",
                        "status"
                    )
                    
                    # Get namespace - try multiple paths
                    namespace = self._extract_nested_value(
                        resource,
                        "metadata.metadata.namespace",
                        "metadata.namespace",
                        "namespace"
                    )
                    
                    # Extract node from tags if available
                    node = "Unknown"
                    tags = resource.get("tags", [])
                    if isinstance(tags, list):
                        for tag in tags:
                            if isinstance(tag, dict) and tag.get("Key") == "node":
                                node = tag.get("Value", "Unknown")
                                break
                    
                    simplified = {
                        "name": resource_name,
                        "type": f"{resource_type}/{resource_subtype}" if resource_subtype != "Unknown" else resource_type,
                        "status": phase,
                        "namespace": namespace,
                        "node": node
                    }
                    simplified_resources.append(simplified)
                
                logger.info(f"✅ Simplified {len(simplified_resources)} resources from {len(resources_data)}")
                return {
                    "count": len(resources_data),
                    "returned": len(simplified_resources),
                    "resources": simplified_resources,
                    "note": f"Showing {len(simplified_resources)} resources with status, namespace, and node info"
                }
        
        # Return original result for other cases
        logger.info(f"⚠️ No preprocessing applied for tool: {tool_name}")
        return result
    
    async def generate_enriched_response(self, state: Dict[str, Any], websocket=None) -> Dict[str, Any]:
        """Use LLM to generate contextual, actionable response with optional streaming"""
        
        try:
            if not self.llm:
                logger.warning("No LLM available, using fallback")
                fallback = self._fallback_response_generation(state)
                if websocket:
                    await websocket.send_text(json.dumps({"on_chat_model_stream": fallback.get("final_response", "")}))
                return fallback
            
            # Extract tool results
            mcp_results = state.get("mcp_results", [])
            # Get query_analysis from context_data (where it's actually stored)
            context_data = state.get("context_data", {})
            query_analysis = context_data.get("query_analysis", {})
            # Get search terms from llm_analysis (where they're actually stored)
            llm_analysis = query_analysis.get("llm_analysis", {})
            search_terms = llm_analysis.get("search_terms", [])
            
            tool_data = []
            for result in mcp_results:
                if result.get("success"):
                    # Pre-process complex nested data structures with fuzzy matching
                    processed_data = self._preprocess_tool_result(
                        result.get("result", {}), 
                        result.get("tool_name", ""),
                        search_terms=search_terms
                    )
                    tool_data.append({
                        "tool": result.get("tool_name"),
                        "data": processed_data
                    })
            
            logger.info(f"Processing {len(tool_data)} successful tool results with search_terms: {search_terms}")
            
            # Log size of preprocessed data
            import sys
            preprocessed_size = sum(sys.getsizeof(json.dumps(td)) for td in tool_data)
            logger.info(f"📊 Preprocessed tool data size: {preprocessed_size} bytes ({preprocessed_size/1024:.1f} KB)")
            
            context = {
                "original_query": state.get("user_query"),
                "query_type": state.get("query_type"),
                "search_terms": search_terms,
                "tool_results": tool_data,  # Only preprocessed data
                "execution_summary": {
                    "tools_executed": len(state.get("executed_tools", [])),
                    "success_count": len([r for r in mcp_results if r.get("success")])
                },
                "conversation_history": state.get("conversation_history", [])
            }
            
            # Log context size to diagnose token issues
            context_json = json.dumps(context, indent=2)
            context_size = len(context_json)
            logger.info(f"📊 Context JSON size: {context_size} bytes ({context_size/1024:.1f} KB)")
            logger.info(f"📊 Estimated tokens: ~{context_size/4} (rough estimate)")
            
            system_prompt = f"""You are a helpful assistant generating responses based on tool execution results.

Context: {context_json}

⚠️ CRITICAL ANTI-HALLUCINATION RULES:
1. ONLY use data from tool_results - NEVER fabricate information
2. If tool_results is EMPTY or tools FAILED, explicitly state: "I couldn't retrieve the data due to [reason]"
3. If you have NO data for a requested field, say "Data not available" - DON'T make it up
4. NEVER invent resource details, versions, metadata, or changelogs
5. If execution_summary shows failures, acknowledge them in your response

⚠️ CRITICAL: NO GENERIC INSTRUCTIONS!
If the user asks about infrastructure state (pods, containers, resources), you MUST:
- Use ACTUAL data from tool_results
- Show REAL resource names, statuses, and details
- Filter results based on user criteria (e.g., "CrashLoopBackOff" status)
- NEVER provide generic kubectl commands or troubleshooting steps
- If tool_results is empty, say "No tools were executed - I'll need to query the infrastructure"

CRITICAL INSTRUCTIONS FOR SMART FILTERING:
1. If search_terms exist, filter the tool_results to find matches
2. Use AGGRESSIVE fuzzy matching with these rules:
   - Break query into keywords: "Mit-runtime-api-services" → ["runtime", "api", "services"]
   - Match if ANY significant keyword (2+ chars) appears in title/description/source
   - Ignore case, hyphens, underscores, apostrophes: "runtime-api" = "Runtime api" = "runtime_api" = "Runtime-aws-api's"
   - Remove company prefixes: "mit", "acme", "gcp" - focus on service names
   - Partial word matching: "api" matches "api's", "apis", "api-services"
   - Score matches: 2+ keyword matches = strong match, 1 match = possible match
   - Examples:
     * "Mit-runtime-api-services" should match "Runtime-aws-api's are not working"
     * "runtime api" should match "Incident on runtime api services"
     * "cart service" should match "Acme cart service are down"
3. Look for partial matches in ALL fields: title, description, applicationIds, metadata, source
4. If no exact match, ALWAYS present the CLOSEST matches ranked by relevance
5. Explain your matching logic: "I found 'Runtime-aws-api's are not working' which matches 'runtime' and 'api' from your query"
6. For infrastructure queries: Filter by status in metadata.status.phase field (Running, Pending, Failed, CrashLoopBackOff)
6. For infrastructure queries: Filter by status in metadata.status.phase field (Running, Pending, Failed, CrashLoopBackOff)

FORMATTING INSTRUCTIONS FOR DIFFERENT DATA TYPES:

For KUBERNETES PODS/RESOURCES:
- Filter by metadata.status.phase (e.g., "CrashLoopBackOff", "Pending", "Failed")
- List each pod with: resourceName, status (phase), namespace, node
- Include container status and restart counts if available
- Format example: "vector-0 (Status: Pending) in namespace 'vector' on node 'gke-mit-acme-mit-default-61b6a85a-7hsc'"

For TICKETS/SERVICE REQUESTS:
- List each ticket with: ticket_id (e.g., CS-334), title, status, priority
- Include brief description (1-2 sentences)
- Mention key activity or latest comment if relevant
- Format example: "CS-334: Jira integration data not ingested (Done, Highest priority) - Integration completed but data not flowing into Manifest. Latest activity: Token scope issue resolved."

For INCIDENTS:
- List each incident with: id, title, severity, status
- Include start time and affected applications
- Format example: "INC-123: API Gateway Timeout (High severity, Resolved) - Started 2025-01-15 10:30 AM, affected runtime-api service."

For RESOURCES:
- List each resource with: name, type, status
- Include relevant metadata if available

SPACING RULES - KEEP RESPONSES COMPACT:
- Use single newlines between sentences, NOT double
- Only add blank lines between major sections
- Keep lists tight with no spacing between items
- Avoid excessive paragraph breaks
- Write in a dense, information-rich style like ChatGPT

LIST FORMATTING RULES:
- NEVER use numbered lists (1., 2., 3., etc.)
- ALWAYS use bullet points with dots (•) for lists
- Use dash (-) for sub-items or simple lists
- Example: "• Changelogs: Found 5 changes" NOT "1. Changelogs: Found 5 changes"

Generate a comprehensive, natural language response to the user's question with SPECIFIC details from filtered results.
If no exact match: explain what you searched for and present closest matches.
If NO tools executed for infrastructure query: State that you need to query the system first.

CONVERSATION CONTEXT:
The conversation_history field contains previous exchanges. Use it to:
- Answer follow-up questions (e.g., "what incidents did you mention?" → refer to previous assistant messages)
- Maintain context across messages (e.g., "tell me more about that" → know what "that" refers to)
- Avoid repeating information already shared
- IMPORTANT: Always answer the CURRENT query provided in the user message, not previous questions from conversation history

Write in a conversational, helpful tone as if you're ChatGPT explaining the results with compact spacing and bullet points."""
            
            # Add current query to system prompt
            current_query = context.get("original_query", "")
            # Add current query to system prompt
            current_query = context.get("original_query", "")
            system_prompt += f"\n\nCURRENT USER QUERY: {current_query}"
            
            # Build messages array with conversation history
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history if available
            conversation_history = context.get("conversation_history", [])
            if conversation_history:
                logger.info(f"📜 Including {len(conversation_history)} previous messages in context")
                messages.extend(conversation_history)
            
            # Add current query with explicit instruction
            messages.append({
                "role": "user", 
                "content": f"Answer this question: {current_query}\n\nGenerate the enriched response based on the tool results provided above."
            })
            
            logger.info("Invoking LLM for response generation...")
            
            # If websocket provided, use streaming for direct text response
            if websocket:
                content = ""
                async for chunk in self.llm.astream(messages):
                    token = chunk.content
                    if token:
                        content += token
                        await websocket.send_text(json.dumps({"on_chat_model_stream": token}))
                logger.info(f"Streaming completed, total length: {len(content)}")
                
                # Now generate metadata (forward links, recommendations) without streaming
                metadata_response = await self._generate_metadata(state, content)
                
                return {
                    "final_response": content,
                    "forward_links": metadata_response.get("forward_links", []),
                    "recommendations": metadata_response.get("recommendations", []),
                    "insights": metadata_response.get("insights", {})
                }
            else:
                response = self.llm.invoke(messages)
                logger.info(f"LLM invocation completed, response type: {type(response)}")
                content = response.content
                
                # Generate metadata for non-streaming mode too
                metadata_response = await self._generate_metadata(state, content)
                
                return {
                    "final_response": content,
                    "forward_links": metadata_response.get("forward_links", []),
                    "recommendations": metadata_response.get("recommendations", []),
                    "insights": metadata_response.get("insights", {})
                }
            
            
            logger.info("✅ Enriched response generated successfully")
            
        except Exception as e:
            logger.error(f"❌ Response generation failed: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            fallback = self._fallback_response_generation(state)
            logger.debug(f"Using fallback response: {fallback}")
            return fallback
    
    async def _generate_metadata(self, state: Dict[str, Any], response_text: str) -> Dict[str, Any]:
        """Generate forward links and recommendations based on the response"""
        
        try:
            query = state.get("user_query", "")
            
            metadata_prompt = f"""Based on the user's question and the response provided, generate helpful metadata.

User Question: {query}

Response: {response_text}

Generate:
1. Forward links: 3-5 relevant follow-up questions the user might want to ask
2. Recommendations: 3-5 actionable next steps or suggestions
3. Insights: Key observations about the data or search strategy

Return ONLY valid JSON in this exact format:
{{
    "forward_links": ["question 1", "question 2", "question 3"],
    "recommendations": ["action 1", "action 2", "action 3"],
    "insights": {{"key_observation": "value", "search_strategy": "description"}}
}}"""
            
            messages = [
                {"role": "system", "content": "You are a helpful assistant that generates metadata. Return ONLY valid JSON."},
                {"role": "user", "content": metadata_prompt}
            ]
            
            response = self.llm.invoke(messages)
            content = response.content
            
            json_str = self._extract_json_from_response(content)
            metadata = json.loads(json_str)
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Metadata generation failed: {e}, using defaults")
            return {
                "forward_links": ["What else can you help me with?", "Show me more details"],
                "recommendations": ["Review the data", "Check for related information"],
                "insights": {}
            }
        
    # Fallback methods for when LLM is unavailable
    
    def _fallback_query_analysis(self, user_query: str) -> Dict[str, Any]:
        """Fallback query analysis using simple heuristics"""
        query_lower = user_query.lower()
        
        # Extract search terms from query
        import re
        # Remove common words and extract meaningful terms
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'about', 'tell', 'me', 'describe', 'show', 'what', 'when', 'where', 'how', 'is', 'are', 'was', 'were', 'happened'}
        words = re.findall(r'\b\w+\b', query_lower)
        search_terms = [w for w in words if w not in stop_words and len(w) > 2]
        
        # Simple keyword matching
        if any(word in query_lower for word in ["error", "incident", "problem", "issue", "failure"]):
            query_type = "incident_analysis"
        elif any(word in query_lower for word in ["show", "list", "get", "display"]):
            query_type = "exploration"
        elif any(word in query_lower for word in ["why", "cause", "reason"]):
            query_type = "root_cause"
        else:
            query_type = "conversational"
        
        return {
            "query_type": query_type,
            "intent": "Analyze the query",
            "entities": [],
            "search_terms": search_terms,
            "confidence_score": 0.5,
            "specificity_level": "medium",
            "is_multi_part": False,
            "sub_queries": []
        }
    
    def _fallback_tool_planning(self, query_analysis: Dict[str, Any], available_tools: List[str]) -> List[Dict[str, Any]]:
        """Fallback tool planning using simple rules"""
        query_type = query_analysis.get("query_type", "general")
        search_terms = query_analysis.get("search_terms", [])
        search_query = " ".join(search_terms) if search_terms else ""
        
        # Simple rule-based tool selection with search terms
        tool_map = {
            "incident_analysis": [
                {"name": "search_incidents", "parameters": {"query": search_query}} if search_query else {"name": "get_incidents", "parameters": {}},
                {"name": "get_incidents", "parameters": {}}
            ],
            "exploration": [
                {"name": "get_incidents", "parameters": {}},
                {"name": "search_incidents", "parameters": {"query": search_query}} if search_query else {"name": "get_incidents", "parameters": {}}
            ],
            "root_cause": [
                {"name": "search_incidents", "parameters": {"query": search_query}} if search_query else {"name": "get_incidents", "parameters": {}},
                {"name": "query_logs", "parameters": {"query": search_query}} if search_query else {"name": "get_log_stats", "parameters": {}}
            ],
            "conversational": [
                {"name": "get_incidents", "parameters": {}}
            ]
        }
        
        return tool_map.get(query_type, [{"name": "get_incidents", "parameters": {}}])
    
    def _fallback_response_generation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback response generation"""
        mcp_results = state.get("mcp_results", [])
        success_count = len([r for r in mcp_results if r.get("success")])
        
        return {
            "final_response": f"I executed {len(mcp_results)} tools and {success_count} were successful. Here are the results.",
            "forward_links": ["Check system status", "View recent logs"],
            "recommendations": ["Review the data", "Monitor the situation"],
            "insights": {"tools_executed": len(mcp_results), "success_rate": success_count / len(mcp_results) if mcp_results else 0}
        }


# Global instance
llm_client = LLMDecisionMaker()
