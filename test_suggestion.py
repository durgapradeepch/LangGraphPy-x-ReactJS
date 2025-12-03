#!/usr/bin/env python3
"""Test script for the suggestion system"""
import asyncio
import sys
from graph import invoke_our_graph

class MockWebSocket:
    """Mock WebSocket for testing"""
    def __init__(self):
        self.messages = []
        self.response_parts = []
    
    async def send_text(self, text):
        """Capture sent messages"""
        self.messages.append(text)
        # Capture just the response content for analysis
        if "on_chat_model_stream" in text:
            import json
            try:
                data = json.loads(text)
                self.response_parts.append(data.get("on_chat_model_stream", ""))
            except:
                pass

async def test_suggestion():
    """Test the suggestion system with a query that returns no exact results"""
    mock_ws = MockWebSocket()
    query = "describe me about the incident happened on 'Mit-runtime-api-services'"
    session_id = "test-session-123"
    
    print(f"🧪 Testing query: {query}")
    print(f"📋 Session ID: {session_id}\n")
    
    # Invoke the graph
    await invoke_our_graph(mock_ws, query, session_id)
    
    # Reconstruct the full response
    full_response = "".join(mock_ws.response_parts)
    
    print(f"\n✅ Test complete. Received {len(mock_ws.messages)} messages")
    print(f"\n{'='*80}")
    print(f"📝 FULL RESPONSE:")
    print(f"{'='*80}")
    print(full_response)
    print(f"{'='*80}\n")
    
    # Check for suggestion keywords
    suggestion_keywords = ["similar", "suggest", "found these", "related", "might be looking for"]
    has_suggestions = any(keyword in full_response.lower() for keyword in suggestion_keywords)
    
    if has_suggestions:
        print("✅ SUCCESS: Response contains suggestions!")
    else:
        print("❌ ISSUE: No suggestions found in response")
        print("\nResponse says no data available - suggestion system may not have triggered")

if __name__ == "__main__":
    asyncio.run(test_suggestion())
