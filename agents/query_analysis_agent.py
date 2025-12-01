"""
Query Analysis Agent - Analyzes user queries to determine intent and plan execution
"""

import json
import logging
from typing import Dict, Any
from state import ChatState, update_state_context
from utils.llm_client import llm_client

logger = logging.getLogger(__name__)


class QueryAnalysisAgent:
    """
    Agent responsible for analyzing user queries
    """
    
    def __init__(self):
        self.name = "QueryAnalysisAgent"
    
    async def analyze_query(self, state: ChatState) -> ChatState:
        """Analyze user query to determine intent and extract entities"""
        
        try:
            logger.info(f"🔍 Analyzing query: '{state['user_query'][:50]}...'")
            
            # Use LLM to analyze query
            available_tools = state.get("available_tools", [])
            tool_schemas = state.get("tool_schemas", [])
            analysis = await llm_client.analyze_query_intent(
                state["user_query"],
                available_tools
            )
            
            # Plan tool sequence based on analysis (pass tool schemas)
            tool_plan = await llm_client.plan_tool_sequence(
                analysis,
                tool_schemas,  # Pass full schemas instead of just names
                state.get("context_data", {})
            )
            
            # Log tool plan for debugging
            logger.info(f"📋 Tool plan: {json.dumps(tool_plan, indent=2)}")
            
            # Update state with analysis results
            updated_state = {
                **state,
                "query_type": analysis.get("query_type", "general"),
                "intent": analysis.get("intent", "unknown"),
                "entities": analysis.get("entities", []),
                "confidence_score": analysis.get("confidence_score", 0.0),
                "specificity_level": analysis.get("specificity_level", "medium"),
                "tool_plan": tool_plan,
                "current_agent": self.name
            }
            
            # Store full analysis in context
            updated_state = update_state_context(updated_state, "query_analysis", {
                "llm_analysis": analysis,
                "tool_plan": tool_plan
            })
            
            logger.info(f"✅ Query analyzed: type={analysis.get('query_type')}, confidence={analysis.get('confidence_score')}")
            
            return updated_state
            
        except Exception as e:
            logger.error(f"❌ Query analysis failed: {str(e)}")
            return {
                **state,
                "error_count": state.get("error_count", 0) + 1,
                "workflow_status": "degraded"
            }
