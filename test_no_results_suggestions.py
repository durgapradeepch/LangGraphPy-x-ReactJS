"""
Test No-Results Suggestion Enhancement

Tests that the system provides intelligent suggestions when no exact match is found.
"""

import asyncio
import sys
sys.path.append('/Users/pradeep/LangGraphPy-x-ReactJS')

from utils.llm_client import llm_client
from utils.mcp_client import mcp_client_manager


async def test_no_results_handling():
    """Test the no-results suggestion feature"""
    
    print("=" * 80)
    print("NO-RESULTS SUGGESTION ENHANCEMENT TEST")
    print("=" * 80)
    print()
    
    # Simulate a state with no results for "Mit-runtime-api-services"
    test_state = {
        "user_query": "describe me about the incident happened on 'Mit-runtime-api-services'",
        "context_data": {
            "query_analysis": {
                "llm_analysis": {
                    "search_terms": ["Mit-runtime-api-services", "runtime", "api", "services"],
                    "multi_entity": False
                }
            }
        },
        "mcp_results": [
            {
                "success": True,
                "tool_name": "search_incidents",
                "result": {
                    "incidents": [],
                    "count": 0,
                    "page": 1,
                    "page_size": 20
                }
            }
        ],
        "executed_tools": ["search_incidents"],
        "conversation_history": []
    }
    
    print("Test Case: Query for non-existent 'Mit-runtime-api-services'")
    print(f"Search Terms: {test_state['context_data']['query_analysis']['llm_analysis']['search_terms']}")
    print()
    print("Expected Behavior:")
    print("1. Detect empty result")
    print("2. Extract keywords: runtime, api, services")
    print("3. Search for similar incidents with those keywords")
    print("4. Return suggestions in response")
    print()
    print("-" * 80)
    print()
    
    try:
        # Test the _is_empty_result method
        print("Step 1: Testing empty result detection...")
        empty_result = {"incidents": [], "count": 0}
        is_empty = llm_client._is_empty_result(empty_result)
        print(f"✅ Empty result detected: {is_empty}")
        print()
        
        # Test the _find_similar_entities method
        print("Step 2: Finding similar entities...")
        search_terms = ["Mit-runtime-api-services", "runtime", "api"]
        empty_tools = ["search_incidents"]
        
        suggestions = await llm_client._find_similar_entities(test_state, search_terms, empty_tools)
        
        if suggestions:
            print(f"✅ Found suggestions!")
            print(f"Message: {suggestions['message']}")
            print(f"Similar items count: {len(suggestions['similar_items'])}")
            print()
            print("Suggestions:")
            for item in suggestions['similar_items']:
                print(f"  • {item['suggestion']}")
            print()
        else:
            print("⚠️  No suggestions found")
            print()
        
        print("-" * 80)
        print()
        print("Step 3: Expected LLM Response Format:")
        print()
        print("I couldn't find an exact match for 'Mit-runtime-api-services'. However,")
        print("I found these similar incidents:")
        print()
        if suggestions and suggestions['similar_items']:
            for item in suggestions['similar_items'][:3]:
                print(f"  • {item['suggestion']}")
        print()
        print("Would you like details about one of these?")
        print()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)
    print()
    print("To test end-to-end:")
    print("1. Open web UI: http://localhost:3000")
    print("2. Query: 'describe me about the incident happened on Mit-runtime-api-services'")
    print("3. Expect response with suggestions for similar incidents")
    print()


if __name__ == "__main__":
    asyncio.run(test_no_results_handling())
