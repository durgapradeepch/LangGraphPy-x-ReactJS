# MCP Tool Testing Questions
## Comprehensive Test Suite for All 47 MCP Tools

**Test Date:** December 1, 2025  
**Purpose:** Validate all MCP tools return correct data through the UI

---

## ✅ Category 1: Neo4j Graph Database Tools (9 tools)

### 1.1 get_node_labels
**Question:** "What node types exist in the Neo4j database?"  
**Expected Data:** Domain, Organization, Application, ErrorSignature, AlertSignature, ResourceAlertSignature, MetricSignature, ResourceProfile, CodeChange, User, SourceCodeRepository, Provider, TimeSlotFiveMins, TimeSlotHalfHour, Resource, ResourceAlert, ChangeEvent, Deployment (20 labels total)

### 1.2 get_database_stats
**Question:** "Show me Neo4j database statistics"  
**Expected Data:** 
- Total nodes: 5,379
- Total relationships: 14,308
- Node labels: 20
- Relationship types: 15
- Property keys: 110

### 1.3 get_relationship_types
**Question:** "What relationship types are in the graph database?"  
**Expected Data:** OF_PROVIDER, OCCURRED_IN_5M, OCCURRED_IN_30M, ROLLS_UP_TO, LINKED_TO_CODE_CHANGE, HAS_DEPLOYMENT, OF_DOMAIN, HAS_LOG_SIGNATURE, OWNED_BY, PARENT_OF, PERFORMED_BY_ACTOR, AFFECTS_REPOSITORY, HOSTED_ON, HAS_RESOURCE_ALERT_SIGNATURE, AFFECTED_RESOURCE (15 types)

### 1.4 get_schema
**Question:** "Describe the Neo4j database schema"  
**Expected Data:** Complete schema with all node labels, relationships, and property keys

### 1.5 query_nodes
**Question:** "Find all Application nodes in Neo4j"  
**Expected Data:** List of Application nodes with their properties

### 1.6 search_nodes
**Question:** "Search for nodes with name containing 'api'"  
**Expected Data:** Nodes matching "api" in name property (fuzzy match)

### 1.7 get_relationships
**Question:** "Show me relationships in the graph"  
**Expected Data:** Edge list with source nodes, target nodes, and relationship types

### 1.8 get_node_count
**Question:** "How many nodes are in the database?"  
**Expected Data:** 5,379 nodes total

### 1.9 execute_cypher
**Question:** "Execute this Cypher query: MATCH (n:Application) RETURN count(n)"  
**Expected Data:** Count of Application nodes

---

## ✅ Category 2: Manifest API - Incidents (5 tools)

### 2.1 get_incidents
**Question:** "What relationship types are in the graph database?"  
**Expected Data:** 
- ID: 415, Title: "GCP Services are down", Severity: High, Status: New
- ID: 1174, Title: "Acme cart service are down", Severity: High, Status: New
- ID: 1175, Title: "Acme cart services are down", Severity: High, Status: New

### 2.2 get_incident_by_id
**Question:** "Get details of incident ID 415"  
**Expected Data:** Full incident details for "GCP Services are down"

### 2.3 search_incidents
**Question:** "Search for incidents about cart services"  
**Expected Data:** 
- ID: 1531, Title: "change on azure bucket tag"
- ID: 1496, Title: "acme-cart service are down"
- ID: 1527, Title: "Acme-cart-services are down"

### 2.4 get_incident_changelogs
**Question:** "What changes happened during incident 415?"  
**Expected Data:** Changelog entries associated with incident ID 415

### 2.5 get_incident_curated
**Question:** "Show me curated incident data"  
**Expected Data:** Curated/analyzed incident information

---

## ✅ Category 3: Manifest API - Resources (7 tools)

### 3.1 get_resources
**Question:** "List all infrastructure resources"  
**Expected Data:** Resources with IDs like 50944068, 46080700, 51203317

### 3.2 get_resource_by_id
**Question:** "Get details of resource 50944068"  
**Expected Data:** Complete resource info: name, type, status, configuration, tags

### 3.3 search_resources
**Question:** "Find resources with name containing 'api'"  
**Expected Data:** Resources matching "api" in name/description

### 3.4 get_resource_tickets ⚠️ API ISSUE
**Question:** "What tickets are related to resource 50944068?"  
**Expected Data:** Service tickets/requests for that resource  
**Known Issue:** Manifest API endpoint returns "Bad request Resource id should be integer" error - API may be broken or not fully implemented

### 3.5 get_resource_version
**Question:** "What version is resource 50944068?"  
**Expected Data:** Version tracking info for the resource

### 3.6 get_resource_metadata
**Question:** "Show metadata for resource 50944068"  
**Expected Data:** Tags, labels, custom properties, annotations

### 3.7 get_notifications_by_resource
**Question:** "What notifications exist for resource 50944068?"  
**Expected Data:** Alerts and notifications related to that resource

---

## ✅ Category 4: Manifest API - Changelogs (8 tools)

### 4.1 get_changelogs
**Question:** "Show me recent configuration changes"  
**Expected Data:** Recent changelog entries with derivedType, eventType, severity

### 4.2 get_changelog_by_id
**Question:** "Get details for changelog ID 123"  
**Expected Data:** Single change event with timestamp, resource, change type  
**Note:** First run `get_changelogs` to get a valid changelog ID, then use it here

### 4.3 search_changelogs
**Question:** "Find critical severity changes"  
**Expected Data:** Changelogs filtered by severity=critical

### 4.4 get_changelog_by_resource
**Question:** "What changes happened to resource 50944068?"  
**Expected Data:** Complete change history for that resource with version info

### 4.5 get_changelog_list_by_resource
**Question:** "List changelogs for resource 50944068 without version details"  
**Expected Data:** Simplified changelog list for that resource

### 4.6 search_changelogs_by_event_type
**Question:** "Show me all deployment changes"  
**Expected Data:** Changelogs filtered by event_type=deployment

### 4.7 search_changelogs_by_resource_id
**Question:** "Search changelogs for resource 50944068 with high severity"  
**Expected Data:** Advanced filtered search results

### 4.8 search_changelogs (with IAM/RBAC)
**Question:** "Which IAM or RBAC changes occurred recently?"  
**Expected Data:** Changelogs matching IAM/RBAC keywords

---

## ✅ Category 5: Manifest API - Tickets (3 tools)

### 5.1 get_tickets
**Question:** "List all service tickets"  
**Expected Data:** Jira tickets like "Jira integration data not ingested" and "GH - SaaS-Azure - logout not working"

### 5.2 get_ticket_by_id
**Question:** "Get details of ticket CS-335"  
**Expected Data:** Full ticket details with description, comments, assignee, status for "GH - SaaS-Azure - logout is not working"

### 5.3 search_tickets
**Question:** "Search for tickets about Jira integration"  
**Expected Data:** Tickets matching "jira" keyword

---

## ✅ Category 6: Manifest API - Notifications (3 tools)

### 6.1 get_notifications
**Question:** "Show me all system notifications"  
**Expected Data:** Alert and notification records

### 6.2 get_notification_by_id
**Question:** "Get details of notification ID X"  
**Expected Data:** Single notification details

### 6.3 get_notification_rule
**Question:** "What notification rules are configured?"  
**Expected Data:** Notification rule configurations

---

## ✅ Category 7: Manifest API - Graph Visualization (4 tools)

### 7.1 get_graph
**Question:** "Show me the infrastructure topology graph"  
**Expected Data:** Graph visualization data with nodes and edges

### 7.2 get_graph_by_label
**Question:** "Get graph filtered by label X"  
**Expected Data:** Filtered graph data

### 7.3 get_graph_nodes
**Question:** "List all nodes in the topology graph"  
**Expected Data:** Complete node list from Manifest graph

### 7.4 create_graph_link / execute_graph_cypher
**Question:** "Create a graph link between resources" / "Execute graph query"  
**Expected Data:** Graph operation results

---

## ✅ Category 8: VictoriaLogs Tools (4 tools)

### 8.1 query_logs
**Question:** "Query logs with ERROR level in the last hour"  
**Expected Data:** Log entries matching LogSQL query "level:ERROR"

### 8.2 search_logs
**Question:** "Search logs containing 'database' text"  
**Expected Data:** Log messages with "database" keyword

### 8.3 get_log_metrics
**Question:** "What log fields are available?"  
**Expected Data:** Field names and stream information from VictoriaLogs

### 8.4 get_log_stats
**Question:** "Get statistics for error logs"  
**Expected Data:** Count and summary of log entries

---

## ✅ Category 9: VictoriaMetrics Tools (4 tools)

### 9.1 query_metrics
**Question:** "Show CPU usage rate over the last hour"  
**Expected Data:** Time-series metric data with timestamps and values

### 9.2 instant_query_metrics
**Question:** "What is the current CPU usage?"  
**Expected Data:** Single point-in-time metric value (snapshot)

### 9.3 get_metric_labels
**Question:** "What metric labels exist?"  
**Expected Data:** Label names like 'job', 'instance', 'pod' with their values

### 9.4 get_metric_series
**Question:** "Find all metrics for job=api"  
**Expected Data:** Time series matching the label selector

---

## 🎯 Complex Multi-Tool Questions

### Complex 1: Full Incident Investigation
**Question:** "Investigate the Acme cart service incident - show me the incident details, related resources, changelogs during that time, and any tickets created"  
**Expected Tools Used:** 
- search_incidents (find cart incident)
- get_incident_by_id (get full details)
- get_incident_changelogs (changes during incident)
- search_tickets (related tickets)

### Complex 2: Resource Deep Dive
**Question:** "Tell me everything about resource 50944068 - its details, version, metadata, related tickets, change history, and notifications"  
**Expected Tools Used:**
- get_resource_by_id
- get_resource_version
- get_resource_metadata
- get_resource_tickets
- get_changelog_by_resource
- get_notifications_by_resource

### Complex 3: System Health Overview
**Question:** "Give me a complete system health report - database stats, recent incidents, error logs, and current metrics"  
**Expected Tools Used:**
- get_database_stats
- get_incidents (status=open)
- search_logs (level=ERROR)
- instant_query_metrics (current status)

### Complex 4: Change Audit
**Question:** "Audit all changes in the last 24 hours - show me changelogs, deployments, and who made them"  
**Expected Tools Used:**
- get_changelogs
- search_changelogs_by_event_type (deployment)
- query_nodes (User nodes for actors)

### Complex 5: Application Dependency Analysis
**Question:** "Show me the Application nodes in Neo4j and their relationships to other resources"  
**Expected Tools Used:**
- query_nodes (label=Application)
- get_relationships (from_label=Application)
- get_graph_nodes

---

## 📊 Test Execution Checklist

For each question above:
1. ✅ Enter question in UI
2. ✅ Verify enhanced mode triggers (check backend logs)
3. ✅ Confirm correct tool(s) called
4. ✅ Validate response matches expected data
5. ✅ Check for proper error handling
6. ✅ Verify enriched response format

**Success Criteria:**
- Tool selection accuracy: >95%
- Data accuracy: 100%
- Response time: <5 seconds
- Error handling: Graceful with helpful messages
- Enrichment quality: Forward links + recommendations present

---

## 🐛 Known Edge Cases to Test

1. **Empty Results:** "Find incidents with keyword 'zzznonexistent'"
2. **Invalid IDs:** "Get resource with ID 999999999"
3. **Complex Queries:** Multi-condition LogSQL or Cypher queries
4. **Large Results:** Questions returning >1000 records
5. **Ambiguous Intent:** "Tell me about api" (could be Neo4j node, resource, incident)

---

## 📝 Manual Verification Commands

```bash
# Test Neo4j directly
curl -s -X POST http://localhost:3001/api/mcp/execute -H "Content-Type: application/json" \
  -d '{"tool_name": "get_database_stats", "arguments": {}}' | jq '.result'

# Test Manifest Incidents
curl -s -X POST http://localhost:3001/api/mcp/execute -H "Content-Type: application/json" \
  -d '{"tool_name": "get_incidents", "arguments": {}}' | jq '.result.incidents[0:3]'

# Test Search
curl -s -X POST http://localhost:3001/api/mcp/execute -H "Content-Type: application/json" \
  -d '{"tool_name": "search_incidents", "arguments": {"query": "cart"}}' | jq '.result.incidents[0:3]'

# Test Tickets
curl -s -X POST http://localhost:3001/api/mcp/execute -H "Content-Type: application/json" \
  -d '{"tool_name": "get_tickets", "arguments": {}}' | jq '.result.tickets[0:2]'
```

---

**Ready to test!** Start with simple single-tool questions, then progress to complex multi-tool scenarios. 🚀
