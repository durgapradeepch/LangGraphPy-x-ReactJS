const express = require('express');
const axios = require('axios');
const neo4j = require('neo4j-driver');
const config = require('./config');

const app = express();
const PORT = config.SERVER_PORT;

// Neo4j configuration
const NEO4J_CONFIG = config.NEO4J_CONFIG;
const NEO4J_URI = NEO4J_CONFIG.uri;
const NEO4J_USER = NEO4J_CONFIG.username;
const NEO4J_PASS = NEO4J_CONFIG.password;
const NEO4J_DATABASE = NEO4J_CONFIG.database;

// Initialize Neo4j driver
let neo4jDriver = null;
try {
    neo4jDriver = neo4j.driver(
        NEO4J_URI,
        neo4j.auth.basic(NEO4J_USER, NEO4J_PASS),
        {
            maxConnectionLifetime: 3 * 60 * 60 * 1000, // 3 hours
            maxConnectionPoolSize: 50,
            connectionAcquisitionTimeout: 2 * 60 * 1000 // 2 minutes
        }
    );
    console.log('🔧 Neo4j driver initialized');
    console.log('   URI:', NEO4J_URI);
    console.log('   Database:', NEO4J_DATABASE);
} catch (error) {
    console.error('❌ Failed to initialize Neo4j driver:', error.message);
}

// Initialize LLM configuration
let llmAvailable = false;
let llmChoice = config.LLM_CHOICE || 'llama';

if (llmChoice === 'openai' && config.OPENAI_API_KEY) {
    llmAvailable = true;
    console.log('✅ OpenAI API configured');
    console.log('   Model:', config.MODEL_NAME || 'gpt-4o-mini');
} else if (llmChoice === 'llama' && config.LLAMA_API_ENDPOINT && config.LLAMA_API_KEY) {
    llmAvailable = true;
    console.log('✅ Llama API configured');
    console.log('   Endpoint:', config.LLAMA_API_ENDPOINT);
} else {
    console.warn('⚠️ No LLM configured - AI features will use fallback mode');
}

// Unified LLM API caller - supports both OpenAI and Llama
async function callLLM(messages, temperature = 0.05, max_tokens = 500) {
    if (llmChoice === 'openai') {
        return await callOpenAI(messages, temperature, max_tokens);
    } else {
        return await callLlamaAPI(messages, temperature, max_tokens);
    }
}

// OpenAI API caller
async function callOpenAI(messages, temperature = 0.05, max_tokens = 500) {
    try {
        const payload = {
            model: config.MODEL_NAME || "gpt-4o-mini",
            messages: messages,
            temperature: temperature,
            max_tokens: max_tokens
        };

        console.log('🔍 OpenAI API Request:', JSON.stringify(payload, null, 2));

        const response = await axios.post('https://api.openai.com/v1/chat/completions', payload, {
            headers: {
                'Authorization': `Bearer ${config.OPENAI_API_KEY}`,
                'Content-Type': 'application/json'
            },
            timeout: 120000
        });

        console.log('📥 OpenAI API Response:', JSON.stringify(response.data, null, 2));

        if (response.data.choices && response.data.choices[0] && response.data.choices[0].message) {
            return response.data.choices[0].message.content;
        } else {
            throw new Error('Unexpected response format from OpenAI API');
        }
    } catch (error) {
        console.error('❌ OpenAI API error:', error.response?.data || error.message);
        throw error;
    }
}

// Helper function to call Llama API (matching Python format)
async function callLlamaAPI(messages, temperature = 0.05, max_tokens = 500) {
    try {
        const payload = {
            model: config.MODEL_NAME || "llama3",
            messages: messages,
            options: {
                temperature: temperature,
                max_tokens: max_tokens
            },
            stream: config.STREAM === 'true' ? true : false
        };

        console.log('🔍 Llama API Request:', JSON.stringify(payload, null, 2));

        const response = await axios.post(config.LLAMA_API_ENDPOINT, payload, {
            headers: {
                'Authorization': `Bearer ${config.LLAMA_API_KEY}`,
                'Content-Type': 'application/json'
            },
            timeout: 120000  // Increased to 120 seconds for LLM response
        });

        console.log('📥 Llama API Response:', JSON.stringify(response.data, null, 2));

        // Handle response format matching Python code
        if (response.data.message && response.data.message.content) {
            return response.data.message.content;
        } else if (response.data.response) {
            return response.data.response;
        } else if (response.data.content) {
            return response.data.content;
        } else {
            throw new Error('Unexpected response format from Chat API');
        }
    } catch (error) {
        console.error('❌ Llama API error:', error.response?.data || error.message);
        throw error;
    }
}

/**
 * STREAMING VERSION: Call Llama API with streaming enabled
 * Yields tokens/chunks as they arrive for progressive UI updates
 * Used by streaming endpoints only - existing endpoints unchanged
 * 
 * @param {Array} messages - Chat messages array
 * @param {Number} temperature - Sampling temperature
 * @param {Number} max_tokens - Maximum tokens to generate
 * @yields {String} Token/chunk from LLM
 */
async function* callLlamaAPIStreaming(messages, temperature = 0.05, max_tokens = 500) {
    try {
        const payload = {
            model: config.MODEL_NAME || "llama3",
            messages: messages,
            options: {
                temperature: temperature,
                max_tokens: max_tokens
            },
            stream: true  // Enable streaming
        };

        console.log('🔍 Llama API Streaming Request:', JSON.stringify(payload, null, 2));

        const response = await axios.post(config.LLAMA_API_ENDPOINT, payload, {
            headers: {
                'Authorization': `Bearer ${config.LLAMA_API_KEY}`,
                'Content-Type': 'application/json'
            },
            responseType: 'stream',  // Critical for receiving stream chunks
            timeout: 120000
        });

        let fullContent = '';

        // Process stream chunks as they arrive
        for await (const chunk of response.data) {
            const chunkStr = chunk.toString();
            const lines = chunkStr.split('\n').filter(line => line.trim());

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6).trim();
                        if (jsonStr === '[DONE]') {
                            console.log('✅ Streaming completed');
                            break;
                        }

                        const jsonData = JSON.parse(jsonStr);

                        // Handle different response formats
                        let content = null;
                        if (jsonData.message?.content) {
                            content = jsonData.message.content;
                        } else if (jsonData.response) {
                            content = jsonData.response;
                        } else if (jsonData.content) {
                            content = jsonData.content;
                        } else if (jsonData.choices?.[0]?.delta?.content) {
                            content = jsonData.choices[0].delta.content;
                        } else if (jsonData.choices?.[0]?.text) {
                            content = jsonData.choices[0].text;
                        }

                        if (content) {
                            fullContent += content;
                            yield content;  // Yield individual token/chunk
                        }
                    } catch (parseError) {
                        console.warn('⚠️ Failed to parse stream chunk:', parseError.message);
                    }
                }
            }
        }

        console.log('📥 Streaming completed. Total content length:', fullContent.length);

    } catch (error) {
        console.error('❌ Llama API streaming error:', error.response?.data || error.message);
        throw error;
    }
}

// MCP Tool Definitions
const MCP_TOOLS = {
    // VictoriaLogs Tools
    query_logs: {
        name: "query_logs",
        description: "Execute LogSQL queries on VictoriaLogs for STRUCTURED log searching. Requires LogSQL syntax knowledge. Query examples: 'level:ERROR', '_msg:database', 'level:ERROR AND pod:api-server'. Supports: field:value matching, AND/OR logic, time range (start_time, end_time in ISO 8601), result limit (default 1000, max 10000). Use for: complex log queries with multiple conditions, precise field matching, structured log analysis. For SIMPLE text search or single label filter, use search_logs instead (easier, no syntax knowledge needed). Best for advanced users who know LogSQL or when you need complex boolean queries.",
        inputSchema: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "LogSQL query string (e.g., 'level:ERROR AND _msg:database')",
                    required: true
                },
                start_time: {
                    type: "string",
                    description: "Start time for log query in ISO 8601 format (e.g., '2022-01-01T00:00:00Z'). If not provided, queries recent logs."
                },
                end_time: {
                    type: "string",
                    description: "End time for log query in ISO 8601 format (e.g., '2025-11-20T23:59:59Z'). If not provided, uses current time."
                },
                limit: {
                    type: "number",
                    description: "Maximum number of log entries to return (default: 1000, max: 10000)",
                    default: 1000
                }
            },
            required: ["query"]
        }
    },

    search_logs: {
        name: "search_logs",
        description: "Simple log search - NO LogSQL syntax needed. Search by: free text in messages (search_text parameter), or label filters as key-value pairs (e.g., {level: 'ERROR', object: 'TaskManager'}). EASIER than query_logs. Use for: simple text searches ('find logs containing X'), single or multiple label filters, when you DON'T need complex LogSQL queries. Best for: 'show me error logs', 'logs from pod X', 'logs containing database'. For complex queries with AND/OR logic, use query_logs instead.",
        inputSchema: {
            type: "object",
            properties: {
                search_text: {
                    type: "string",
                    description: "Free text to search for in log messages"
                },
                labels: {
                    type: "object",
                    description: "Label filters as key-value pairs (e.g., {level: 'ERROR', object: 'TaskManager'})"
                },
                limit: {
                    type: "number",
                    description: "Maximum number of log entries to return (default: 20, max: 10000). Lower limits provide better sampling for LLM context. Usually not needed - leave unset for best results.",
                    default: 20
                }
            }
        }
    },

    get_log_metrics: {
        name: "get_log_metrics",
        description: "Get available log field names and stream information from VictoriaLogs metadata. Use this to discover what fields and streams are available for querying.",
        inputSchema: {
            type: "object",
            properties: {
                metric_type: {
                    type: "string",
                    description: "Type of metadata: 'fields' for field names or 'streams' for stream info",
                    default: "fields"
                }
            }
        }
    },

    get_log_stats: {
        name: "get_log_stats",
        description: "Get statistical summary and counts for log entries matching a LogSQL query. Use this for log analytics and aggregations.",
        inputSchema: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "LogSQL query to get statistics for (default: '*' for all logs)",
                    default: "*"
                }
            }
        }
    },

    // VictoriaMetrics Tools
    query_metrics: {
        name: "query_metrics",
        description: "Execute PromQL RANGE queries on VictoriaMetrics for time-series metrics over TIME PERIODS. Returns metric data points over time. Query examples: 'rate(cpu_usage[5m])', 'memory_usage_bytes', 'http_requests_total{job=\"api\"}'. Requires: query (PromQL), start_time (required), end_time (optional, defaults to now), step (resolution like '1m'). Use for: analyzing metric trends, calculating rates/derivatives, aggregating over time, graphing metrics. Best for: 'CPU usage over last hour', 'request rate trends', time-series analysis. For INSTANT/current values, use instant_query_metrics. Requires PromQL knowledge.",
        inputSchema: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "PromQL query string (e.g., 'rate(cpu_usage_seconds_total[5m])', 'memory_usage_bytes')",
                    required: true
                },
                start_time: {
                    type: "string",
                    description: "Start time for query (ISO 8601, Unix timestamp, or relative like '1h', '30m')",
                    required: true
                },
                end_time: {
                    type: "string",
                    description: "End time for query (ISO 8601, Unix timestamp, or relative). Defaults to now if not provided."
                },
                step: {
                    type: "string",
                    description: "Query resolution step (e.g., '1m', '5m', '1h'). Defaults to '1m'.",
                    default: "1m"
                }
            },
            required: ["query", "start_time"]
        }
    },

    instant_query_metrics: {
        name: "instant_query_metrics",
        description: "Execute PromQL INSTANT query on VictoriaMetrics for metric values at a SINGLE POINT in time (snapshot). Returns current/latest values, NOT time series. Query examples: up with job api, node_memory_free_bytes, container_cpu_usage. Optional time parameter (defaults to now). Use for: getting current metric values, latest status, point-in-time snapshots. Best for: what is current CPU, is service up, current memory usage. For metrics OVER TIME (trends, graphs), use query_metrics instead. Faster than range queries when you only need current values.",
        inputSchema: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "PromQL query string (e.g., up or node_memory_free_bytes)",
                    required: true
                },
                time: {
                    type: "string",
                    description: "Time for instant query (ISO 8601, Unix timestamp, or relative). Defaults to now if not provided."
                }
            },
            required: ["query"]
        }
    },

    get_metric_labels: {
        name: "get_metric_labels",
        description: "Discover available metric labels and their values in VictoriaMetrics. Use this to explore what labels exist (e.g., 'job', 'instance', 'pod') and their possible values for query construction.",
        inputSchema: {
            type: "object",
            properties: {
                label_name: {
                    type: "string",
                    description: "Specific label name to get values for (e.g., 'job', 'instance'). If not provided, returns all label names."
                }
            }
        }
    },

    get_metric_series: {
        name: "get_metric_series",
        description: "Find time series that match a label pattern in VictoriaMetrics. Use this to discover what metrics are available and their label combinations (e.g., all series for a specific job or pod).",
        inputSchema: {
            type: "object",
            properties: {
                match: {
                    type: "string",
                    description: "Series selector pattern (e.g., up or cpu_usage_seconds_total)",
                    required: true
                },
                start_time: {
                    type: "string",
                    description: "Start time to search for series (ISO 8601, Unix timestamp, or relative like 1h)"
                },
                end_time: {
                    type: "string",
                    description: "End time to search for series (ISO 8601, Unix timestamp, or relative)"
                }
            },
            required: ["match"]
        }
    },

    // Manifest API Tools
    get_changelogs: {
        name: "get_changelogs",
        description: "List ALL recent changelogs (configuration changes, deployments) without filtering. NO filters applied - returns all change events across all resources. Use for: browsing recent changes, getting change overview, timeline of all modifications. Supports offset for pagination. For SPECIFIC resource's changes, use get_changelog_by_resource. For SPECIFIC incident's changes, use get_incident_changelogs. For filtered/searched changelogs, use search_changelogs. For ONE specific changelog_id, use get_changelog_by_id.",
        inputSchema: {
            type: "object",
            properties: {
                offset: {
                    type: "integer",
                    description: "Number of changelogs to skip for pagination",
                    default: 0
                }
            }
        }
    },

    get_graph: {
        name: "get_graph",
        description: "Retrieve graph visualization data from Manifest API. Optionally filter by graph_type. Use this for topology and dependency mapping.",
        inputSchema: {
            type: "object",
            properties: {
                graph_type: {
                    type: "string",
                    description: "Type of graph to retrieve (optional filter)"
                }
            }
        }
    },

    get_incidents: {
        name: "get_incidents",
        description: "List ALL incidents from Manifest API. NO incident_id required - returns multiple incidents. Optionally filter by status (open/closed/resolved). Use this for: browsing all incidents, getting incident lists, finding top N incidents, or when you DON'T have a specific incident_id. For a SPECIFIC incident ID, use get_incident_by_id instead. Supports status filtering for open/closed incidents.",
        inputSchema: {
            type: "object",
            properties: {
                status: {
                    type: "string",
                    description: "Filter by incident status: 'open', 'closed', 'resolved', etc."
                }
            }
        }
    },

    get_notifications: {
        name: "get_notifications",
        description: "List ALL notification records - alerts, warnings, system notifications. NO notification_id required - returns multiple notifications. Use for: browsing all notifications, getting notification feed, alert overview. Returns notification events across all resources and services. For SPECIFIC notification by ID, use get_notification_by_id. For notifications RELATED TO a specific resource, use get_notifications_by_resource. Best for general notification monitoring and alert history.",
        inputSchema: {
            type: "object",
            properties: {}
        }
    },

    get_resources: {
        name: "get_resources",
        description: "List ALL resources in the infrastructure inventory. NO resource_id required - returns multiple resources. Optionally filter by resource_type (VM, Container, Database, Storage, Network). Use for: browsing all resources, getting resource lists, discovering infrastructure assets. Returns resource IDs, names, types, status, and metadata. For SPECIFIC resource by ID, use get_resource_by_id. For searching resources by name/keyword, use search_resources. Best for infrastructure discovery and asset inventory queries.",
        inputSchema: {
            type: "object",
            properties: {
                resource_type: {
                    type: "string",
                    description: "Filter by resource type/category"
                }
            }
        }
    },

    get_tickets: {
        name: "get_tickets",
        description: "List ALL service tickets/requests. NO ticket_id required - returns multiple tickets. Optionally filter by status (open/closed/pending/resolved). Use for: browsing all tickets, getting ticket lists, overview of service requests. Returns basic ticket info (ID, title, status, priority). For SPECIFIC ticket by ID, use get_ticket_by_id. For SEARCHING tickets with multiple filters or keywords, use search_tickets. Simple status-based filtering use case.",
        inputSchema: {
            type: "object",
            properties: {
                status: {
                    type: "string",
                    description: "Filter by ticket status: 'open', 'closed', 'pending', etc."
                }
            }
        }
    },

    // Additional Resource Tools
    get_resource_by_id: {
        name: "get_resource_by_id",
        description: "Get ONE specific resource by exact resource_id. REQUIRES resource_id parameter. Returns complete resource details: name, type, status, configuration, tags, metadata, health status, and relationships. Use when: user provides specific resource ID, or you have resource_id from previous results (e.g., from incident). NOT for searching by name (use search_resources) or listing all resources (use get_resources). Related tools: get_resource_tickets for tickets, get_resource_metadata for extended attributes, get_changelog_by_resource for change history.",
        inputSchema: {
            type: "object",
            properties: {
                resource_id: {
                    type: "integer",
                    description: "Unique resource identifier (numeric)",
                    required: true
                }
            },
            required: ["resource_id"]
        }
    },

    get_resource_tickets: {
        name: "get_resource_tickets",
        description: "Get ALL tickets/service requests associated with a SPECIFIC resource_id. REQUIRES resource_id parameter. Returns tickets where this resource is mentioned, affected, or involved. Use for: finding tickets about a resource, 'show tickets for resource X', investigating resource-related issues. Perfect when you have a resource and want to see its service tickets. Reverse operation of getting resource from ticket. Related: use get_resource_by_id for resource details, search_tickets for ticket searches.",
        inputSchema: {
            type: "object",
            properties: {
                resource_id: {
                    type: "integer",
                    description: "Resource ID to get tickets for (numeric)",
                    required: true
                }
            },
            required: ["resource_id"]
        }
    },

    search_resources: {
        name: "search_resources",
        description: "Search resources by keywords/text with PARTIAL MATCHING. Use when: looking for resources by name pattern (e.g., 'bucket', 'api'), searching descriptions, or finding resources matching text criteria. Supports pagination (page, page_size). Returns resources matching query across name, description, tags, and other text fields. Best for: 'find resources named X', 'resources containing Y'. For browsing all resources, use get_resources. For exact resource_id lookup, use get_resource_by_id.",
        inputSchema: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Search query text/keyword"
                },
                page: {
                    type: "integer",
                    description: "Page number for pagination (starts at 1)",
                    default: 1
                },
                page_size: {
                    type: "integer",
                    description: "Number of items per page",
                    default: 20
                }
            }
        }
    },

    get_resource_version: {
        name: "get_resource_version",
        description: "Get VERSION information for a specific resource_id. REQUIRES resource_id parameter. Returns version tracking data: current version, version history, version metadata. Use for: tracking resource versions over time, version comparison, 'what version is resource X'. Different from get_changelog_by_resource (which shows changes) - this shows version numbers/tags. Use get_resource_by_id for general resource info, get_changelog_by_resource for change history.",
        inputSchema: {
            type: "object",
            properties: {
                resource_id: {
                    type: "integer",
                    description: "Resource ID to get version for (numeric)",
                    required: true
                }
            },
            required: ["resource_id"]
        }
    },

    get_resource_metadata: {
        name: "get_resource_metadata",
        description: "Get EXTENDED metadata and custom attributes for a specific resource_id. REQUIRES resource_id parameter. Returns: tags, labels, custom properties, annotations, extended configuration details not in basic resource info. Use when: you need detailed resource attributes beyond basic info, looking for tags/labels, custom metadata fields. Complement to get_resource_by_id (which gives core info). Best for: 'show tags for resource X', 'get metadata of resource Y', custom attribute lookups.",
        inputSchema: {
            type: "object",
            properties: {
                resource_id: {
                    type: "integer",
                    description: "Resource ID to get metadata for (numeric)",
                    required: true
                }
            },
            required: ["resource_id"]
        }
    },

    // Additional Changelog Tools
    get_changelog_by_id: {
        name: "get_changelog_by_id",
        description: "Get ONE specific changelog by its unique changelog_id (NOT resource_id or incident_id). REQUIRES changelog_id parameter. Returns single change event details: timestamp, resource affected, change type, who made change, before/after values. Use ONLY when you have exact changelog_id from previous results. For changes on a SPECIFIC RESOURCE, use get_changelog_by_resource (takes resource_id). For changes related to SPECIFIC INCIDENT, use get_incident_changelogs (takes incident_id). For searching changelogs, use search_changelogs.",
        inputSchema: {
            type: "object",
            properties: {
                changelog_id: {
                    type: "string",
                    description: "Changelog ID (not resource ID)",
                    required: true
                }
            },
            required: ["changelog_id"]
        }
    },

    search_changelogs: {
        name: "search_changelogs",
        description: "Search changelogs with ADVANCED FILTERS across ALL resources: severity (critical/high/medium/low), provider_key (AWS/Azure/GCP), description (text search). Supports pagination. Use for: finding changelogs by attributes, filtering changes by severity/provider, searching change descriptions. Best for: 'show critical changes', 'Azure changes', 'changes matching X'. For ALL changelogs unfiltered, use get_changelogs. For changes on SPECIFIC resource, use get_changelog_by_resource. For changes related to SPECIFIC incident, use get_incident_changelogs.",
        inputSchema: {
            type: "object",
            properties: {
                severity: {
                    type: "string",
                    description: "Filter by severity"
                },
                provider_key: {
                    type: "string",
                    description: "Filter by provider key"
                },
                description: {
                    type: "string",
                    description: "Filter by description"
                },
                page: {
                    type: "integer",
                    description: "Page number",
                    default: 1
                },
                page_size: {
                    type: "integer",
                    description: "Page size",
                    default: 20
                }
            }
        }
    },

    get_changelog_by_resource: {
        name: "get_changelog_by_resource",
        description: "Get ALL changelogs for a SPECIFIC resource_id with VERSION information included. REQUIRES resource_id parameter. Returns complete change history for one resource: configuration changes, deployments, updates, with version tracking. Use for: resource change history, 'what changed on resource X', tracking resource modifications over time. Includes version data (richer than get_changelog_list_by_resource). For SIMPLE list without versions, use get_changelog_list_by_resource. For changes related to INCIDENT, use get_incident_changelogs.",
        inputSchema: {
            type: "object",
            properties: {
                resource_id: {
                    type: "integer",
                    description: "Resource ID to get changelogs for (numeric)",
                    required: true
                }
            },
            required: ["resource_id"]
        }
    },

    get_changelog_list_by_resource: {
        name: "get_changelog_list_by_resource",
        description: "Get a simplified list of changelogs for a specific resource ID WITHOUT version information. Use this for basic changelog lists by resource. Endpoint: /resource/{id}/list",
        inputSchema: {
            type: "object",
            properties: {
                resource_id: {
                    type: "integer",
                    description: "Resource ID to get changelog list for (numeric)",
                    required: true
                }
            },
            required: ["resource_id"]
        }
    },

    search_changelogs_by_event_type: {
        name: "search_changelogs_by_event_type",
        description: "Search and filter change log entries by event type classification (e.g., 'deployment', 'configuration_change'). Use when filtering by event category.",
        inputSchema: {
            type: "object",
            properties: {
                event_type: {
                    type: "string",
                    description: "Event type to filter by (e.g., 'deployment', 'update')"
                },
                severity: {
                    type: "string",
                    description: "Filter by severity"
                },
                page: {
                    type: "integer",
                    description: "Page number",
                    default: 1
                },
                page_size: {
                    type: "integer",
                    description: "Page size",
                    default: 20
                }
            }
        }
    },

    search_changelogs_by_resource_id: {
        name: "search_changelogs_by_resource_id",
        description: "Advanced search for changelogs by resource ID with additional filtering by severity and pagination. Use when you need filtered search results for a resource.",
        inputSchema: {
            type: "object",
            properties: {
                resource_id: {
                    type: "integer",
                    description: "Resource ID to search changelogs for (numeric)",
                    required: true
                },
                severity: {
                    type: "string",
                    description: "Optional severity filter"
                },
                page: {
                    type: "integer",
                    description: "Page number",
                    default: 1
                },
                page_size: {
                    type: "integer",
                    description: "Page size",
                    default: 20
                }
            },
            required: ["resource_id"]
        }
    },

    // Additional Notification Tools
    get_notification_by_id: {
        name: "get_notification_by_id",
        description: "Get ONE specific notification by exact notification_id. REQUIRES notification_id parameter. Returns notification details: message, severity, timestamp, source, target resources, notification rule applied. Use when: user provides specific notification ID, or you have notification_id from previous results. NOT for listing all notifications (use get_notifications) or resource-specific notifications (use get_notifications_by_resource). For notification rules, use get_notification_rule.",
        inputSchema: {
            type: "object",
            properties: {
                notification_id: {
                    type: "string",
                    description: "Unique notification identifier",
                    required: true
                }
            },
            required: ["notification_id"]
        }
    },

    get_notification_rule: {
        name: "get_notification_rule",
        description: "Get configuration of a specific notification/alert RULE by rule_id. REQUIRES rule_id parameter. Returns rule settings: conditions, thresholds, severity levels, notification channels, enabled status. Use for: understanding notification rules, 'how is this notification configured', reviewing alert conditions. NOT for notification events (use get_notification_by_id). This shows the RULE configuration, not notification instances. Best for rule management and alert policy review.",
        inputSchema: {
            type: "object",
            properties: {
                rule_id: {
                    type: "string",
                    description: "Notification rule identifier",
                    required: true
                }
            },
            required: ["rule_id"]
        }
    },

    get_notifications_by_resource: {
        name: "get_notifications_by_resource",
        description: "Get ALL notifications related to a SPECIFIC resource_id. REQUIRES resource_id parameter. Returns all alerts, warnings, and notifications where this resource is mentioned or affected. Use for: finding notifications about a resource, 'show alerts for resource X', investigating resource-related notifications. Reverse of get_notification_by_id. Perfect when you have a resource and want to see its notification history. Related: use get_resource_by_id for resource details.",
        inputSchema: {
            type: "object",
            properties: {
                resource_id: {
                    type: "integer",
                    description: "Resource ID to get notifications for (numeric)",
                    required: true
                }
            },
            required: ["resource_id"]
        }
    },

    // Additional Ticket Tools
    get_ticket_by_id: {
        name: "get_ticket_by_id",
        description: "Get ONE specific ticket by ticket_id (internal numeric ID like 4114208) OR sourceRef (external ID like 'CS-335', 'NEO-270'). Automatically handles both formats. REQUIRES ticket_id parameter. Returns complete ticket details: title, description, type, priority, status, assignee, created/updated timestamps, related resources. Use when: user provides specific ticket ID/reference, or you have ticket_id from previous results. NOT for searching (use search_tickets) or listing all (use get_tickets). Perfect for 'show ticket CS-335' or 'get details of ticket 12345'.",
        inputSchema: {
            type: "object",
            properties: {
                ticket_id: {
                    type: "string",
                    description: "Ticket identifier - can be internal numeric ID (4114208) or external sourceRef (CS-335, NEO-270, etc.)",
                    required: true
                }
            },
            required: ["ticket_id"]
        }
    },

    search_tickets: {
        name: "search_tickets",
        description: "Search and filter tickets with MULTIPLE criteria: title (partial match), type (incident/request/problem), priority (high/medium/low), status (open/in_progress/closed), severity. Use for: finding tickets by keywords, filtering tickets by attributes, advanced ticket queries with multiple conditions. Supports pagination. Best for 'show me high priority open tickets' or 'find tickets about X'. For listing all tickets, use get_tickets. For ONE specific ticket_id, use get_ticket_by_id.",
        inputSchema: {
            type: "object",
            properties: {
                title: {
                    type: "string",
                    description: "Filter by ticket title (partial match)"
                },
                type: {
                    type: "string",
                    description: "Filter by ticket type (e.g., 'incident', 'request')"
                },
                priority: {
                    type: "string",
                    description: "Filter by priority level (e.g., 'high', 'medium', 'low')"
                },
                status: {
                    type: "string",
                    description: "Filter by status (e.g., 'open', 'in_progress', 'closed')"
                },
                severity: {
                    type: "string",
                    description: "Filter by severity level"
                },
                page: {
                    type: "integer",
                    description: "Page number for pagination",
                    default: 1
                },
                page_size: {
                    type: "integer",
                    description: "Results per page",
                    default: 20
                }
            }
        }
    },

    // Additional Incident Tools
    get_incident_by_id: {
        name: "get_incident_by_id",
        description: "Get ONE specific incident by exact incident_id (e.g., 1529, 1531). REQUIRES incident_id parameter. Returns detailed incident information including title, severity, status, timestamps, affected resources, and root cause analysis. Use when: user provides specific incident ID ('get incident 1529'), or you have incident_id from previous tool results. NOT for searching by keywords (use search_incidents) or listing all incidents (use get_incidents). Related: use get_incident_changelogs to get changes for this incident, get_incident_curated for AI analysis.",
        inputSchema: {
            type: "object",
            properties: {
                incident_id: {
                    type: "string",
                    description: "Unique incident identifier",
                    required: true
                }
            },
            required: ["incident_id"]
        }
    },

    get_incident_changelogs: {
        name: "get_incident_changelogs",
        description: "Get ALL changelogs (resource changes) associated with a SPECIFIC incident. REQUIRES incident_id parameter. Returns configuration changes, deployments, and resource modifications that occurred around the incident time and may be related to the incident's root cause. Perfect for: incident investigation ('what changed?'), root cause analysis, correlating changes with incidents. Use after get_incident_by_id when analyzing 'incident X and its changes'. Returns empty if no changelogs linked to incident.",
        inputSchema: {
            type: "object",
            properties: {
                incident_id: {
                    type: "string",
                    description: "Incident ID to get changelogs for",
                    required: true
                }
            },
            required: ["incident_id"]
        }
    },

    get_incident_curated: {
        name: "get_incident_curated",
        description: "Get AI-CURATED incident analysis with enhanced insights, context, and recommended actions for a SPECIFIC incident. REQUIRES incident_id. Returns: incident summary, root cause analysis, affected services, correlated events, similar past incidents, recommended remediation steps. This is ENRICHED data with AI insights, unlike get_incident_by_id which returns raw incident data. Use for: deep incident investigation, root cause analysis requests, when user asks for 'detailed analysis' or 'what caused this incident'. Best combined with get_incident_by_id and get_incident_changelogs for complete incident context.",
        inputSchema: {
            type: "object",
            properties: {
                incident_id: {
                    type: "string",
                    description: "Incident ID to get curated data for",
                    required: true
                }
            },
            required: ["incident_id"]
        }
    },

    search_incidents: {
        name: "search_incidents",
        description: "Search incidents by keywords with PARTIAL TEXT MATCHING in incident titles. Best for: finding incidents by service names, error keywords, or descriptions. CRITICAL: Extract KEY TERMS from full service names - use 'cart' instead of 'acme-cart-services', 'runtime api' instead of 'mit-runtime-api-services'. Supports multiple filters: query (title search), title, priority (critical/high/medium/low), status (open/investigating/resolved), severity. Returns paginated results. When user asks 'find incidents about X' or 'incidents containing Y', use this tool. For exact incident ID (e.g., incident 1531), use get_incident_by_id. For listing all incidents without search, use get_incidents.",
        inputSchema: {
            type: "object",
            properties: {
                query: {
                    type: "string",
                    description: "Search query to match against incident titles (partial match). Extract KEY TERMS from service names - e.g., use 'runtime api' not 'Mit-runtime-api-services'"
                },
                title: {
                    type: "string",
                    description: "Filter by incident title (partial match)"
                },
                priority: {
                    type: "string",
                    description: "Filter by priority level (e.g., 'critical', 'high', 'medium', 'low')"
                },
                status: {
                    type: "string",
                    description: "Filter by status (e.g., 'open', 'investigating', 'resolved', 'closed')"
                },
                severity: {
                    type: "string",
                    description: "Filter by severity level (e.g., 'sev1', 'sev2')"
                },
                page: {
                    type: "integer",
                    description: "Page number for pagination",
                    default: 1
                },
                page_size: {
                    type: "integer",
                    description: "Results per page",
                    default: 20
                }
            }
        }
    },

    // Graph Tools
    get_graph_nodes: {
        name: "get_graph_nodes",
        description: "Get COMPLETE graph topology - ALL nodes and ALL relationships in Manifest database. NO filters - returns entire graph structure. Use for: understanding overall system architecture, exploring full dependency map, discovering all resource interconnections, topology visualization. WARNING: Returns large dataset - all nodes, edges, and relationships. Best for: 'show me the architecture', 'what is the topology', 'how are things connected'. For FILTERED graph by node type, use get_graph_by_label (much faster for specific node types). For CUSTOM graph queries, use execute_graph_cypher.",
        inputSchema: {
            type: "object",
            properties: {}
        }
    },

    get_graph_by_label: {
        name: "get_graph_by_label",
        description: "Get FILTERED graph topology by specific node label (e.g., 'Resource', 'Service', 'Incident', 'Component'). REQUIRES label parameter. Returns ONLY nodes matching the label and their relationships. MUCH FASTER than get_graph_nodes when you need specific node types. Use for: focused topology views, 'show me all Resources', 'Service dependencies', exploring specific entity types. Reduces data size significantly vs full graph. Best for: 'graph of X nodes', 'how are Services connected', targeted topology analysis. For COMPLETE graph, use get_graph_nodes. For CUSTOM queries, use execute_graph_cypher.",
        inputSchema: {
            type: "object",
            properties: {
                label: {
                    type: "string",
                    description: "Node label to filter by",
                    required: true
                }
            },
            required: ["label"]
        }
    },

    create_graph_link: {
        name: "create_graph_link",
        description: "Create a new relationship link between two existing nodes in the Manifest graph. Use this to establish connections between resources, services, or components. Requires valid source node ID, target node ID, and relationship type. Use for building or updating graph topology, establishing dependencies, or creating service connections. Endpoint: POST /graph/link",
        inputSchema: {
            type: "object",
            properties: {
                from_node: {
                    type: "string",
                    description: "Source node ID",
                    required: true
                },
                to_node: {
                    type: "string",
                    description: "Target node ID",
                    required: true
                },
                relationship_type: {
                    type: "string",
                    description: "Type of relationship",
                    required: true
                }
            },
            required: ["from_node", "to_node", "relationship_type"]
        }
    },

    execute_graph_cypher: {
        name: "execute_graph_cypher",
        description: "Execute a custom Cypher query directly on the Manifest graph database. Use this for complex graph traversals, pattern matching, or advanced queries that cannot be handled by other graph tools. Requires knowledge of Cypher query language. Use for complex analysis like finding shortest paths, detecting cycles, or performing multi-hop relationship queries. Most flexible but requires Cypher expertise. Endpoint: POST /graph/cypher",
        inputSchema: {
            type: "object",
            properties: {
                cypher_query: {
                    type: "string",
                    description: "Cypher query to execute",
                    required: true
                }
            },
            required: ["cypher_query"]
        }
    }
};

// MCP Tool Registry
class MCPToolRegistry {
    constructor() {
        this.tools = new Map();
        this.registerTools();
    }

    registerTools() {
        // Register VictoriaLogs tools
        this.tools.set('query_logs', this.queryLogs.bind(this));
        this.tools.set('search_logs', this.searchLogs.bind(this));
        this.tools.set('get_log_metrics', this.getLogMetrics.bind(this));
        this.tools.set('get_log_stats', this.getLogStats.bind(this));

        // Register VictoriaMetrics tools
        this.tools.set('query_metrics', this.queryMetrics.bind(this));
        this.tools.set('instant_query_metrics', this.instantQueryMetrics.bind(this));
        this.tools.set('get_metric_labels', this.getMetricLabels.bind(this));
        this.tools.set('get_metric_series', this.getMetricSeries.bind(this));

        // Register Manifest API tools
        this.tools.set('get_changelogs', this.getChangelogs.bind(this));
        this.tools.set('get_graph', this.getGraph.bind(this));
        this.tools.set('get_incidents', this.getIncidents.bind(this));
        this.tools.set('get_notifications', this.getNotifications.bind(this));
        this.tools.set('get_resources', this.getResources.bind(this));
        this.tools.set('get_tickets', this.getTickets.bind(this));

        // Register additional Manifest API Resource tools
        this.tools.set('get_resource_by_id', this.getResourceById.bind(this));
        this.tools.set('get_resource_tickets', this.getResourceTickets.bind(this));
        this.tools.set('search_resources', this.searchResources.bind(this));
        this.tools.set('get_resource_version', this.getResourceVersion.bind(this));
        this.tools.set('get_resource_metadata', this.getResourceMetadata.bind(this));

        // Register additional Changelog tools
        this.tools.set('get_changelog_by_id', this.getChangelogById.bind(this));
        this.tools.set('search_changelogs', this.searchChangelogs.bind(this));
        this.tools.set('get_changelog_by_resource', this.getChangelogByResource.bind(this));
        this.tools.set('get_changelog_list_by_resource', this.getChangelogListByResource.bind(this));
        this.tools.set('search_changelogs_by_event_type', this.searchChangelogsByEventType.bind(this));
        this.tools.set('search_changelogs_by_resource_id', this.searchChangelogsByResourceId.bind(this));

        // Register additional Notification tools
        this.tools.set('get_notification_by_id', this.getNotificationById.bind(this));
        this.tools.set('get_notification_rule', this.getNotificationRule.bind(this));
        this.tools.set('get_notifications_by_resource', this.getNotificationsByResource.bind(this));

        // Register additional Ticket tools
        this.tools.set('get_ticket_by_id', this.getTicketById.bind(this));
        this.tools.set('search_tickets', this.searchTickets.bind(this));

        // Register additional Incident tools
        this.tools.set('get_incident_by_id', this.getIncidentById.bind(this));
        this.tools.set('get_incident_changelogs', this.getIncidentChangelogs.bind(this));
        this.tools.set('get_incident_curated', this.getIncidentCurated.bind(this));
        this.tools.set('search_incidents', this.searchIncidents.bind(this));

        // Register Graph tools
        this.tools.set('get_graph_nodes', this.getGraphNodes.bind(this));
        this.tools.set('get_graph_by_label', this.getGraphByLabel.bind(this));
        this.tools.set('create_graph_link', this.createGraphLink.bind(this));
        this.tools.set('execute_graph_cypher', this.executeGraphCypher.bind(this));
    }

    // Get available tools
    getAvailableTools() {
        return Object.values(MCP_TOOLS);
    }

    // Execute a tool
    async executeTool(toolName, parameters) {
        if (!this.tools.has(toolName)) {
            throw new Error(`Tool '${toolName}' not found`);
        }

        const tool = this.tools.get(toolName);
        return await tool(parameters);
    }

    // VictoriaLogs tool implementations
    async queryLogs(params) {
        console.log('🔍 queryLogs called with params:', JSON.stringify(params));
        const { query, start_time, end_time, limit = 1000 } = params;

        try {
            // Validate query parameter
            if (!query) {
                console.error('❌ Query parameter missing! Params:', params);
                throw new Error('Query parameter is required');
            }

            // VictoriaLogs uses LogSQL syntax, not PromQL
            // Build the request parameters
            const requestParams = {
                query: query,
                limit: Math.min(limit, 10000) // Cap at 10000 to prevent overwhelming responses
            };

            // Add time range parameters if provided
            if (start_time) {
                requestParams.start = start_time;
                console.log('📅 Start time filter:', start_time);
            }
            if (end_time) {
                requestParams.end = end_time;
                console.log('📅 End time filter:', end_time);
            }

            // Check if query contains a timestamp filter and extract it (legacy support)
            if (!start_time && !end_time && typeof query === 'string') {
                const timestampMatch = query.match(/_time:([0-9TZ\-:.]+)/i);
                if (timestampMatch) {
                    // Extract timestamp and use it for time range filtering
                    const timestamp = timestampMatch[1];
                    // VictoriaLogs accepts 'start' and 'end' parameters for time filtering
                    // For a specific timestamp, search around that time (±1 second)
                    const targetTime = new Date(timestamp);
                    const startTime = new Date(targetTime.getTime() - 1000); // 1 second before
                    const endTime = new Date(targetTime.getTime() + 1000);   // 1 second after

                    requestParams.start = startTime.toISOString();
                    requestParams.end = endTime.toISOString();
                    // Remove _time from query since we're using time range params
                    requestParams.query = query.replace(/_time:[^\s]+\s*/i, '').trim() || '*';

                    console.log('📅 Time range query (legacy):', {
                        start: requestParams.start,
                        end: requestParams.end,
                        query: requestParams.query
                    });
                }
            }

            // First, get the total count using the /hits endpoint
            let totalCount = 0;
            let countIsExact = false;
            try {
                const hitsParams = { ...requestParams };
                delete hitsParams.limit; // Remove limit for count query
                const hitsResponse = await axios.get(`${VICTORIA_LOGS_API_URL}/hits`, {
                    params: hitsParams,
                    timeout: 10000
                });

                // VictoriaLogs /hits returns: {"hits": [{"total": 123456, ...}]}
                if (hitsResponse.data && Array.isArray(hitsResponse.data.hits) && hitsResponse.data.hits.length > 0) {
                    totalCount = hitsResponse.data.hits[0].total || 0;
                    countIsExact = true;
                } else if (typeof hitsResponse.data === 'object' && hitsResponse.data.hits !== undefined) {
                    totalCount = hitsResponse.data.hits;
                    countIsExact = true;
                } else if (typeof hitsResponse.data === 'number') {
                    totalCount = hitsResponse.data;
                    countIsExact = true;
                } else if (typeof hitsResponse.data === 'string') {
                    totalCount = parseInt(hitsResponse.data, 10) || 0;
                    countIsExact = totalCount > 0;
                }
                console.log(`📊 Total matching logs: ${totalCount}, returning up to ${requestParams.limit}`);
            } catch (hitsError) {
                console.warn('⚠️ Could not fetch total count from /hits endpoint:', hitsError.message);
                // CRITICAL: Set flag so LLM knows count is unknown
                // Without this flag, if logs.length=1000, LLM thinks there are "exactly 1000 logs"
                // when there might be 1,000,000+ logs (hallucination risk)
                countIsExact = false;
            }

            const response = await axios.get(`${VICTORIA_LOGS_API_URL}/query`, {
                params: requestParams,
                timeout: 30000
            });

            // VictoriaLogs returns newline-delimited JSON (NDJSON), not a JSON array
            let logs = [];
            if (typeof response.data === 'string') {
                // Split by newlines and parse each JSON object
                const lines = response.data.trim().split('\n');
                logs = lines.map(line => {
                    try {
                        return JSON.parse(line);
                    } catch (e) {
                        return null;
                    }
                }).filter(log => log !== null);
            } else if (Array.isArray(response.data)) {
                logs = response.data;
            } else {
                logs = [response.data];
            }

            return {
                query: query,
                start_time: start_time || 'not specified',
                end_time: end_time || 'not specified',
                limit: requestParams.limit,
                total_count: totalCount > 0 ? totalCount : logs.length, // Use total if available, otherwise returned count
                count_is_exact: countIsExact, // Flag indicating if total_count is reliable
                count_unknown: !countIsExact, // Explicit flag for LLM prompt processing
                is_limited: logs.length >= requestParams.limit, // Flag indicating if results were truncated
                returned_count: logs.length,
                logs: logs,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            console.error('VictoriaLogs query error details:', error.response?.data || error.message);
            throw new Error(`VictoriaLogs query failed: ${error.response?.data?.error || error.message}`);
        }
    }

    async searchLogs(params) {
        const { search_text, labels = {}, limit = 20 } = params;
        console.log(`🔍 searchLogs called with: search_text="${search_text}", labels=${JSON.stringify(labels)}, limit=${limit}`);

        // Validate search_text - reject undefined/null as string
        if (search_text && (search_text === "undefined" || search_text === "null" || search_text.toLowerCase() === "undefined")) {
            console.log(`❌ Rejected invalid search_text: "${search_text}"`);
            return {
                search_text: search_text,
                labels: labels,
                count: 0,
                logs: [],
                timestamp: new Date().toISOString(),
                error: "Invalid search_text parameter. Do not pass 'undefined' or 'null' as a string."
            };
        }

        try {
            let query = '';

            // Build LogSQL query based on search parameters
            if (search_text) {
                // Search for text in log content using LogSQL syntax with wildcards
                query = `_msg:*${search_text}*`;
            } else if (Object.keys(labels).length > 0) {
                // Search by labels using LogSQL syntax
                const labelSelectors = Object.entries(labels)
                    .map(([key, value]) => `${key}:${value}`)
                    .join(' AND ');
                query = labelSelectors;
            } else {
                // Default query to get recent logs
                query = '*';
            }

            const response = await axios.get(`${VICTORIA_LOGS_API_URL}/query`, {
                params: {
                    query: query,
                    limit: Math.min(limit, 10000) // Cap at 10000
                },
                timeout: 30000
            });

            // VictoriaLogs returns newline-delimited JSON (NDJSON)
            let logs = [];
            if (typeof response.data === 'string') {
                // Split by newlines and parse each JSON object
                const lines = response.data.trim().split('\n');
                logs = lines.map(line => {
                    try {
                        return JSON.parse(line);
                    } catch (e) {
                        return null;
                    }
                }).filter(log => log !== null);
            } else if (Array.isArray(response.data)) {
                logs = response.data;
            } else {
                logs = [response.data];
            }

            console.log(`✅ VictoriaLogs returned ${logs.length} logs for query "${query}"`);

            return {
                search_text: search_text,
                labels: labels,
                count: logs.length,
                logs: logs,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`VictoriaLogs search failed: ${error.message}`);
        }
    }

    async getLogMetrics(params) {
        const { metric_type = 'fields' } = params;

        try {
            // VictoriaLogs uses field_names endpoint for field metadata
            let endpoint;
            let query = '*';

            switch (metric_type.toLowerCase()) {
                case 'fields':
                    endpoint = '/field_names';
                    break;
                case 'streams':
                    endpoint = '/stream_field_names';
                    break;
                case 'field_values':
                    // Get field values requires a field name parameter
                    endpoint = '/field_values';
                    break;
                default:
                    endpoint = '/field_names';
            }

            const response = await axios.get(`${VICTORIA_LOGS_API_URL}${endpoint}`, {
                params: { query },
                timeout: 30000
            });

            // VictoriaLogs returns {values: [{value: "field_name", hits: count}, ...]}
            const fields = response.data?.values || response.data || [];

            return {
                metric_type: metric_type,
                fields: Array.isArray(fields) ? fields : [fields],
                count: Array.isArray(fields) ? fields.length : 0,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`VictoriaLogs metadata query failed: ${error.message}`);
        }
    }

    async getLogStats(params) {
        const { query = '*' } = params;

        try {
            const response = await axios.get(`${VICTORIA_LOGS_API_URL}/query`, {
                params: {
                    query: query
                },
                timeout: 30000
            });

            // VictoriaLogs returns newline-delimited JSON (NDJSON)
            let logs = [];
            if (typeof response.data === 'string') {
                // Split by newlines and parse each JSON object
                const lines = response.data.trim().split('\n');
                logs = lines.map(line => {
                    try {
                        return JSON.parse(line);
                    } catch (e) {
                        return null;
                    }
                }).filter(log => log !== null);
            } else if (Array.isArray(response.data)) {
                logs = response.data;
            } else {
                logs = [response.data];
            }

            return {
                query: query,
                count: logs.length,
                logs: logs,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`VictoriaLogs stats query failed: ${error.message}`);
        }
    }

    // Helper method to parse time inputs
    parseTimeInput(timeInput) {
        if (!timeInput || timeInput === 'now') {
            return Math.floor(Date.now() / 1000);
        }

        // Handle relative time (e.g., "1h", "30m", "1d")
        const relativeTimeMatch = timeInput.match(/^(\d+)([smhd])$/);
        if (relativeTimeMatch) {
            const value = parseInt(relativeTimeMatch[1]);
            const unit = relativeTimeMatch[2];
            const now = Math.floor(Date.now() / 1000);

            switch (unit) {
                case 's': return now - value;
                case 'm': return now - (value * 60);
                case 'h': return now - (value * 3600);
                case 'd': return now - (value * 86400);
                default: return now - 3600; // Default to 1 hour
            }
        }

        // Handle Unix timestamp
        if (/^\d+$/.test(timeInput)) {
            return parseInt(timeInput);
        }

        // Handle RFC3339/ISO 8601 format
        const parsedDate = new Date(timeInput);
        const timestamp = Math.floor(parsedDate.getTime() / 1000);

        // Check for Invalid Date (getTime() returns NaN)
        if (isNaN(timestamp)) {
            console.warn(`⚠️ Invalid time format: "${timeInput}". Defaulting to 1 hour ago.`);
            return Math.floor(Date.now() / 1000) - 3600;
        }

        return timestamp;
    }

    // VictoriaMetrics tool implementations
    async queryMetrics(params) {
        const { query, start_time, end_time, step = '1m' } = params;

        try {
            const requestParams = {
                query: query,
                step: step
            };

            // Add time range if provided
            if (start_time) {
                requestParams.start = this.parseTimeInput(start_time);
            }
            if (end_time) {
                requestParams.end = this.parseTimeInput(end_time);
            } else {
                requestParams.end = Math.floor(Date.now() / 1000);
            }

            // Default to last 1 hour if no start time
            if (!requestParams.start) {
                requestParams.start = requestParams.end - 3600;
            }

            console.log('📊 VictoriaMetrics Query:', {
                url: `${VICTORIA_METRICS_SELECT_URL}/select/0/prometheus/api/v1/query_range`,
                query: requestParams.query,
                start: new Date(requestParams.start * 1000).toISOString(),
                end: new Date(requestParams.end * 1000).toISOString(),
                step: requestParams.step
            });

            const response = await axios.get(`${VICTORIA_METRICS_SELECT_URL}/select/0/prometheus/api/v1/query_range`, {
                params: requestParams,
                timeout: 30000
            });

            const data = response.data?.data || {};
            const metrics = data.result || [];

            return {
                query: query,
                start_time: new Date(requestParams.start * 1000).toISOString(),
                end_time: new Date(requestParams.end * 1000).toISOString(),
                step: step,
                result_type: data.resultType || 'matrix',
                metrics_count: metrics.length,
                metrics: metrics,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            console.error('VictoriaMetrics query error:', error.response?.data || error.message);
            throw new Error(`VictoriaMetrics query failed: ${error.response?.data?.error || error.message}`);
        }
    }

    async instantQueryMetrics(params) {
        const { query, time } = params;

        try {
            const requestParams = {
                query: query
            };

            // Add specific time if provided, otherwise use current time
            if (time) {
                requestParams.time = this.parseTimeInput(time);
            }

            console.log('📊 VictoriaMetrics Instant Query:', {
                url: `${VICTORIA_METRICS_SELECT_URL}/select/0/prometheus/api/v1/query`,
                query: requestParams.query,
                time: requestParams.time ? new Date(requestParams.time * 1000).toISOString() : 'now'
            });

            const response = await axios.get(`${VICTORIA_METRICS_SELECT_URL}/select/0/prometheus/api/v1/query`, {
                params: requestParams,
                timeout: 30000
            });

            const data = response.data?.data || {};
            const metrics = data.result || [];

            return {
                query: query,
                query_time: requestParams.time ? new Date(requestParams.time * 1000).toISOString() : new Date().toISOString(),
                result_type: data.resultType || 'vector',
                metrics_count: metrics.length,
                metrics: metrics,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            console.error('VictoriaMetrics instant query error:', error.response?.data || error.message);
            throw new Error(`VictoriaMetrics instant query failed: ${error.response?.data?.error || error.message}`);
        }
    }

    async getMetricLabels(params) {
        const { label_name } = params;

        try {
            const endpoint = label_name
                ? `/select/0/prometheus/api/v1/label/${encodeURIComponent(label_name)}/values`
                : '/select/0/prometheus/api/v1/labels';

            console.log(`📊 VictoriaMetrics Label Query: ${endpoint}`);

            const response = await axios.get(`${VICTORIA_METRICS_SELECT_URL}${endpoint}`, {
                timeout: 10000
            });

            return {
                label_name: label_name || 'all_labels',
                labels: response.data?.data || [],
                count: Array.isArray(response.data?.data) ? response.data.data.length : 0,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`VictoriaMetrics label query failed: ${error.response?.data?.error || error.message}`);
        }
    }

    async getMetricSeries(params) {
        const { match, start_time, end_time } = params;

        if (!match) {
            throw new Error('match parameter is required (e.g., "{__name__=~".*"}")');
        }

        try {
            const requestParams = {
                'match[]': match
            };

            if (start_time) {
                requestParams.start = this.parseTimeInput(start_time);
            }
            if (end_time) {
                requestParams.end = this.parseTimeInput(end_time);
            }

            console.log('📊 VictoriaMetrics Series Query:', requestParams);

            const response = await axios.get(`${VICTORIA_METRICS_SELECT_URL}/select/0/prometheus/api/v1/series`, {
                params: requestParams,
                timeout: 30000
            });

            const series = response.data?.data || [];

            return {
                match: match,
                series_count: series.length,
                series: series,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`VictoriaMetrics series query failed: ${error.response?.data?.error || error.message}`);
        }
    }

    // Manifest API Tool Methods
    async getChangelogs(params) {
        const { offset = 0 } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/changelog`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: { offset },
                timeout: 30000
            });

            return {
                changelogs: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                count_is_exact: false, // API doesn't provide total count, only returned results
                is_limited: true, // Results may be paginated/limited by API
                offset,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API changelogs failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getGraph(params) {
        const { graph_type } = params;

        try {
            const url = graph_type
                ? `${MANIFEST_API_URL}/client/graph/${graph_type}`
                : `${MANIFEST_API_URL}/client/graph`;

            const response = await axios.get(url, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                graph_type: graph_type || 'default',
                data: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API graph failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getIncidents(params) {
        const { status } = params;

        try {
            console.log('🔍 Calling Manifest API:', `${MANIFEST_API_URL}/client/incident`);
            console.log('🔑 Using API Key:', config.MANIFEST_API_KEY ? 'Present' : 'Missing');

            const response = await axios.get(`${MANIFEST_API_URL}/client/incident`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: { status },
                timeout: 30000
            });

            return {
                incidents: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                count_is_exact: false, // API doesn't provide total count, only returned results
                is_limited: true, // Results may be paginated/limited by API
                filter_status: status,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            console.error('❌ Manifest API Error:', {
                status: error.response?.status,
                statusText: error.response?.statusText,
                data: error.response?.data,
                message: error.message
            });

            const errorMsg = error.response?.data?.error || error.response?.data?.message || error.response?.statusText || error.message;

            if (errorMsg.includes('invalidated') || errorMsg.includes('not meant for')) {
                throw new Error(`Manifest API authentication failed: ${errorMsg}. Please verify your API key is valid and generated for the correct organization.`);
            }

            throw new Error(`Manifest API incidents failed: ${errorMsg}`);
        }
    }

    async getNotifications(params) {
        const { } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/notification`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                notifications: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                count_is_exact: false, // API doesn't provide total count, only returned results
                is_limited: true, // Results may be paginated/limited by API
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API notifications failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getResources(params) {
        const { resource_type } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/resource`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: { resource_type },
                timeout: 30000
            });

            return {
                resources: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                count_is_exact: false, // API doesn't provide total count
                is_limited: true, // Results may be paginated
                resource_type,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API resources failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getTickets(params) {
        const { status } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/ticket`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: { status },
                timeout: 30000
            });

            return {
                tickets: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                count_is_exact: false, // API doesn't provide total count
                is_limited: true, // Results may be paginated
                filter_status: status,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API tickets failed: ${error.response?.data?.message || error.message}`);
        }
    }

    // Additional Resource Methods
    async getResourceById(params) {
        const { resource_id } = params;
        const resourceIdInt = parseInt(resource_id, 10);

        if (isNaN(resourceIdInt)) {
            throw new Error(`Invalid resource_id: ${resource_id} must be a valid integer`);
        }

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/resource/${resourceIdInt}`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                resource: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get resource by ID failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getResourceTickets(params) {
        const { resource_id } = params;
        const resourceIdInt = parseInt(resource_id, 10);

        if (isNaN(resourceIdInt)) {
            throw new Error(`Invalid resource_id: ${resource_id} must be a valid integer`);
        }

        try {
            console.log(`🔍 Getting tickets for resource: ${resourceIdInt} (type: ${typeof resourceIdInt})`);
            const url = `${MANIFEST_API_URL}/client/resource/${resourceIdInt}/ticket`;
            console.log(`📡 URL: ${url}`);

            const response = await axios.get(url, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            console.log(`✅ Got ${response.data.length} tickets for resource ${resource_id}`);

            return {
                resource_id,
                tickets: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                count_is_exact: false, // API doesn't provide total count
                is_limited: true, // Results may be limited
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            console.error(`❌ Error getting resource tickets:`, error.response?.data);
            throw new Error(`Manifest API get resource tickets failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async searchResources(params) {
        const { query, page = 1, page_size = 20 } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/resource/search`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: { query, page, page_size },
                timeout: 30000
            });

            return {
                resources: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                count_is_exact: false, // Search doesn't return total count
                is_limited: true, // Results limited by page_size
                page,
                page_size,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API search resources failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getResourceVersion(params) {
        const { resource_id } = params;
        const resourceIdInt = parseInt(resource_id, 10);

        if (isNaN(resourceIdInt)) {
            throw new Error(`Invalid resource_id: ${resource_id} must be a valid integer`);
        }

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/resource/${resourceIdInt}/version`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                resource_id,
                version: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get resource version failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getResourceMetadata(params) {
        const { resource_id } = params;
        const resourceIdInt = parseInt(resource_id, 10);

        if (isNaN(resourceIdInt)) {
            throw new Error(`Invalid resource_id: ${resource_id} must be a valid integer`);
        }

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/resource/${resourceIdInt}/metadata`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                resource_id,
                metadata: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get resource metadata failed: ${error.response?.data?.message || error.message}`);
        }
    }

    // Additional Changelog Methods
    async getChangelogById(params) {
        const { changelog_id } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/changelog/${changelog_id}`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                changelog: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get changelog by ID failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async searchChangelogs(params) {
        const { severity, provider_key, description, page = 1, page_size = 20 } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/changelog/search`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: { severity, provider_key, description, page, page_size },
                timeout: 30000
            });

            return {
                changelogs: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                count_is_exact: false, // Search doesn't return total count
                is_limited: true, // Results limited by page_size
                page,
                page_size,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API search changelogs failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getChangelogByResource(params) {
        const { resource_id } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/changelog/resource/${resource_id}`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                resource_id,
                changelogs: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get changelog by resource failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getChangelogListByResource(params) {
        const { resource_id } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/changelog/resource/${resource_id}/list`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                resource_id,
                changelogs: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get changelog list by resource failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async searchChangelogsByEventType(params) {
        const { event_type, severity, page = 1, page_size = 20 } = params;

        try {
            // Use the general search endpoint with event_type filter instead of the broken /event_type endpoint
            const queryParams = { page, page_size };
            if (event_type) queryParams.event_type = event_type;
            if (severity) queryParams.severity = severity;

            const response = await axios.get(`${MANIFEST_API_URL}/client/changelog/search`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: queryParams,
                timeout: 30000
            });

            return {
                event_type,
                changelogs: response.data?.changelogs || response.data,
                count: response.data?.count || (Array.isArray(response.data) ? response.data.length : 0),
                page,
                page_size,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API search changelogs by event type failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async searchChangelogsByResourceId(params) {
        const { resource_id, severity, page = 1, page_size = 20 } = params;

        try {
            // Use the general search endpoint with resource_id filter instead of the broken /resource_id endpoint
            const queryParams = { page, page_size };
            if (resource_id) queryParams.resource_id = resource_id;
            if (severity) queryParams.severity = severity;

            const response = await axios.get(`${MANIFEST_API_URL}/client/changelog/search`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: queryParams,
                timeout: 30000
            });

            return {
                resource_id,
                changelogs: response.data?.changelogs || response.data,
                count: response.data?.count || (Array.isArray(response.data) ? response.data.length : 0),
                page,
                page_size,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API search changelogs by resource ID failed: ${error.response?.data?.message || error.message}`);
        }
    }

    // Additional Notification Methods
    async getNotificationById(params) {
        const { notification_id } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/notification/${notification_id}`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                notification: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get notification by ID failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getNotificationRule(params) {
        const { rule_id } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/notification/rule/${rule_id}`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                rule: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get notification rule failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getNotificationsByResource(params) {
        const { resource_id } = params;

        try {
            console.log(`🔔 Getting notifications for resource: ${resource_id} (type: ${typeof resource_id})`);
            const url = `${MANIFEST_API_URL}/client/notification/resource/${resource_id}`;
            console.log(`📡 URL: ${url}`);

            const response = await axios.get(url, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            console.log(`✅ Got ${response.data.length || 0} notifications for resource ${resource_id}`);

            return {
                resource_id,
                notifications: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                count_is_exact: false, // API doesn't provide total count
                is_limited: true, // Results may be limited
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            console.error(`❌ Error getting notifications by resource:`, error.response?.data);
            throw new Error(`Manifest API get notifications by resource failed: ${error.response?.data?.message || error.message}`);
        }
    }

    // Additional Ticket Methods
    async getTicketById(params) {
        const { ticket_id } = params;

        try {
            // If ticket_id looks like a sourceRef (contains letters/hyphens), search for it first
            let actualTicketId = ticket_id;
            if (isNaN(ticket_id) || ticket_id.includes('-')) {
                console.log(`🔍 Looking up sourceRef: ${ticket_id}`);
                // Search for ticket by sourceRef - get all tickets
                const searchResponse = await axios.get(`${MANIFEST_API_URL}/client/ticket`, {
                    headers: {
                        'Mit-Api-Key': config.MANIFEST_API_KEY,
                        'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                        'Content-Type': 'application/json'
                    },
                    timeout: 30000
                });

                const tickets = Array.isArray(searchResponse.data) ? searchResponse.data : [];
                console.log(`📋 Found ${tickets.length} tickets`);

                // Find ticket with matching sourceRef
                const ticket = tickets.find(t => t.sourceRef === ticket_id);
                if (!ticket) {
                    console.log(`❌ No ticket found with sourceRef: ${ticket_id}`);
                    // Log first few sourceRefs for debugging
                    const refs = tickets.slice(0, 5).map(t => t.sourceRef);
                    console.log(`   Sample sourceRefs: ${refs.join(', ')}`);
                    throw new Error(`Ticket with sourceRef '${ticket_id}' not found`);
                }
                console.log(`✅ Found ticket ID: ${ticket.id} for sourceRef: ${ticket_id}`);
                actualTicketId = ticket.id;
            }

            const response = await axios.get(`${MANIFEST_API_URL}/client/ticket/${actualTicketId}`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                ticket: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get ticket by ID failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async searchTickets(params) {
        const { title, type, priority, status, severity, page = 1, page_size = 20 } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/ticket/search`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: { title, type, priority, status, severity, page, page_size },
                timeout: 30000
            });

            return {
                tickets: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                page,
                page_size,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API search tickets failed: ${error.response?.data?.message || error.message}`);
        }
    }

    // Additional Incident Methods
    async getIncidentById(params) {
        const { incident_id } = params;

        // Validate and convert incident_id to integer
        const incidentIdInt = parseInt(incident_id, 10);
        if (isNaN(incidentIdInt)) {
            throw new Error(`Invalid incident_id: '${incident_id}' must be a valid integer`);
        }

        console.log(`🔍 get_incident_by_id: input='${incident_id}' (type: ${typeof incident_id}), parsed=${incidentIdInt} (type: ${typeof incidentIdInt})`);

        try {
            const url = `${MANIFEST_API_URL}/client/incident/${incidentIdInt}`;
            console.log(`📡 Making request to: ${url}`);
            const response = await axios.get(url, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                incident: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get incident by ID failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getIncidentChangelogs(params) {
        const { incident_id } = params;

        // Validate and convert incident_id to integer
        const incidentIdInt = parseInt(incident_id, 10);
        if (isNaN(incidentIdInt)) {
            throw new Error(`Invalid incident_id: '${incident_id}' must be a valid integer`);
        }

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/incident/${incidentIdInt}/changelogs`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                incident_id,
                changelogs: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get incident changelogs failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getIncidentCurated(params) {
        const { incident_id } = params;

        // Validate and convert incident_id to integer
        const incidentIdInt = parseInt(incident_id, 10);
        if (isNaN(incidentIdInt)) {
            throw new Error(`Invalid incident_id: '${incident_id}' must be a valid integer`);
        }

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/incident/${incidentIdInt}/curated`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                incident_id,
                curated_incident: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get curated incident failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async searchIncidents(params) {
        const { query, title, priority, status, severity, page = 1, page_size = 20 } = params;

        // Map 'query' parameter to 'title' for the API call
        const searchTitle = query || title;

        console.log(`🔍 searchIncidents - Received params:`, JSON.stringify(params));
        console.log(`🔍 searchIncidents - Search title: "${searchTitle}"`);

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/incident/search`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                params: { title: searchTitle, priority, status, severity, page, page_size },
                timeout: 30000
            });

            console.log(`🔍 searchIncidents - Manifest API returned ${response.data.length} incidents`);

            return {
                incidents: response.data,
                count: Array.isArray(response.data) ? response.data.length : 0,
                page,
                page_size,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API search incidents failed: ${error.response?.data?.message || error.message}`);
        }
    }

    // Graph Methods
    async getGraphNodes(params) {
        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/graph`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                graph: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get graph nodes failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async getGraphByLabel(params) {
        const { label } = params;

        try {
            const response = await axios.get(`${MANIFEST_API_URL}/client/graph/${label}`, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                label,
                graph: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API get graph by label failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async createGraphLink(params) {
        const { from_node, to_node, relationship_type } = params;

        try {
            const response = await axios.post(`${MANIFEST_API_URL}/client/graph`, {
                from_node,
                to_node,
                relationship_type
            }, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                from_node,
                to_node,
                relationship_type,
                result: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API create graph link failed: ${error.response?.data?.message || error.message}`);
        }
    }

    async executeGraphCypher(params) {
        const { cypher_query } = params;

        try {
            const response = await axios.post(`${MANIFEST_API_URL}/client/graph/cypher`, {
                query: cypher_query
            }, {
                headers: {
                    'Mit-Api-Key': config.MANIFEST_API_KEY,
                    'Mit-Org-Key': config.MANIFEST_ORG_KEY || 'dev',
                    'Content-Type': 'application/json'
                },
                timeout: 30000
            });

            return {
                query: cypher_query,
                result: response.data,
                timestamp: new Date().toISOString()
            };
        } catch (error) {
            throw new Error(`Manifest API execute graph cypher failed: ${error.response?.data?.message || error.message}`);
        }
    }
}

// Initialize MCP Tool Registry
const mcpRegistry = new MCPToolRegistry();

// Middleware
app.use(express.json());
app.use(express.static('public'));

// CORS middleware
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept');
    res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    if (req.method === 'OPTIONS') {
        res.sendStatus(200);
    } else {
        next();
    }
});

// Neo4j configuration moved to top

// VictoriaLogs configuration
const VICTORIA_METRICS_URL = config.VICTORIA_METRICS_URL;
const VICTORIA_LOGS_API_URL = config.VICTORIA_LOGS_URL;

// VictoriaMetrics configuration (for metrics queries)
const VICTORIA_METRICS_SELECT_URL = config.VICTORIA_METRICS_SELECT_URL;
const VICTORIA_METRICS_INSERT_URL = config.VICTORIA_METRICS_INSERT_URL;

// Manifest API configuration
const MANIFEST_API_URL = config.MANIFEST_API_URL;
const MANIFEST_API_KEY = config.MANIFEST_API_KEY;

// Debug: Log Manifest API configuration on startup
console.log('🔧 Manifest API Configuration:');
console.log('   URL:', MANIFEST_API_URL);
console.log('   API Key:', MANIFEST_API_KEY ? `${MANIFEST_API_KEY.substring(0, 20)}...` : 'NOT LOADED');

// Neo4j helper function to execute Cypher queries
async function executeCypher(query, params = {}) {
    if (!neo4jDriver) {
        throw new Error('Neo4j driver not initialized');
    }

    const session = neo4jDriver.session({
        database: NEO4J_DATABASE,
        defaultAccessMode: neo4j.session.READ
    });

    try {
        const result = await session.run(query, params);
        return result;
    } catch (error) {
        console.error('Neo4j query error:', error.message);
        throw error;
    } finally {
        await session.close();
    }
}

// Function to test Neo4j connection
async function testNeo4jConnection() {
    try {
        console.log('Testing Neo4j connection...');
        const result = await executeCypher('RETURN "Neo4j connection successful" as message');
        const message = result.records[0].get('message');
        console.log('✅ Neo4j connection successful:', message);
        return true;
    } catch (error) {
        console.error('❌ Neo4j connection failed:', error.message);
        console.error('Please ensure Neo4j is running and credentials are correct');
        return false;
    }
}

// MCP Tool Discovery Endpoint
app.get('/api/mcp/tools', (req, res) => {
    try {
        res.json({
            tools: mcpRegistry.getAvailableTools(),
            mcp_version: "1.0.0",
            server_info: "VictoriaLogs MCP Server"
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

// Health Check Endpoint
app.get('/api/health', (req, res) => {
    try {
        res.json({
            status: "healthy",
            service: "VictoriaLogs MCP Server",
            version: "1.0.0",
            timestamp: new Date().toISOString(),
            checks: {
                server: "operational",
                tools_count: mcpRegistry.getAvailableTools().length
            }
        });
    } catch (error) {
        res.status(500).json({
            status: "unhealthy",
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

// MCP Tool Execution Endpoint
app.post('/api/mcp/execute', async (req, res) => {
    try {
        // Support both 'parameters' and 'arguments' keys
        const tool_name = req.body.tool_name;
        const toolParams = req.body.parameters || req.body.arguments || {};

        console.log(`🔧 MCP Execute - Tool: ${tool_name}, Params:`, JSON.stringify(toolParams));

        if (!tool_name) {
            return res.status(400).json({ error: 'tool_name is required' });
        }

        const result = await mcpRegistry.executeTool(tool_name, toolParams);

        res.json({
            success: true,
            tool_name,
            result,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({
            success: false,
            error: error.message,
            tool_name: req.body.tool_name
        });
    }
});

// AI execution endpoint - uses LLM with tool descriptions for intelligent selection
app.post('/api/ai-execute', async (req, res) => {
    try {
        const { prompt, tool_category } = req.body;

        if (!prompt) {
            return res.status(400).json({ error: 'Prompt is required' });
        }

        console.log('🤖 AI Agent processing prompt:', prompt);
        if (tool_category) {
            console.log('📂 Tool category filter:', tool_category);
        }

        if (!llmAvailable) {
            return res.status(503).json({
                error: 'LLM service not available',
                message: 'Please configure OpenAI API key or Llama endpoint'
            });
        }

        // ⚠️ BUG FIX: Context Window Explosion Prevention
        // With ~50 tools, embedding ALL tool descriptions burns ~5000+ tokens per request
        // Solution: Filter tools by category OR use all if no category specified
        const toolCategories = {
            'neo4j': ['get_node_labels', 'get_relationship_types', 'get_schema', 'query_nodes', 'search_nodes', 'get_relationships', 'execute_cypher', 'get_node_count', 'get_database_stats'],
            'logs': ['query_logs', 'search_logs', 'get_log_metrics', 'get_log_stats'],
            'metrics': ['query_metrics', 'instant_query_metrics', 'get_metric_labels', 'get_metric_series'],
            'incidents': ['get_incidents', 'get_incident_by_id'],
            'tickets': ['get_tickets', 'get_ticket_by_id', 'search_tickets', 'get_resource_tickets'],
            'resources': ['get_resources', 'get_resource_by_id', 'search_resources'],
            'changelogs': ['get_changelogs', 'get_changelog_by_id', 'search_changelogs', 'get_resource_changelogs', 'get_changelog_by_resource', 'get_changelog_list_by_resource'],
            'notifications': ['get_notifications', 'get_resource_notifications'],
            'graph': ['get_graph']
        };

        // Filter tools based on category
        let availableTools = MCP_TOOLS;
        if (tool_category && toolCategories[tool_category]) {
            const categoryToolNames = toolCategories[tool_category];
            availableTools = Object.fromEntries(
                Object.entries(MCP_TOOLS).filter(([name]) => categoryToolNames.includes(name))
            );
            console.log(`📊 Filtered to ${Object.keys(availableTools).length} tools in category '${tool_category}'`);
        } else {
            console.log(`⚠️ Loading ALL ${Object.keys(MCP_TOOLS).length} tools (high token cost)`);
        }

        // Build tool catalog with descriptions for LLM
        const toolCatalog = Object.entries(availableTools).map(([name, schema]) => {
            const params = schema.inputSchema?.properties || {};
            const required = schema.inputSchema?.required || [];

            return {
                name,
                description: schema.description,
                parameters: Object.entries(params).map(([paramName, paramSpec]) => ({
                    name: paramName,
                    type: paramSpec.type,
                    description: paramSpec.description,
                    required: required.includes(paramName)
                }))
            };
        });

        // Create system message with tool catalog
        const systemMessage = `You are an intelligent tool router and parameter extractor. Your job is to:
1. Analyze the user's query
2. Select the MOST APPROPRIATE tool from the available tools based on tool descriptions
3. Extract ALL required parameters from the query

CRITICAL RULES:
- Read tool descriptions CAREFULLY - they explain WHEN to use each tool
- Pay attention to parameter types (e.g., "resource_id" vs "changelog_id")
- If a tool says "NOT resource ID", don't use resource IDs with it
- Match the user's intent to the tool's use case described in its description

Available Tools:
${toolCatalog.map(t => `
${t.name}:
  Description: ${t.description}
  Parameters: ${t.parameters.map(p => `${p.name} (${p.type}${p.required ? ', required' : ''}): ${p.description}`).join('; ')}
`).join('\n')}

OUTPUT FORMAT (JSON only):
{
  "tool": "selected_tool_name",
  "parameters": {
    "param_name": "extracted_value"
  },
  "reasoning": "why this tool was selected based on its description"
}`;

        const messages = [
            { role: "system", content: systemMessage },
            { role: "user", content: `Query: "${prompt}"\n\nSelect the appropriate tool and extract parameters. Output JSON only.` }
        ];

        const aiResponse = await callLLM(messages, 0.1, 500);
        console.log('🧠 LLM Response:', aiResponse);

        // Parse LLM response
        let toolSelection;
        try {
            const jsonMatch = aiResponse.match(/{[\s\S]*}/);
            if (!jsonMatch) {
                throw new Error('No JSON found in LLM response');
            }
            toolSelection = JSON.parse(jsonMatch[0]);
        } catch (parseError) {
            console.error('❌ Failed to parse LLM response:', parseError);
            return res.status(500).json({
                error: 'Failed to understand the query',
                details: aiResponse
            });
        }

        const { tool: selectedTool, parameters, reasoning } = toolSelection;
        console.log(`🎯 Selected tool: ${selectedTool}`);
        console.log(`📋 Parameters:`, parameters);
        console.log(`💭 Reasoning: ${reasoning}`);

        // Validate tool exists
        if (!MCP_TOOLS[selectedTool]) {
            return res.status(400).json({
                error: `Unknown tool: ${selectedTool}`,
                available_tools: Object.keys(MCP_TOOLS)
            });
        }

        // Execute the selected tool
        let result;
        try {
            console.log(`🔧 Executing tool: ${selectedTool} with params:`, parameters);
            result = await mcpRegistry.executeTool(selectedTool, parameters || {});
        } catch (execError) {
            console.error('❌ Tool execution failed:', execError);
            return res.status(500).json({
                error: `Tool execution failed: ${execError.message}`,
                tool: selectedTool,
                parameters
            });
        }

        // Format the result using LLM
        let formattedResult = null;
        try {
            // Determine formatting instructions based on tool type
            let formatInstructions = 'Provide a clear, concise summary of this data.';

            if (selectedTool.includes('log') && !selectedTool.includes('changelog')) {
                formatInstructions = `This is LOG DATA from VictoriaLogs. Write 1-2 sentences: "Found X log entries" and mention the most common pattern or level.`;
            } else if (selectedTool.includes('ticket')) {
                formatInstructions = `Analyze TICKET data. Start with summary (I found X tickets...), then describe each ticket with key details (ID, title, status, priority, description). End with insights about urgent items or trends. Write in natural paragraphs.`;
            } else if (selectedTool.includes('incident')) {
                formatInstructions = `Analyze INCIDENT data. Start with summary (I found X incidents...), highlight critical items, describe each with details (ID, title, severity, status, impact). End with analysis of patterns or concerns. Write in natural paragraphs.`;
            } else if (selectedTool.includes('changelog')) {
                formatInstructions = `Analyze CHANGELOG data. Start with summary (I found X changes...), then describe 5-10 most recent/important changes. For each change, explain what happened (resource/service name, what changed, when, severity, who made it). End with key observations about patterns, important changes, or recommendations. Write in natural flowing paragraphs like a professional report. Make timestamps readable (e.g., "Oct 26, 11:30 PM").`;
            } else if (selectedTool.includes('notification')) {
                formatInstructions = `Analyze NOTIFICATION data. Provide helpful insights with summary, important notifications, and actionable items. Write in natural paragraphs.`;
            } else if (selectedTool.includes('resource')) {
                formatInstructions = `Analyze RESOURCE data. Provide useful information about the resources with key insights and observations. Write in natural paragraphs.`;
            } else if (selectedTool.includes('schema') || selectedTool.includes('node') || selectedTool.includes('relationship')) {
                formatInstructions = `This is graph database schema. Write 1-2 sentences with key statistics.`;
            }

            const formatPrompt = `${formatInstructions}

JSON Data (first 15000 chars):
${JSON.stringify(result, null, 2).substring(0, 15000)}...

Total count in result: ${result.count || result.tickets?.length || result.changelogs?.length || result.incidents?.length || 'unknown'}`;

            const formatMessages = [
                {
                    role: "system", content: `You are a helpful data analyst. Analyze the data and provide clear, conversational insights in plain English. 

CRITICAL FORMATTING RULES:
- NO markdown symbols (no #, ##, ###, *, **, ___, etc.)
- NO bullet points with • or -
- Write in natural paragraphs and sentences
- Use simple line breaks between sections
- Format like a professional email or report
- Be conversational but professional

Focus on what's useful and actionable. Help users understand what's happening in their systems.` },
                { role: "user", content: formatPrompt }
            ];

            formattedResult = await callLLM(formatMessages, 0.3, 2000);
            console.log('📝 Formatted result:', formattedResult);
        } catch (formatError) {
            console.warn('⚠️ Could not format result:', formatError.message);
            formattedResult = JSON.stringify(result, null, 2);
        }

        res.json({
            message: formattedResult,
            tool_used: selectedTool,
            reasoning: reasoning,
            raw_result: result
        });

    } catch (error) {
        console.error('❌ AI execution error:', error);
        res.status(500).json({
            error: `Failed to execute prompt: ${error.message}`
        });
    }
});

// Start Express server
app.listen(PORT, () => {
    console.log(`🚀 VictoriaLogs MCP Server running on port ${PORT}`);
    console.log(`🔗 Neo4j connection at: ${NEO4J_URI}`);
    console.log(`📊 Access VictoriaLogs at: ${VICTORIA_METRICS_URL}`);
    console.log(`🎨 Frontend should connect to: http://localhost:3001`);
    console.log(`🤖 MCP Tools available at /api/mcp/tools`);
    console.log(`⚡ MCP Tool execution at /api/mcp/execute`);
    console.log(`🧠 AI execution endpoint at /api/ai-execute`);

    console.log(`📊 Available VictoriaLogs Tools: query_logs, search_logs, get_log_metrics, get_log_stats`);
    console.log(`🔧 Available Manifest API Tools: get_changelogs, get_graph, get_incidents, get_notifications, get_resources, get_tickets`);

    // Test Neo4j connection on startup
    setTimeout(() => {
        testNeo4jConnection();
    }, 2000); // Wait 2 seconds for Neo4j to be ready
});

// Graceful shutdown
process.on('SIGINT', async () => {
    console.log('\n🛑 Shutting down gracefully...');
    if (neo4jDriver) {
        await neo4jDriver.close();
        console.log('✅ Neo4j driver closed');
    }
    process.exit(0);
});

process.on('SIGTERM', async () => {
    console.log('\n🛑 Shutting down gracefully...');
    if (neo4jDriver) {
        await neo4jDriver.close();
        console.log('✅ Neo4j driver closed');
    }
    process.exit(0);
});
