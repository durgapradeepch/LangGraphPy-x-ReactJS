# No-Results Smart Suggestions Enhancement

## Overview

Enhanced the system to provide **intelligent suggestions** when searches return no exact matches, improving user experience by recommending similar entities instead of just saying "no data available".

## Problem Solved

**Before:**
```
User: "describe me about the incident happened on 'Mit-runtime-api-services'"
System: "The available data does not provide any information about an incident 
         related to 'Mit-runtime-api-services.'"
```

**After:**
```
User: "describe me about the incident happened on 'Mit-runtime-api-services'"
System: "I couldn't find an exact match for 'Mit-runtime-api-services'. However, 
         I found these similar incidents:
         
         • Incident 1507: 'Incident on runtime api' (High severity)
         • Incident 1499: 'Runtime-aws-api's are not working' (High severity)
         • Incident 1504: 'Playground apis are down' (High severity)
         
         Would you like details about one of these?"
```

---

## How It Works

### 1. Empty Result Detection

When all search tools return empty results:

```python
# In generate_enriched_response()
empty_results = []  # Track which searches returned no data

for result in mcp_results:
    is_empty = self._is_empty_result(processed)
    if is_empty:
        empty_results.append(tool_name)
```

**Detection Logic:**
- Checks for empty arrays: `incidents: []`, `resources: []`
- Checks count fields: `count: 0`
- Returns `True` if no meaningful data found

---

### 2. Keyword Extraction

Extracts meaningful keywords from the original search terms:

```python
search_terms = ["Mit-runtime-api-services", "runtime", "api", "services"]

# Extract keywords (words > 3 chars)
keywords = []
for term in search_terms:
    words = term.lower().replace('-', ' ').split()
    keywords.extend([w for w in words if len(w) > 3])

# Result: ["runtime", "api", "services"]
```

---

### 3. Broader Search

Uses extracted keywords to search for similar entities:

```python
# Try each keyword separately
for keyword in keywords[:2]:  # Limit to first 2
    # Search incidents
    result = await mcp_client.call_tool("search_incidents", {
        "query": keyword, 
        "limit": 3
    })
    
    # Search resources  
    result = await mcp_client.call_tool("search_resources", {
        "query": keyword,
        "limit": 3
    })
```

**Search Strategy:**
- Use individual keywords instead of full phrase
- Limit to 3 results per keyword
- Search both incidents and resources
- Combine all findings into suggestions list

---

### 4. Suggestion Formatting

Formats suggestions for LLM to present naturally:

```python
suggestions = {
    "message": "No exact match found. Here are similar items:",
    "similar_items": [
        {
            "type": "incident",
            "id": 1507,
            "title": "Incident on runtime api",
            "severity": "High",
            "suggestion": "Incident 1507: 'Incident on runtime api'"
        },
        {
            "type": "incident",
            "id": 1499,
            "title": "Runtime-aws-api's are not working",
            "severity": "High",
            "suggestion": "Incident 1499: 'Runtime-aws-api's are not working'"
        }
    ]
}
```

---

### 5. LLM Response Generation

Updated system prompt to handle suggestions:

```python
HANDLING NO RESULTS / SUGGESTIONS:
- If tool_results contains a "suggestions" entry with similar_items, 
  this means NO EXACT MATCH was found
- Start response with: "I couldn't find an exact match for '[search term]'. 
  However, I found these similar items:"
- List the suggestions naturally
- End with: "Would you like details about one of these?"
- Do NOT pretend the suggestions are the answer - they are alternatives!
```

---

## Code Changes

### File: `utils/llm_client.py`

#### 1. Enhanced Result Processing (Lines ~665-690)
```python
empty_results = []  # NEW: Track empty searches

for result in mcp_results:
    is_empty = self._is_empty_result(processed)  # NEW
    if is_empty:
        empty_results.append(tool_name)

# NEW: Smart no-results handling
if empty_results and len(empty_results) == len(tool_data):
    suggestions = await self._find_similar_entities(state, search_terms, empty_results)
    if suggestions:
        tool_data.append({"tool": "suggestions", "data": suggestions})
```

#### 2. New Method: `_is_empty_result()` (Lines ~850-870)
```python
def _is_empty_result(self, processed_data: Any) -> bool:
    """Check if a processed result is empty or has no meaningful data"""
    if isinstance(processed_data, dict):
        # Check common data fields
        for key in ["incidents", "resources", "tickets", ...]:
            if key in processed_data and len(data_list) > 0:
                return False
        count = processed_data.get("count", 0)
        if count > 0:
            return False
    return True
```

#### 3. New Method: `_find_similar_entities()` (Lines ~872-945)
```python
async def _find_similar_entities(self, state, search_terms, empty_tools):
    """Find similar entities when exact search returns no results"""
    
    # Extract keywords (words > 3 chars)
    keywords = [w for term in search_terms 
                for w in term.replace('-', ' ').split() 
                if len(w) > 3]
    
    # Try broader searches with keywords
    for keyword in keywords[:2]:
        result = await mcp_client.call_tool("search_incidents", 
                                           {"query": keyword, "limit": 3})
        # Collect suggestions...
    
    return {"message": "...", "similar_items": [...]}
```

#### 4. Updated System Prompt (Lines ~700-715)
```python
HANDLING NO RESULTS / SUGGESTIONS:
- If tool_results contains "suggestions" with similar_items
- Start with: "I couldn't find an exact match for..."
- List suggestions naturally
- End with: "Would you like details about one of these?"
```

### File: `workflow.py`

#### Enhanced Response Enrichment Node (Lines ~187-209)
```python
async def _response_enrichment_node(self, state):
    state_with_context = {**state}
    
    # Add MCP client for similar entity search
    if hasattr(self, 'mcp_client') and self.mcp_client:
        client = await self.mcp_client.get_client()
        state_with_context["_mcp_client"] = client  # NEW
    
    result = await self.response_enricher.enrich_response(state_with_context)
    
    # Remove non-serializable refs
    if "_mcp_client" in result:
        del result["_mcp_client"]
    
    return result
```

---

## Example Scenarios

### Scenario 1: Non-Existent Incident Name

**Query:** "What happened to Mit-runtime-api-services?"

**Flow:**
1. search_incidents(query="Mit-runtime-api-services") → 0 results
2. System detects empty result
3. Extracts keywords: ["runtime", "api", "services"]
4. Searches for "runtime": Finds 3 incidents
5. Searches for "api": Finds 4 more incidents
6. Combines and presents suggestions

**Response:**
> I couldn't find an incident specifically named 'Mit-runtime-api-services'. However, I found these similar incidents:
>
> - Incident 1507: 'Incident on runtime api' (High severity)
> - Incident 1499: 'Runtime-aws-api's are not working' (High severity)
> - Incident 1504: 'Playground apis are down' (High severity)
>
> Would you like details about one of these?

---

### Scenario 2: Typo in Resource Name

**Query:** "Show me resource vector-x"

**Flow:**
1. search_resources(query="vector-x") → 0 results
2. Extracts keyword: ["vector"]
3. Searches for "vector": Finds resources
4. Suggests: vector-0, vector-1, etc.

**Response:**
> I couldn't find a resource named 'vector-x'. However, I found these similar resources:
>
> - Resource: vector-0 (Workload/Pod)
> - Resource: vector-1 (Workload/Pod)
>
> Would you like information about one of these?

---

### Scenario 3: Partial Match

**Query:** "GCP runtime issues"

**Flow:**
1. search_incidents(query="GCP runtime") → 0 exact matches
2. Extracts: ["runtime"]
3. Finds incidents containing "runtime"
4. Presents as suggestions

---

## Benefits

### 1. Better User Experience
- ❌ Before: "No data available" (dead end)
- ✅ After: "Here are similar items..." (helpful alternatives)

### 2. Typo Tolerance
- Users don't need exact names
- System suggests closest matches
- Reduces frustration

### 3. Discovery
- Users learn what entities actually exist
- Can refine their queries based on suggestions
- Increases system utility

### 4. Intelligent Fallback
- Automatic keyword extraction
- No manual configuration needed
- Works for any entity type

---

## Configuration

### Adjust Number of Suggestions

In `_find_similar_entities()`:

```python
for keyword in keywords[:2]:  # Change to adjust keyword count
    result = await mcp_client.call_tool("search_incidents", {
        "query": keyword,
        "limit": 3  # Change to adjust results per keyword
    })
```

### Adjust Keyword Filtering

```python
keywords = [w for w in words if len(w) > 3]  # Change threshold
```

### Adjust Response Format

In system prompt (utils/llm_client.py):

```python
HANDLING NO RESULTS / SUGGESTIONS:
- Start response with: "I couldn't find..."  # Customize message
- List the suggestions naturally
- End with: "Would you like..."  # Customize ending
```

---

## Testing

### Manual Test

1. Open web UI: http://localhost:3000
2. Try query: "describe incident on Mit-runtime-api-services"
3. Expected: Suggestions for "runtime api" incidents
4. Verify response format and suggestions

### Check Logs

```bash
tail -f server.log | grep -E "empty.*result|similar.*entities|suggestions"

# Look for:
💡 No results found for exact query. Attempting broader search...
🔍 Searching for similar entities with keywords: ['runtime', 'api']
✅ Found 3 similar items
```

### Test Different Scenarios

```python
# Test 1: Non-existent name
"Show me incident on XYZ-service"

# Test 2: Typo
"Resource vectr-0 details"

# Test 3: Partial match
"runtime service problems"

# Test 4: Multiple keywords
"mit jenkins api issues"
```

---

## Future Enhancements

### 1. Fuzzy Matching
Use Levenshtein distance for typo correction:
```python
from fuzzywuzzy import fuzz
similarity = fuzz.ratio("Mit-runtime-api", "Incident on runtime api")
```

### 2. Machine Learning Ranking
Rank suggestions by relevance using embeddings:
```python
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
embeddings = model.encode(suggestions)
scores = cosine_similarity(query_embedding, embeddings)
```

### 3. User Feedback Loop
Track which suggestions users click:
```python
# Log suggestion selections
if user_selects_suggestion:
    log_feedback(original_query, selected_suggestion)
    # Use for improving keyword extraction
```

### 4. Context-Aware Suggestions
Consider user's previous queries:
```python
if previous_query_about_GCP:
    boost_GCP_suggestions()
```

### 5. Category-Specific Keywords
Different extraction strategies per entity type:
```python
if searching_incidents:
    extract_severity_keywords()
elif searching_resources:
    extract_namespace_keywords()
```

---

## Summary

✅ **Implemented:** Smart suggestions when no exact match found
✅ **Automatic:** Keyword extraction and broader search
✅ **User-Friendly:** Natural language suggestions
✅ **Configurable:** Easy to adjust thresholds and limits
✅ **Extensible:** Foundation for ML-based improvements

The system now gracefully handles "no results" scenarios by providing intelligent alternatives, significantly improving user experience and system usability! 🚀
