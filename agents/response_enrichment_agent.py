"""
Response Enrichment Agent - Enriches the final response with context and recommendations
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from core.state import ChatState
from utils.llm_client import llm_client

logger = logging.getLogger(__name__)


class ResponseEnrichmentAgent:
    """
    Agent responsible for enriching responses with smart fallbacks and structured annotations
    """
    
    def __init__(self):
        self.name = "ResponseEnrichmentAgent"
    
    async def enrich_response(self, state: ChatState) -> ChatState:
        """Enrich the response with forward links, recommendations, and insights"""
        
        try:
            logger.info("✨ Enriching response")
            
            # Use LLM to generate enriched response
            try:
                logger.info("🤖 Calling LLM to generate enriched response...")
                
                # Check if websocket is available for streaming (from workflow context)
                websocket = state.get("_websocket_ref")
                if websocket:
                    logger.info("🌊 Using streaming mode for response generation")
                    llm_response = await llm_client.generate_enriched_response(state, websocket=websocket)
                else:
                    logger.info("📝 Using non-streaming mode for response generation")
                    llm_response = await llm_client.generate_enriched_response(state)
                
                logger.info(f"🔍 LLM response type: {type(llm_response)}, value: {str(llm_response)[:200] if llm_response else 'None'}")
                
                # Check if llm_response is None or not a dict
                if llm_response is None:
                    raise ValueError("LLM response is None")
                if not isinstance(llm_response, dict):
                    raise ValueError(f"LLM response is not a dictionary, got {type(llm_response)}")
                
                final_response = llm_response.get("final_response", "")
                forward_links = llm_response.get("forward_links", [])
                recommendations = llm_response.get("recommendations", [])
                insights = llm_response.get("insights", {})
                
                logger.info(f"📝 LLM generated response: {len(final_response)} chars")
                
            except Exception as llm_error:
                logger.error(f"❌ LLM generation failed: {llm_error}. Engaging smart fallback.")
                # Smart Fallback: Construct response from raw data
                final_response = self._create_smart_fallback_response(state)
                forward_links = self._generate_context_aware_links(state)
                recommendations = self._generate_default_recommendations(state)
                insights = {"error": "Generated via fallback logic due to LLM unavailability"}
            
            # Create structured annotations (better for frontend)
            annotations = self._create_structured_annotations(state)
            
            # Quality Assessment & Logging
            quality_score = self._assess_enrichment_quality(forward_links, annotations)
            if quality_score < 0.5:
                logger.warning(f"⚠️ Low enrichment quality score: {quality_score:.2f}")
            
            # Compile enrichment data
            enrichment_data = {
                "forward_links": forward_links,
                "annotations": annotations,
                "contextual_insights": insights,
                "recommendations": recommendations,
                "enrichment_timestamp": datetime.now().isoformat(),
                "enrichment_quality": quality_score
            }
            
            # Update state
            updated_state = {
                **state,
                "enrichment_data": enrichment_data,
                "forward_links": forward_links,
                "annotations": annotations,
                "final_response": final_response,
                "current_agent": self.name
            }
            
            logger.info(f"✅ Response enrichment completed with {len(forward_links)} forward links")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"❌ Critical Enrichment Failure: {str(e)}")
            # Return basic response without enrichment using smart fallback
            return {
                **state,
                "final_response": self._create_smart_fallback_response(state),
                "error_count": state.get("error_count", 0) + 1,
                "enrichment_data": {
                    "error": str(e),
                    "enrichment_quality": 0.0
                }
            }
    
    def _create_smart_fallback_response(self, state: ChatState) -> str:
        """
        Creates a readable response directly from tool data without LLM.
        Iterates through successful tools and extracts 'titles', 'messages', or 'names'.
        """
        mcp_results = state.get("mcp_results", [])
        successful_tools = [r for r in mcp_results if r.get("success")]
        
        if not successful_tools:
            return f"I attempted to analyze '{state.get('user_query')}', but the tools provided no data."

        response_lines = [f"I executed {len(mcp_results)} tools. Here are the results:\n"]

        for result in successful_tools:
            tool_name = result.get("tool_name", "Unknown Tool")
            data = result.get("result", {})
            
            # Dynamic parsing based on common data shapes
            count = data.get("count", 0)
            response_lines.append(f"\n**{tool_name}** ({count} items found):")
            
            # Try to find a list in the data (incidents, logs, resources)
            found_list = None
            for key in ["incidents", "logs", "resources", "tickets", "changelogs", "notifications"]:
                if key in data and isinstance(data[key], list):
                    found_list = data[key]
                    break
            
            if found_list:
                for item in found_list[:3]:  # Limit to top 3 for brevity
                    # Try to find a readable label
                    label = (item.get("title") or item.get("message") or 
                             item.get("name") or item.get("id") or "Item")
                    response_lines.append(f"• {str(label)[:100]}")
                if len(found_list) > 3:
                    response_lines.append(f"• ...and {len(found_list) - 3} more.")
            else:
                response_lines.append("• Data available (view details).")
            
            response_lines.append("")  # spacer

        return "\n".join(response_lines)
    
    def _generate_context_aware_links(self, state: ChatState) -> List[str]:
        """
        Generate links using specific entities found in the query analysis.
        Uses strict_service_name if available for more relevant suggestions.
        """
        context_data = state.get("context_data", {})
        query_analysis = context_data.get("query_analysis", {})
        
        # Use the "Smart Logic" strict_service_name if available
        service_name = query_analysis.get("strict_service_name")
        query_type = state.get("query_type", "general")
        search_terms = query_analysis.get("search_terms", [])

        links = []
        
        # Priority 1: Service-specific links
        if service_name:
            links.append(f"Show logs for {service_name}")
            links.append(f"Check incidents for {service_name}")
            links.append(f"View topology for {service_name}")
        
        # Priority 2: Search term based links
        elif search_terms:
            primary_term = search_terms[0]
            links.append(f"Search logs for {primary_term}")
            links.append(f"Find incidents mentioning {primary_term}")
        
        # Priority 3: Fallback to query type templates
        if not links:
            defaults = {
                "incident_analysis": ["Show active incidents", "Check system health", "View recent changes"],
                "infrastructure_query": ["List all pods", "Show failed resources", "Check cluster status"],
                "graph_query": ["Show database schema", "Count all nodes", "Explore relationships"],
                "log_analysis": ["View error logs", "Check warning patterns", "Analyze log trends"],
                "root_cause": ["Investigate timeline", "Check dependencies", "Review deployments"]
            }
            links = defaults.get(query_type, ["View details", "Get help", "Refine query"])
            
        return links[:4]  # Limit to 4 links for clean UI
    
    def _generate_default_recommendations(self, state: ChatState) -> List[str]:
        """Generate default recommendations"""
        return [
            "Review the analysis results",
            "Monitor the situation",
            "Consider follow-up actions if needed"
        ]
    
    def _create_structured_annotations(self, state: ChatState) -> List[Dict[str, str]]:
        """
        Create structured annotations for the UI.
        Returns dictionaries with label, type, and icon for frontend rendering as badges/chips.
        """
        annotations = []
        
        # Execution Badge
        executed_tools = state.get("executed_tools", [])
        if executed_tools:
            annotations.append({
                "label": f"{len(executed_tools)} Tools Ran",
                "type": "info",
                "icon": "terminal",
                "tooltip": f"Executed: {', '.join(executed_tools[:3])}"
            })
        
        # Confidence Badge
        context_data = state.get("context_data", {})
        query_analysis = context_data.get("query_analysis", {})
        confidence = query_analysis.get("confidence_score", 0)
        
        if confidence > 0:
            if confidence > 0.8:
                confidence_type = "success"
                confidence_icon = "shield-check"
            elif confidence > 0.5:
                confidence_type = "warning"
                confidence_icon = "shield"
            else:
                confidence_type = "error"
                confidence_icon = "shield-alert"
                
            annotations.append({
                "label": f"{confidence:.0%} Confidence",
                "type": confidence_type,
                "icon": confidence_icon
            })
        
        # Query Type Badge
        query_type = state.get("query_type", "")
        if query_type:
            type_icons = {
                "incident_analysis": "alert-circle",
                "infrastructure_query": "server",
                "log_analysis": "file-text",
                "graph_query": "share-2",
                "root_cause": "search"
            }
            annotations.append({
                "label": query_type.replace("_", " ").title(),
                "type": "default",
                "icon": type_icons.get(query_type, "help-circle")
            })
        
        # Service Badge (if strict_service_name found)
        service_name = query_analysis.get("strict_service_name")
        if service_name:
            annotations.append({
                "label": f"Service: {service_name}",
                "type": "primary",
                "icon": "box"
            })
        
        # Timestamp Badge
        annotations.append({
            "label": datetime.now().strftime('%H:%M:%S'),
            "type": "default",
            "icon": "clock"
        })
        
        return annotations
    
    def _assess_enrichment_quality(self, forward_links: List[str], annotations: List[Any]) -> float:
        """
        Assess the quality of the enrichment.
        Logs warnings if quality drops below threshold.
        """
        quality_score = 0.0
        
        # Forward links quality
        if forward_links:
            quality_score += 0.4
        if len(forward_links) >= 3:
            quality_score += 0.2
        
        # Annotations quality
        if annotations:
            quality_score += 0.3
        if len(annotations) >= 3:
            quality_score += 0.1
        
        return quality_score
