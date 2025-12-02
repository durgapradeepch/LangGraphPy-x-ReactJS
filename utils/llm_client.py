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
        
        # NEW: Dedicated model for routing (Fast & Cheap)
        # gpt-4o-mini is perfect for simple classification tasks (~200ms latency)
        self.router_model_name = os.getenv("ROUTER_MODEL", "gpt-4o-mini")
        self.temperature = 0.1
        
        if self.api_key:
            # Main client for complex reasoning (Analysis, Planning, Response)
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=2000
            )
            
            # Router client for fast binary decisions
            self.router_llm = ChatOpenAI(
                model=self.router_model_name,
                temperature=0,  # Strict deterministic outputs
                max_tokens=100
            )
            logger.info(f"✅ LLM clients initialized. Main: {self.model_name}, Router: {self.router_model_name}")
        else:
            self.llm = None
            self.router_llm = None
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
    
    async def should_use_tools(self, user_query: str) -> bool:
        """
        Layer 1 Router: Decides if the query requires tool execution (Enhanced Mode)
        or if it is just a conversational/general question (Simple Mode).
        
        Uses gpt-4o-mini for speed (~200ms) and cost efficiency.
        """
        # Use router_llm if available, otherwise fall back to main llm
        llm_to_use = self.router_llm if self.router_llm else self.llm
        
        if not llm_to_use:
            return True  # Fallback to safe mode (try to use tools) if LLM is down
            
        system_prompt = """You are a router for a technical assistant. 
Your job is to decide if a query requires checking internal systems/tools or if it is general conversation.

RETURN JSON ONLY: {"use_tools": true} or {"use_tools": false}

CRITERIA FOR "use_tools": true (Enhanced Mode):
- Questions about system status, incidents, outages, errors, or failures
- Requests to check logs, metrics, changelogs, tickets, or notifications
- Questions about infrastructure (pods, containers, kubernetes, AWS, nodes)
- Questions about the Neo4j graph, database schema, or relationships
- Queries asking "what happened", "why did it fail", "show me..."
- Specific service names mentioned (Acme, Cart, API, Runtime, services, applications)
- Problem descriptions ("stuck", "broken", "not working", "kaput", "dead")
- Performance issues ("slow", "high latency", "timeout")

CRITERIA FOR "use_tools": false (Simple Mode):
- Greetings (hello, hi, how are you)
- General knowledge questions (what is python? write me a poem, explain concept X)
- Compliments or closings (thank you, bye, great job)
- Questions unrelated to the system/infrastructure
- Hypothetical or educational questions (how does X work in general?)

User Query: """

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ]
            
            # Fast/cheap call
            response = await llm_to_use.ainvoke(messages)
            content = self._extract_json_from_response(response.content)
            result = json.loads(content)
            
            decision = result.get("use_tools", False)
            mode = 'Enhanced Mode' if decision else 'Simple Mode'
            logger.info(f"🚦 Router ({self.router_model_name}) decision for '{user_query[:50]}...': {mode}")
            return decision
            
        except Exception as e:
            logger.error(f"❌ Router failed: {e}")
            # If router fails, default to Enhanced mode to be safe
            return True
    
    async def analyze_query_intent(self, user_query: str, available_tools: List[str]) -> Dict[str, Any]:
        """Analyze user query to determine intent and extract entities"""
        
        if not self.llm:
            return self._fallback_query_analysis(user_query)
        
        system_prompt = f"""You are a query analysis expert. Analyze the user's query.

Respond ONLY with valid JSON in this exact format:
{{
    "query_type": "incident_analysis|exploration|root_cause|infrastructure_query|graph_query|conversational",
    "intent": "brief description",
    "entities": [{{"type": "resource", "value": "id"}}],
    "search_terms": ["term1", "term2"],
    "strict_service_name": "service-name or null",
    "specific_id": "12345 or null",
    "confidence_score": 0.8
}}

CRITICAL EXTRACTION RULES:
1. **Specific IDs (HIGHEST PRIORITY)**: 
   - If the user provides a numeric ID (e.g., "50944068", "1529"), extract it to `specific_id`.
   - If the user provides a ticket ID (e.g., "CS-335"), extract it to `specific_id`.
   
2. **Strict Service Name**:
   - Extract the service name string (e.g., "acme-cart").
   - **IMPORTANT**: If the input is just a number (like "50944068"), `strict_service_name` must be NULL. Numbers are IDs, not names.
   - Clean generic/company prefixes: "ai-acme cart" → "acme-cart" (NOT "ai-acme")
   - Context-aware: "billing service error" → "billing"

Examples:
- "tell me about resource 50944068" → {{"specific_id": "50944068", "strict_service_name": null, "query_type": "infrastructure_query"}}
- "status of acme-cart" → {{"specific_id": null, "strict_service_name": "acme-cart"}}
- "incident 1529" → {{"specific_id": "1529", "strict_service_name": null, "query_type": "incident_analysis"}}
- "failure in ai-acme cart" → {{"specific_id": null, "strict_service_name": "acme-cart", "query_type": "incident_analysis"}}"""
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this query: {user_query}"}
            ]
            
            response = self.llm.invoke(messages)
            content = response.content
            
            json_str = self._extract_json_from_response(content)
            analysis = json.loads(json_str)
            
            logger.info(f"🔍 Query analyzed: {analysis.get('query_type')}")
            logger.info(f"🎯 IDs extracted: {analysis.get('specific_id')} | Service Name: {analysis.get('strict_service_name')}")
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
                    required_marker = " [REQUIRED]" if param_name in required_params else " [OPTIONAL]"
                    param_details.append(f"    * {param_name} ({param_type}){required_marker}")
                if param_details:
                    tool_desc += "\n  Parameters:\n" + "\n".join(param_details)
            tools_info.append(tool_desc)
        
        tools_with_schemas = '\n'.join(tools_info)
        
        system_prompt = f"""You are a tool execution planner. Based on the query analysis, create a plan of tools to execute.

Query Analysis: {json.dumps(query_analysis)}

Available tools:
{tools_with_schemas}

⚠️ CRITICAL DECISION LOGIC (FOLLOW ORDER EXACTLY):

1. **CHECK FOR SPECIFIC ID (Priority #1)**
   If `specific_id` is present in Query Analysis (e.g., "50944068" or "CS-335"):
   - **DO NOT USE SEARCH TOOLS.**
   - **Resource ID (numeric):** Use `get_resource_by_id(resource_id=ID)`.
     * OPTIONAL: For "everything" queries, also add:
       - `get_resource_version(resource_id=ID)`
       - `get_resource_metadata(resource_id=ID)`
       - `get_resource_tickets(resource_id=ID)`
       - `get_changelog_by_resource(resource_id=ID)`
       - `get_notifications_by_resource(resource_id=ID)`
   - **Incident ID:** Use `get_incident_by_id(incident_id=ID)` + `get_incident_changelogs(incident_id=ID)`.
   - **Ticket ID:** Use `get_ticket_by_id(ticket_id=ID)`.
   - **Changelog ID:** Use `get_changelog_by_id(changelog_id=ID)`.

2. **CHECK FOR SERVICE NAME (Priority #2)**
   Only if `specific_id` is NULL, check `strict_service_name`.
   
   **COMPREHENSIVE QUERIES (when user asks for "everything", "all details", "complete information"):**
   - If query intent is comprehensive (check query_analysis for keywords like "everything", "all", "details", "complete", "comprehensive"):
     * Step 1: Use search tool to find the resource/incident and get its ID
     * Step 2: SKIP remaining steps - let the system handle ID extraction from results
     * Example: If user asks "everything about vector-0", just use `search_resources(query="vector-0")`
     * The system will extract the resource_id from search results and can make a follow-up request
   
   **SPECIFIC QUERIES (when user asks for specific info like "status", "when created", "what type"):**
   - Use appropriate search tool with the service name
   - Example: `search_resources(query="acme-cart")`, `search_incidents(query="acme-cart")`

3. **FALLBACK SEARCH (Priority #3)**
   - If both ID and Service Name are null, use `search_terms` in search tools.

QUERY INTENT DETECTION:
- **Comprehensive keywords**: "everything", "all details", "all information", "complete info", "tell me about", "full details", "comprehensive"
- **Specific keywords**: "status", "when", "what type", "is it", "show me only"

SCENARIO EXAMPLES:
- User: "Everything about resource 50944068"
  -> Analysis: {{"specific_id": "50944068", "intent": "comprehensive"}}
  -> Plan: [
       {{"name": "get_resource_by_id", "parameters": {{"resource_id": "50944068"}}}},
       {{"name": "get_resource_version", "parameters": {{"resource_id": "50944068"}}}},
       {{"name": "get_resource_metadata", "parameters": {{"resource_id": "50944068"}}}},
       {{"name": "get_resource_tickets", "parameters": {{"resource_id": "50944068"}}}},
       {{"name": "get_changelog_by_resource", "parameters": {{"resource_id": "50944068"}}}},
       {{"name": "get_notifications_by_resource", "parameters": {{"resource_id": "50944068"}}}}
     ]

- User: "Tell me everything about vector-0 resource - details, version, metadata, tickets, change history, notifications"
  -> Analysis: {{"strict_service_name": "vector-0", "intent": "comprehensive"}}
  -> Plan: [{{"name": "search_resources", "parameters": {{"query": "vector-0"}}}}]
  -> Note: System will extract resource_id from results and can follow up if needed

- User: "What's the status of acme-cart?"
  -> Analysis: {{"strict_service_name": "acme-cart", "intent": "specific status query"}}
  -> Plan: [{{"name": "search_resources", "parameters": {{"query": "acme-cart"}}}}]

Respond ONLY with valid JSON array format."""
        
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
            return self._fallback_tool_planning(query_analysis, [t.get("name") for t in tool_schemas])
    
    def _extract_nested_value(self, obj: Any, *paths) -> Any:
        """Safely extract nested values from object using multiple possible paths."""
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
        
        # Helper function to calculate fuzzy match score
        def calculate_match_score(text: str, terms: List[str]) -> int:
            if not terms or not text: return 0
            text_lower = text.lower()
            score = 0
            for term in terms:
                term_lower = term.lower()
                if term_lower in text_lower: score += 3
                elif any(term_lower in word for word in text_lower.split()): score += 1
            return score
        
        # [Simplified logic for brevity - keeping your existing robust preprocessing]
        # Handle log data (use more specific check to avoid matching "changelog")
        if "log" in tool_name.lower() and "changelog" not in tool_name.lower() and "logs" in result:
            logs_data = result.get("logs", [])
            if logs_data and search_terms:
                scored_logs = []
                for log in logs_data:
                    msg = str(log.get("_msg") or log.get("message") or "")
                    service = str(log.get("object") or log.get("labels.type") or "")
                    score = calculate_match_score(f"{msg} {service}", search_terms)
                    scored_logs.append((score, log))
                scored_logs.sort(key=lambda x: x[0], reverse=True)
                logs_data = [log for score, log in scored_logs[:20]]
            
            simplified_logs = []
            for log in logs_data[:20]:
                simplified_logs.append({
                    "time": log.get("_time") or "Unknown",
                    "level": log.get("msg.logs.level") or "Unknown",
                    "msg": str(log.get("_msg") or "")[:150],
                    "service": log.get("object") or "Unknown"
                })
            return {"logs": simplified_logs, "count": len(simplified_logs)}

        # Handle incidents (keeping your existing logic structure)
        if "incident" in tool_name.lower():
            incidents_data = result.get("sample") or result.get("incidents") or []
            if incidents_data and search_terms:
                scored_incidents = []
                for inc in incidents_data:
                    score = calculate_match_score(f"{inc.get('title')} {inc.get('description')}", search_terms)
                    scored_incidents.append((score, inc))
                scored_incidents.sort(key=lambda x: x[0], reverse=True)
                incidents_data = [inc for score, inc in scored_incidents[:10]]
            
            simplified = []
            for inc in incidents_data[:10]:
                simplified.append({
                    "id": inc.get("id"),
                    "title": str(inc.get("title"))[:100],
                    "severity": inc.get("severity"),
                    "status": inc.get("status"),
                    "description": str(inc.get("description", ""))[:150],
                    "createdAt": inc.get("createdAt"),
                    "startedAt": inc.get("startedAt"),
                    "endedAt": inc.get("endedAt"),
                    "triggeredBy": inc.get("triggeredBy")
                })
            return {"incidents": simplified, "count": len(simplified)}

        # Handle changelogs (BEFORE resources to avoid conflict with get_changelog_by_resource)
        if "changelog" in tool_name.lower():
            changelogs_data = []
            
            logger.info(f"🔍 DEBUG {tool_name} - result keys: {list(result.keys())}")
            
            # Check multiple possible keys (like incidents and notifications do)
            if "changelogs" in result and isinstance(result["changelogs"], list):
                changelogs_data = result["changelogs"]
                logger.info(f"🔍 DEBUG {tool_name} - found 'changelogs' array with {len(changelogs_data)} items")
            elif "sample" in result and isinstance(result["sample"], list):
                changelogs_data = result["sample"]
                logger.info(f"🔍 DEBUG {tool_name} - found 'sample' array with {len(changelogs_data)} items")
            elif "items" in result and isinstance(result["items"], list):
                changelogs_data = result["items"]
                logger.info(f"🔍 DEBUG {tool_name} - found 'items' array with {len(changelogs_data)} items")
            elif "results" in result and isinstance(result["results"], list):
                changelogs_data = result["results"]
                logger.info(f"🔍 DEBUG {tool_name} - found 'results' array with {len(changelogs_data)} items")
            elif "changelog" in result and isinstance(result["changelog"], dict):
                changelogs_data = [result["changelog"]]
                logger.info(f"🔍 DEBUG {tool_name} - found single 'changelog' dict")
            
            if changelogs_data:
                simplified = []
                for cl in changelogs_data[:20]:
                    simplified.append({
                        "id": cl.get("id"),
                        "eventType": cl.get("eventType"),
                        "derivedType": cl.get("derivedType"),
                        "severity": cl.get("severity"),
                        "description": str(cl.get("description", ""))[:150],
                        "triggeredAt": cl.get("triggeredAt"),
                        "isActorHuman": cl.get("isActorHuman")
                    })
                logger.info(f"📋 Preprocessed {len(simplified)} changelogs for {tool_name}")
                return {"changelogs": simplified, "count": len(simplified)}
            else:
                logger.warning(f"⚠️ No changelog data found in result for {tool_name}. Keys: {list(result.keys())}")
                return {"changelogs": [], "count": 0}

        # Handle notifications (BEFORE resources to avoid conflict with get_notifications_by_resource)
        if "notification" in tool_name.lower():
            notifications_data = []
            
            # Single notification
            if "notification" in result and isinstance(result["notification"], dict):
                notifications_data = [result["notification"]]
            # Array of notifications
            elif "notifications" in result and isinstance(result["notifications"], list):
                notifications_data = result["notifications"]
            # Sample field (some APIs return this)
            elif "sample" in result and isinstance(result["sample"], list):
                notifications_data = result["sample"]
            
            if notifications_data:
                simplified = []
                for notif in notifications_data[:20]:
                    simplified.append({
                        "id": notif.get("id"),
                        "type": notif.get("type"),
                        "severity": notif.get("severity"),
                        "message": str(notif.get("message", ""))[:150],
                        "createdAt": notif.get("createdAt"),
                        "status": notif.get("status")
                    })
                return {"notifications": simplified, "count": len(simplified)}
            else:
                return {"notifications": [], "count": 0}

        # Handle resources - explicitly show when no events exist
        if "resource" in tool_name.lower():
            # Handle both single resource and array of resources
            resources_data = []
            
            # Single resource (from get_resource_by_id, get_resource_version, etc.)
            if "resource" in result and isinstance(result["resource"], dict):
                resources_data = [result["resource"]]
            # Array of resources (from get_resources, search_resources)
            elif "resources" in result and isinstance(result["resources"], list):
                resources_data = result["resources"]
            
            # Handle metadata responses
            if "metadata" in result and isinstance(result["metadata"], dict):
                # Return metadata as-is for metadata-specific queries
                return {"metadata": result["metadata"], "tool": tool_name}
            
            # Handle version responses
            if "version" in result:
                return {"version": result["version"], "tool": tool_name}
            
            # Handle tickets responses
            if "tickets" in result:
                return {"tickets": result["tickets"], "count": len(result["tickets"]) if isinstance(result["tickets"], list) else 0}
            
            # Apply scoring if search terms provided
            if resources_data and search_terms:
                scored_resources = []
                for res in resources_data:
                    name = str(res.get("resourceName", ""))
                    score = calculate_match_score(name, search_terms)
                    scored_resources.append((score, res))
                scored_resources.sort(key=lambda x: x[0], reverse=True)
                resources_data = [res for score, res in scored_resources[:10]]
            
            # Simplify resource data
            simplified = []
            for res in resources_data[:10]:
                metadata = res.get("metadata", {})
                events = metadata.get("events", [])
                
                # Extract event reasons if they exist
                event_reasons = []
                if events:
                    for event in events[:5]:
                        reason = event.get("reason", "")
                        if reason:
                            event_reasons.append(reason)
                
                simplified.append({
                    "id": res.get("id"),
                    "name": res.get("resourceName", "Unknown"),
                    "type": res.get("resourceType"),
                    "subType": res.get("resourceSubType"),
                    "status": res.get("resourceStatus", "Unknown"),
                    "provider": res.get("providerKey"),
                    "createdAt": res.get("createdAt"),
                    "events": event_reasons if event_reasons else ["NO_EVENTS"],
                    "event_count": len(events)
                })
            return {"resources": simplified, "count": len(simplified)}

        # Default return
        return result
    
    async def generate_enriched_response(self, state: Dict[str, Any], websocket=None) -> Dict[str, Any]:
        """Use LLM to generate contextual, actionable response with optional streaming"""
        try:
            if not self.llm:
                return self._fallback_response_generation(state)
            
            context_data = state.get("context_data", {})
            query_analysis = context_data.get("query_analysis", {})
            llm_analysis = query_analysis.get("llm_analysis", {})
            search_terms = llm_analysis.get("search_terms", [])
            
            mcp_results = state.get("mcp_results", [])
            tool_data = []
            for result in mcp_results:
                if result.get("success"):
                    tool_name = result.get("tool_name", "")
                    processed = self._preprocess_tool_result(result.get("result", {}), tool_name, search_terms)
                    tool_data.append({"tool": tool_name, "data": processed})
                    # Log preprocessing results for debugging
                    if "changelog" in tool_name.lower() or "notification" in tool_name.lower():
                        data_count = processed.get("count", len(processed) if isinstance(processed, list) else "N/A")
                        logger.info(f"🔍 Preprocessed {tool_name}: {data_count} items")
            
            # Include conversation history for context awareness
            conversation_history = state.get("conversation_history", [])
            
            context = {
                "original_query": state.get("user_query"),
                "tool_results": tool_data,
                "execution_summary": {"tools_executed": len(state.get("executed_tools", []))}
            }
            
            system_prompt = f"""You are a technical assistant providing narrative analysis. Answer ONLY using data from tool_results below.
Context: {json.dumps(context, indent=2)}

CONVERSATION CONTEXT AWARENESS:
- Previous conversation history is provided in the message history
- When user asks follow-up questions with pronouns (it, that, this, them), refer to previous conversation
- Example: If previous Q was "When did incident X occur?" and current Q is "Who triggered it?", "it" refers to incident X

CRITICAL ANTI-HALLUCINATION RULES (MANDATORY):
1. **NEVER make up or infer information not present in tool_results.**
2. **NEVER mention technical terms (like "OOMKilled", "CrashLoopBackOff", etc.) unless they appear EXACTLY in the tool_results data.**
3. **If tool_results has no specific root cause, say "The root cause is not clear from the available data."**
4. **Only describe what is ACTUALLY present in the data:**
   - Incidents: Report only the titles, descriptions, severities that are in tool_results
   - Resources: Report only the statuses, events that are in tool_results
   - Logs: Report only the messages, errors that are in tool_results
5. **If data shows "N/A", "Unknown", empty arrays, or null - acknowledge this gap.**
6. **Do NOT make diagnostic conclusions unless supported by explicit data.**
7. **When uncertain, describe what data IS available and what is MISSING.**

RESPONSE FORMAT - PARAGRAPH ANALYSIS (MANDATORY):
Write your response as flowing narrative paragraphs, NOT as structured lists or bullet points.

**Structure:**
1. **Opening Summary** (1-2 paragraphs): Provide high-level overview of the resource/incident/topic with key identifying information woven naturally into sentences.

2. **Detailed Analysis** (2-4 paragraphs): Discuss findings in narrative form:
   - Weave version, metadata, status information into descriptive sentences
   - Describe change history as a timeline narrative ("The resource experienced multiple deletion events, with the most recent occurring on December 1st at 10:30 AM...")
   - Connect related information contextually ("While the resource shows an Active status, the version information indicates...")
   
3. **Data Gaps & Context** (1 paragraph): Naturally describe what information is unavailable ("The available data does not include details about related tickets or notifications, which limits our ability to understand...")

**Style Guidelines:**
- Use natural, flowing sentences that connect ideas
- Avoid lists, bullet points, or structured sections with headers
- Use transitional phrases: "Additionally," "Furthermore," "However," "Notably," "In contrast,"
- Integrate specific data (IDs, timestamps, names) smoothly into narrative
- Write as if explaining to a colleague, not documenting in a report
- Keep paragraphs focused (3-5 sentences each)
- Use bold (**text**) sparingly for critical terms or values

**Example Paragraph Style:**
"Resource 50944068, identified as vector-0, is a Kubernetes Pod workload currently showing an Active status. The resource was initially created on November 26th, 2025, and has been operating under version v0.0.5 since December 1st when a deletion operation was recorded. The metadata reveals it operates within the vector namespace and is categorized as a container orchestrator workload with minimal resource consumption at 0m CPU and 43 MiB memory."

Format: Flowing narrative analysis → Integrated data points → Contextual gaps → Natural conclusions."""
            
            # Build messages with conversation history for context
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history (last 5 turns for context)
            for msg in conversation_history[-5:]:
                if msg.get("role") == "user":
                    messages.append({"role": "user", "content": msg.get("content", "")})
                elif msg.get("role") == "assistant":
                    messages.append({"role": "assistant", "content": msg.get("content", "")})
            
            # Add current query
            messages.append({"role": "user", "content": f"Answer this: {state.get('user_query')}"})
            
            import re
            
            if websocket:
                content = ""
                pending_newlines = 0
                async for chunk in self.llm.astream(messages):
                    token = chunk.content
                    if token:
                        content += token
                        # Streaming post-process: collapse multiple newlines in real-time
                        for char in token:
                            if char == '\n':
                                pending_newlines += 1
                            else:
                                # Flush pending newlines (max 1)
                                if pending_newlines > 0:
                                    await websocket.send_text(json.dumps({"on_chat_model_stream": "\n"}))
                                    pending_newlines = 0
                                # Send the actual character
                                await websocket.send_text(json.dumps({"on_chat_model_stream": char}))
                        
                # Flush any remaining newline (max 1)
                if pending_newlines > 0:
                    await websocket.send_text(json.dumps({"on_chat_model_stream": "\n"}))
            else:
                response = self.llm.invoke(messages)
                content = response.content
            
            # Post-process: Remove excessive newlines for compact display
            # Replace 3+ newlines with 2, and 2 newlines with 1
            content = re.sub(r'\n{3,}', '\n\n', content)  # Max 2 newlines
            content = re.sub(r'\n\n', '\n', content)       # Convert double to single
            
            metadata_response = await self._generate_metadata(state, content)
            
            return {
                "final_response": content,
                "forward_links": metadata_response.get("forward_links", []),
                "recommendations": metadata_response.get("recommendations", []),
                "insights": metadata_response.get("insights", {})
            }
            
        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return self._fallback_response_generation(state)
    
    async def _generate_metadata(self, state: Dict[str, Any], response_text: str) -> Dict[str, Any]:
        """Generate forward links and recommendations"""
        try:
            prompt = f"Generate 3 forward links (questions) and recommendations based on: {response_text}. Return JSON."
            messages = [{"role": "user", "content": prompt}]
            response = self.llm.invoke(messages)
            return json.loads(self._extract_json_from_response(response.content))
        except:
            return {"forward_links": [], "recommendations": [], "insights": {}}
    
    def _fallback_query_analysis(self, user_query: str) -> Dict[str, Any]:
        """Simple fallback analysis"""
        return {
            "query_type": "conversational",
            "search_terms": user_query.split(),
            "strict_service_name": None
        }
    
    def _fallback_tool_planning(self, query_analysis: Dict[str, Any], available_tools: List[str]) -> List[Dict[str, Any]]:
        """Smart fallback tool planning"""
        strict_name = query_analysis.get("strict_service_name")
        search_terms = query_analysis.get("search_terms", [])
        
        # Priority 1: Use strict name if available
        if strict_name and strict_name not in ["null", "None", ""]:
            query = strict_name
        # Priority 2: Use first search term
        elif search_terms:
            query = search_terms[0]
        else:
            query = ""
            
        return [{"name": "get_incidents", "parameters": {}}]
    
    def _fallback_response_generation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {"final_response": "I'm having trouble connecting to the tools right now.", "forward_links": [], "recommendations": [], "insights": {}}


# Global instance
llm_client = LLMDecisionMaker()