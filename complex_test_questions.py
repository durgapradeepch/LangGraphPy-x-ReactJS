#!/usr/bin/env python3
"""
10 Complex Test Questions for LLM System
These questions test various capabilities: cross-entity linking, multi-entity queries,
comprehensive analysis, suggestions, search, and filtering.
"""

COMPLEX_TEST_QUESTIONS = [
    {
        "id": 1,
        "question": "Show me incident 1507 and all its affected resources with their complete details",
        "tests": ["Cross-entity linking", "Comprehensive query", "ID extraction", "Follow-up execution"],
        "expected_tools": ["get_incident_by_id", "get_resource_by_id (multiple)"],
        "difficulty": "High"
    },
    {
        "id": 2,
        "question": "Give me all GCP incidents, their related resources, open tickets, and recent notifications",
        "tests": ["Multi-entity summary", "Multiple tool execution", "Keyword filtering", "Aggregation"],
        "expected_tools": ["search_incidents", "search_resources", "search_tickets", "get_notifications"],
        "difficulty": "Very High"
    },
    {
        "id": 3,
        "question": "Tell me everything about vector-0 resource including incidents, tickets, and changelogs",
        "tests": ["Comprehensive query", "Service name extraction", "Cross-entity relationships"],
        "expected_tools": ["search_resources", "get_resource_by_id", "search_incidents", "search_tickets", "search_changelogs"],
        "difficulty": "High"
    },
    {
        "id": 4,
        "question": "Show me top 5 critical incidents from last week sorted by severity",
        "tests": ["Filtering", "Sorting", "Limit", "Time range", "Severity matching"],
        "expected_tools": ["search_incidents"],
        "difficulty": "Medium"
    },
    {
        "id": 5,
        "question": "Find all open tickets related to runtime APIs and their associated incidents",
        "tests": ["Status filtering", "Keyword search", "Cross-entity linking", "Relationship discovery"],
        "expected_tools": ["search_tickets", "search_incidents"],
        "difficulty": "High"
    },
    {
        "id": 6,
        "question": "What incidents happened on 'Mit-runtime-api-services'?",
        "tests": ["No-results handling", "Smart suggestions", "Fuzzy matching", "Keyword extraction"],
        "expected_tools": ["search_incidents", "suggestion system triggers"],
        "difficulty": "Medium (tests suggestion system)"
    },
    {
        "id": 7,
        "question": "Get resource 50944068 with all related incidents, tickets, and recent changelogs",
        "tests": ["Numeric ID extraction", "Comprehensive details", "Multiple entity types", "Resource-centric query"],
        "expected_tools": ["get_resource_by_id", "search_incidents", "search_tickets", "search_changelogs"],
        "difficulty": "High"
    },
    {
        "id": 8,
        "question": "Show me all high severity incidents in payment service with their root cause analysis",
        "tests": ["Service name filtering", "Severity filtering", "Analysis", "Keyword matching"],
        "expected_tools": ["search_incidents", "get_incident_by_id (for analysis)"],
        "difficulty": "Medium-High"
    },
    {
        "id": 9,
        "question": "List all CrashLoopBackOff resources and show me incidents that affected them in the last 24 hours",
        "tests": ["Resource status filtering", "Time range", "Incident-resource linking", "Reverse relationship"],
        "expected_tools": ["search_resources", "search_incidents", "cross-entity linking"],
        "difficulty": "High"
    },
    {
        "id": 10,
        "question": "Compare incidents, tickets, and notifications for acme-cart-services vs runtime-api",
        "tests": ["Multi-entity comparison", "Service comparison", "Aggregation", "Multiple keywords"],
        "expected_tools": ["search_incidents", "search_tickets", "get_notifications", "comparison logic"],
        "difficulty": "Very High"
    }
]


def print_questions():
    """Print all test questions with details"""
    print("=" * 100)
    print("🧪 10 COMPLEX TEST QUESTIONS FOR LLM SYSTEM")
    print("=" * 100)
    print()
    
    for q in COMPLEX_TEST_QUESTIONS:
        print(f"{'='*100}")
        print(f"Question #{q['id']} - Difficulty: {q['difficulty']}")
        print(f"{'='*100}")
        print(f"❓ {q['question']}")
        print()
        print(f"🎯 Tests: {', '.join(q['tests'])}")
        print(f"🔧 Expected Tools: {', '.join(q['expected_tools'])}")
        print()


def get_test_script():
    """Generate test script to run all questions"""
    script = '''#!/usr/bin/env python3
"""
Automated test script for complex questions
Run: python complex_test_questions.py --run-tests
"""
import asyncio
from graph import invoke_our_graph

class MockWebSocket:
    def __init__(self):
        self.messages = []
        self.response_parts = []
    
    async def send_text(self, text):
        self.messages.append(text)
        if "on_chat_model_stream" in text:
            import json
            try:
                data = json.loads(text)
                self.response_parts.append(data.get("on_chat_model_stream", ""))
            except:
                pass

async def test_question(question_id, question_text):
    """Test a single question"""
    print(f"\\n{'='*80}")
    print(f"Testing Question #{question_id}")
    print(f"{'='*80}")
    print(f"❓ {question_text}")
    
    mock_ws = MockWebSocket()
    session_id = f"test-q{question_id}"
    
    await invoke_our_graph(mock_ws, question_text, session_id)
    
    full_response = "".join(mock_ws.response_parts)
    
    print(f"\\n📝 Response Length: {len(full_response)} chars")
    print(f"💬 Messages Sent: {len(mock_ws.messages)}")
    print(f"\\n{'='*80}")
    print("📄 RESPONSE:")
    print(f"{'='*80}")
    print(full_response[:500] + "..." if len(full_response) > 500 else full_response)
    print(f"{'='*80}\\n")

async def run_all_tests():
    """Run all test questions"""
    for q in COMPLEX_TEST_QUESTIONS:
        await test_question(q['id'], q['question'])
        await asyncio.sleep(1)  # Small delay between tests

if __name__ == "__main__":
    import sys
    
    if "--run-tests" in sys.argv:
        print("🚀 Running all complex test questions...")
        asyncio.run(run_all_tests())
    else:
        print_questions()
        print()
        print("To run automated tests: python complex_test_questions.py --run-tests")
'''
    return script


if __name__ == "__main__":
    import sys
    
    if "--run-tests" in sys.argv:
        exec(get_test_script())
    else:
        print_questions()
        print()
        print("=" * 100)
        print("💡 TO RUN AUTOMATED TESTS:")
        print("=" * 100)
        print("python complex_test_questions.py --run-tests")
        print()
        print("=" * 100)
        print("💡 TO TEST INDIVIDUALLY IN WEB UI:")
        print("=" * 100)
        print("1. Start server: bash start.sh")
        print("2. Open: http://localhost:3000")
        print("3. Copy-paste questions from above")
        print()
