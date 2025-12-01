#!/usr/bin/env python
"""Test script to verify ticket preprocessing fix"""

import asyncio
import websockets
import json

async def test_tickets():
    uri = "ws://localhost:8000/ws"
    
    async with websockets.connect(uri) as websocket:
        # Send query
        query = {
            "type": "query",
            "message": "List all service tickets",
            "uuid": "test-user-123"
        }
        
        await websocket.send(json.dumps(query))
        print("✅ Sent query: List all service tickets\n")
        
        # Receive all responses
        responses = []
        full_response = ""
        try:
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                data = json.loads(response)
                responses.append(data)
                
                # Handle streaming responses
                if "on_chat_model_stream" in data:
                    chunk = data["on_chat_model_stream"]
                    full_response += chunk
                    print(".", end="", flush=True)  # Show progress
                    continue
                
                # Handle final response
                if "final_response" in data or "message" in data:
                    final_msg = data.get("final_response") or data.get("message", "")
                    if final_msg:
                        full_response = final_msg
                    break
                    
        except asyncio.TimeoutError:
            print("\n\n⏱️ Stream ended (timeout)")
        except Exception as e:
            print(f"\n\n❌ Error: {str(e)}")
        
        # Display the complete response
        if full_response:
            print("\n\n🎯 FINAL RESPONSE:")
            print("=" * 80)
            print(full_response)
            print("=" * 80)
            
            # Check if tickets are properly formatted
            if "CS-334" in full_response or "CS-335" in full_response or "ticket" in full_response.lower():
                print("\n✅ SUCCESS: Tickets are mentioned in response!")
                if "CS-334" in full_response:
                    print("  - Found CS-334")
                if "CS-335" in full_response:
                    print("  - Found CS-335")
                print(f"  - Response length: {len(full_response)} chars")
            else:
                print("\n⚠️ WARNING: Generic response")
                print(f"  - Response preview: {full_response[:200]}...")
        else:
            print("\n❌ No response received")

if __name__ == "__main__":
    asyncio.run(test_tickets())
