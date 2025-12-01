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
1. Query type: incident_analysis, exploration, root_cause, or conversational
2. Intent: what the user wants to accomplish
3. Entities: specific items mentioned (resource IDs, timestamps, severity levels)
4. Search terms: extract key terms for flexible searching (extract service names, application names, keywords)
5. Confidence score (0-1)
6. Specificity level: low, medium, or high
7. Whether this is a multi-part query with multiple sub-questions

Available tools: {', '.join(available_tools)}

IMPORTANT: Extract search terms intelligently:
- For "Mit-runtime-api-services", extract: ["mit", "runtime", "api", "services", "mit-runtime-api-services"]
- For "Shopping 3 website", extract: ["shopping", "shopping 3", "website"]
- For "Acme-Cart", extract: ["acme", "cart", "acme-cart"]
- Include variations and partial matches

Respond ONLY with valid JSON in this exact format:
{{
    "query_type": "incident_analysis|exploration|root_cause|conversational",
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

CRITICAL TOOL DISAMBIGUATION:
**LOGS vs CHANGELOGS vs INCIDENTS - Choose the RIGHT tool:**
- "search logs", "log entries", "log messages", "system logs", "application logs", "error logs"
  → Use LOG tools: search_logs, query_logs (for VictoriaLogs - raw log data)
- "changes", "deployments", "configuration changes", "IAM changes", "RBAC changes", "what changed", "modifications"
  → Use CHANGELOG tools: search_changelogs, get_changelog_by_resource (for change tracking)
- "incidents", "outages", "downtime", "service down", "alerts", "problems"
  → Use INCIDENT tools: search_incidents, get_incidents (for incident management)

**Key distinction**: 
- "logs" = raw log entries from VictoriaLogs (use search_logs)
- "changelogs" = configuration/deployment change records (use search_changelogs)
- "incidents" = service outage/problem records (use search_incidents)

CRITICAL SEARCH STRATEGY:
1. Use search_terms from query_analysis for flexible matching
2. For LOG searches:
   - search_logs with search_text parameter for simple text searches
   - query_logs with query parameter for complex LogSQL queries
3. For incident searches, try multiple approaches:
   - search_incidents with query parameter using search_terms
   - get_incidents to list all, then filter by search_terms
   - If specific incident ID mentioned, use get_incident_by_id
3. For changelog searches with filters:
   - search_changelogs with severity/provider_key/description
   - search_changelogs_by_event_type for deployment/configuration type filtering
   - get_changelog_by_resource for specific resource's change history
4. Use partial matches and fuzzy search when exact match fails
5. Extract key words: "Mit-runtime-api-services" → search for "runtime", "api", "mit"

Return a JSON array of tools with parameters in this exact format:
[
    {{"name": "tool_name", "parameters": {{"param": "value"}}}},
    {{"name": "another_tool", "parameters": {{}}}}
]

For incident queries, ALWAYS include search_terms in parameters:
[
    {{"name": "search_incidents", "parameters": {{"query": "space-separated search terms from search_terms array"}}}},
    {{"name": "get_incidents", "parameters": {{}}}}
]

Consider:
1. Tool dependencies and execution order
2. Required vs optional parameters  
3. Use search_terms for fuzzy/partial matching
4. Context from previous executions: {json.dumps(context) if context else 'None'}"""
        
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
    
    def _preprocess_tool_result(self, result: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
        """Pre-process complex nested data structures for better LLM consumption"""
        
        logger.info(f"🔧 Preprocessing tool: {tool_name}, result keys: {list(result.keys()) if isinstance(result, dict) else 'not a dict'}")
        
        # Handle log data (from search_logs, query_logs) - CRITICAL: these can return 1000s of logs
        if "log" in tool_name.lower() and "logs" in result:
            logs_data = result.get("logs")
            if logs_data and isinstance(logs_data, list):
                logger.info(f"📋 Found {len(logs_data)} logs, limiting to 10 and truncating fields")
                # Extract key fields from logs (limit to first 10 only!)
                simplified_logs = []
                for log in logs_data[:10]:  # ONLY show 10 logs max
                    simplified = {
                        "time": log.get("_time", "N/A"),
                        "level": log.get("level", "N/A"),
                        "msg": log.get("_msg", "No message")[:100],  # Truncate message
                        "service": log.get("service", log.get("object", "Unknown"))
                    }
                    simplified_logs.append(simplified)
                
                logger.info(f"✅ Simplified {len(simplified_logs)} logs from {len(logs_data)} total")
                return {
                    "query": result.get("query", result.get("search_text", "N/A")),
                    "total_count": result.get("total_count", result.get("count", len(logs_data))),
                    "returned": len(simplified_logs),
                    "logs": simplified_logs,
                    "note": f"Showing first {len(simplified_logs)} of {result.get('total_count', result.get('count', len(logs_data)))} logs (truncated for brevity)"
                }
        
        # Handle ticket data (from get_tickets, search_tickets_by_*, search_tickets)
        if "ticket" in tool_name.lower():
            # Try both 'sample' and 'tickets' keys
            tickets_data = result.get("sample") or result.get("tickets")
            if tickets_data and isinstance(tickets_data, list):
                logger.info(f"🎫 Found {len(tickets_data)} tickets, limiting to 3 and heavily truncating")
                # Extract key fields from each ticket (limit to first 3 tickets only!)
                simplified_tickets = []
                for ticket in tickets_data[:3]:  # Limit to ONLY 3 tickets
                    simplified = {
                        "id": ticket.get("id"),
                        "ticket_id": ticket.get("sourceRef", "N/A"),
                        "title": ticket.get("title", "No title")[:80],  # Heavily truncate title
                        "description": ticket.get("description", "No description")[:100],  # Heavily truncate description
                        "status": ticket.get("externalStatus", ticket.get("status", "Unknown")),
                        "priority": ticket.get("externalPriority", ticket.get("priority", "Unknown")),
                        "type": ticket.get("type", "Unknown")
                        # Skip created/resolved dates, comments, and activities to save space
                    }
                    
                    simplified_tickets.append(simplified)
                
                logger.info(f"✅ Simplified {len(simplified_tickets)} tickets (removed metadata, comments, activities)")
                return {
                    "count": result.get("count", len(tickets_data)),
                    "returned": len(simplified_tickets),
                    "tickets": simplified_tickets,
                    "note": f"Showing first {len(simplified_tickets)} of {result.get('count', len(tickets_data))} tickets (heavily truncated for brevity)"
                }
        
        # Handle incident data (limit to first 5)
        if "incident" in tool_name.lower() and "sample" in result:
            if isinstance(result["sample"], list):
                simplified_incidents = []
                for incident in result["sample"][:5]:
                    simplified_incidents.append({
                        "id": incident.get("id"),
                        "title": incident.get("title", "No title")[:100],
                        "severity": incident.get("severity", "Unknown"),
                        "status": incident.get("status", "Unknown"),
                        "start_time": incident.get("startTime", "N/A"),
                        "application": incident.get("applicationIds", [])[:3]  # Limit apps
                    })
                return {
                    "count": result.get("count", len(result["sample"])),
                    "returned": len(simplified_incidents),
                    "incidents": simplified_incidents
                }
        
        # Handle resource data (limit to first 5)
        if "resource" in tool_name.lower() and "sample" in result:
            if isinstance(result["sample"], list):
                simplified_resources = []
                for resource in result["sample"][:5]:
                    simplified_resources.append({
                        "id": resource.get("id"),
                        "name": resource.get("name", "No name")[:100],
                        "type": resource.get("type", "Unknown"),
                        "status": resource.get("status", "Unknown")
                    })
                return {
                    "count": result.get("count", len(result["sample"])),
                    "returned": len(simplified_resources),
                    "resources": simplified_resources
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
            query_analysis = state.get("query_analysis") or {}
            search_terms = query_analysis.get("search_terms", [])
            
            tool_data = []
            for result in mcp_results:
                if result.get("success"):
                    # Pre-process complex nested data structures
                    processed_data = self._preprocess_tool_result(result.get("result", {}), result.get("tool_name", ""))
                    tool_data.append({
                        "tool": result.get("tool_name"),
                        "data": processed_data
                    })
            
            logger.info(f"Processing {len(tool_data)} successful tool results with search_terms: {search_terms}")
            
            # Log size of preprocessed data
            import sys
            import json as json_lib
            preprocessed_size = sum(sys.getsizeof(json_lib.dumps(td)) for td in tool_data)
            logger.info(f"📊 Preprocessed tool data size: {preprocessed_size} bytes ({preprocessed_size/1024:.1f} KB)")
            
            context = {
                "original_query": state.get("user_query"),
                "query_type": state.get("query_type"),
                "search_terms": search_terms,
                "tool_results": tool_data,  # Only preprocessed data
                "execution_summary": {
                    "tools_executed": len(state.get("executed_tools", [])),
                    "success_count": len([r for r in mcp_results if r.get("success")])
                }
            }
            
            # Log context size to diagnose token issues
            context_json = json_lib.dumps(context, indent=2)
            context_size = len(context_json)
            logger.info(f"📊 Context JSON size: {context_size} bytes ({context_size/1024:.1f} KB)")
            logger.info(f"📊 Estimated tokens: ~{context_size/4} (rough estimate)")
            
            system_prompt = f"""You are a helpful assistant generating responses based on tool execution results.

Context: {context_json}

CRITICAL INSTRUCTIONS FOR SMART FILTERING:
1. If search_terms exist, filter the tool_results to find matches
2. Use fuzzy matching: "Mit-runtime-api-services" should match "runtime api" or "Incident on runtime api"
3. Look for partial matches in: title, description, applicationIds, metadata
4. If exact match not found, present the CLOSEST matches with explanation
5. Always explain what you found and why it matches (or why nothing matched)

FORMATTING INSTRUCTIONS FOR DIFFERENT DATA TYPES:

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

Generate a comprehensive, natural language response to the user's question with SPECIFIC details from filtered results.
If no exact match: explain what you searched for and present closest matches.

Write in a conversational, helpful tone as if you're ChatGPT explaining the results."""
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generate the enriched response."}
            ]
            
            logger.info("Invoking LLM for response generation...")
            
            # If websocket provided, use streaming for direct text response
            if websocket:
                content = ""
                async for chunk in self.llm.astream(messages):
                    token = chunk.content
                    if token:
                        content += token
                        await websocket.send_text(json_lib.dumps({"on_chat_model_stream": token}))
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
            metadata = json_lib.loads(json_str)
            
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
