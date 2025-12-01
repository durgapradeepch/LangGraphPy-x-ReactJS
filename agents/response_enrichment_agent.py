"""
Response Enrichment Agent - Enriches the final response with context and recommendations
"""

import logging
from datetime import datetime
from typing import Dict, Any, List
from state import ChatState
from utils.llm_client import llm_client

logger = logging.getLogger(__name__)


class ResponseEnrichmentAgent:
    """
    Agent responsible for enriching responses
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
                logger.error(f"❌ LLM response generation failed: {llm_error}, using fallback")
                final_response = self._create_fallback_response(state)
                forward_links = self._generate_default_forward_links(state)
                recommendations = self._generate_default_recommendations(state)
                insights = {}
            
            # Create annotations
            annotations = self._create_annotations(state)
            
            # Compile enrichment data
            enrichment_data = {
                "forward_links": forward_links,
                "annotations": annotations,
                "contextual_insights": insights,
                "recommendations": recommendations,
                "enrichment_timestamp": datetime.now().isoformat(),
                "enrichment_quality": self._assess_enrichment_quality(forward_links, annotations)
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
            logger.error(f"❌ Response enrichment failed: {str(e)}")
            # Return basic response without enrichment
            return {
                **state,
                "final_response": self._create_fallback_response(state),
                "error_count": state.get("error_count", 0) + 1
            }
    
    def _create_fallback_response(self, state: ChatState) -> str:
        """Create a fallback response when LLM fails"""
        mcp_results = state.get("mcp_results", [])
        success_count = len([r for r in mcp_results if r.get("success")])
        
        response_parts = [
            f"I analyzed your query: '{state.get('user_query')}'",
            f"\nExecuted {len(mcp_results)} tools with {success_count} successful.",
        ]
        
        # Add summary of results
        if mcp_results:
            response_parts.append("\n\nResults summary:")
            for result in mcp_results[:3]:  # Show first 3 results
                tool_name = result.get("tool_name", "unknown")
                if result.get("success"):
                    response_parts.append(f"- {tool_name}: Success")
                else:
                    response_parts.append(f"- {tool_name}: Failed")
        
        return "".join(response_parts)
    
    def _generate_default_forward_links(self, state: ChatState) -> List[str]:
        """Generate default forward links"""
        query_type = state.get("query_type", "general")
        
        link_templates = {
            "incident_analysis": [
                "View related incidents",
                "Check recent changes",
                "Analyze error patterns"
            ],
            "exploration": [
                "See more details",
                "View related resources",
                "Check historical data"
            ],
            "root_cause": [
                "Investigate deeper",
                "Check dependencies",
                "Review recent deployments"
            ]
        }
        
        return link_templates.get(query_type, ["Learn more", "View details", "Check status"])
    
    def _generate_default_recommendations(self, state: ChatState) -> List[str]:
        """Generate default recommendations"""
        return [
            "Review the analysis results",
            "Monitor the situation",
            "Consider follow-up actions if needed"
        ]
    
    def _create_annotations(self, state: ChatState) -> List[str]:
        """Create contextual annotations for the response"""
        annotations = []
        
        # Add execution summary
        executed_tools = state.get("executed_tools", [])
        if executed_tools:
            annotations.append(f"Executed {len(executed_tools)} tools: {', '.join(executed_tools[:3])}")
        
        # Add confidence score
        confidence_score = state.get("confidence_score", 0.0)
        if confidence_score:
            annotations.append(f"Analysis confidence: {confidence_score:.0%}")
        
        # Add timestamp
        annotations.append(f"Analysis timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        return annotations
    
    def _assess_enrichment_quality(self, forward_links: List[str], annotations: List[str]) -> float:
        """Assess the quality of the enrichment"""
        quality_score = 0.0
        
        if forward_links:
            quality_score += 0.4
        if annotations:
            quality_score += 0.3
        if len(forward_links) >= 3:
            quality_score += 0.2
        if len(annotations) >= 2:
            quality_score += 0.1
        
        return quality_score
