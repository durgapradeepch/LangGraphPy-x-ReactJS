"""
MCP Client - Connects to Node.js MCP server with 45+ tools
Supports Neo4j, VictoriaLogs, VictoriaMetrics, and Manifest API
"""

import logging
import asyncio
import aiohttp
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Custom exception for MCP client errors"""
    pass


class MCPClient:
    """
    Client for executing MCP tools via Node.js server
    Connects to the MCP server running on localhost
    """
    
    def __init__(self, server_url: str = "http://localhost:8080"):
        self.server_url = server_url
        self.config = {
            "timeout": 60.0,  # Increased for real API calls
            "max_retries": 3,
            "retry_delay": 1.0
        }
        
        # Cache for available tools (fetched from server)
        self._tools_cache = None
        self._cache_time = None
        self._cache_ttl = 300  # 5 minutes
    
    async def _get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available MCP tools from Node.js server"""
        # Check cache
        if self._tools_cache and self._cache_time:
            if (datetime.now() - self._cache_time).total_seconds() < self._cache_ttl:
                return self._tools_cache
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}/api/mcp/tools",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        self._tools_cache = data.get("tools", [])
                        self._cache_time = datetime.now()
                        logger.info(f"✅ Fetched {len(self._tools_cache)} MCP tools from server")
                        return self._tools_cache
                    else:
                        logger.error(f"❌ Failed to fetch tools: HTTP {response.status}")
                        return self._get_fallback_tools()
        except Exception as e:
            logger.error(f"❌ Error fetching tools from server: {str(e)}")
            return self._get_fallback_tools()
    
    def _get_fallback_tools(self) -> List[Dict[str, Any]]:
        """Fallback tool list if server is unavailable"""
        return [
            {"name": "get_node_labels", "description": "Get Neo4j node labels"},
            {"name": "query_nodes", "description": "Query Neo4j nodes"},
            {"name": "search_nodes", "description": "Search Neo4j nodes"},
            {"name": "get_relationships", "description": "Get Neo4j relationships"},
            {"name": "query_logs", "description": "Query VictoriaLogs"},
            {"name": "search_logs", "description": "Search VictoriaLogs"},
            {"name": "query_metrics", "description": "Query VictoriaMetrics"},
            {"name": "instant_query_metrics", "description": "Instant query VictoriaMetrics"},
            {"name": "get_incidents", "description": "Get incidents from Manifest API"},
            {"name": "get_resources", "description": "Get resources from Manifest API"},
            {"name": "get_changelogs", "description": "Get changelogs from Manifest API"},
            {"name": "search_resources", "description": "Search resources"},
        ]
    
    def _convert_parameter_types(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parameter types based on tool requirements.
        Ensures integer IDs are integers, not strings.
        """
        # Define parameters that should be integers
        integer_params = {
            'resource_id', 'incident_id', 'changelog_id', 'ticket_id', 
            'notification_id', 'page', 'page_size', 'limit'
        }
        
        converted = {}
        for key, value in parameters.items():
            if key in integer_params and value is not None:
                try:
                    # Convert string numbers to integers
                    if isinstance(value, str) and value.isdigit():
                        converted[key] = int(value)
                    elif isinstance(value, (int, float)):
                        converted[key] = int(value)
                    else:
                        converted[key] = value
                except (ValueError, TypeError):
                    converted[key] = value
            else:
                converted[key] = value
        
        return converted
    
    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single MCP tool via Node.js server
        """
        try:
            # Convert parameter types
            parameters = self._convert_parameter_types(tool_name, parameters)
            
            logger.info(f"🔧 Executing MCP tool: {tool_name}")
            logger.info(f"🔧 Tool parameters: {json.dumps(parameters)}")
            
            # Execute with retry logic
            for attempt in range(self.config["max_retries"]):
                try:
                    result = await self._execute_tool_on_server(tool_name, parameters)
                    logger.info(f"✅ Tool {tool_name} executed successfully")
                    return result
                    
                except Exception as e:
                    if attempt < self.config["max_retries"] - 1:
                        logger.warning(f"⚠️ Tool {tool_name} attempt {attempt + 1} failed: {str(e)}, retrying...")
                        await asyncio.sleep(self.config["retry_delay"] * (attempt + 1))
                    else:
                        raise
            
        except Exception as e:
            logger.error(f"❌ Tool {tool_name} execution failed: {str(e)}")
            raise MCPClientError(f"Failed to execute tool {tool_name}: {str(e)}")
    
    async def _execute_tool_on_server(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool on Node.js MCP server"""
        
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "tool_name": tool_name,
                    "parameters": parameters
                }
                
                async with session.post(
                    f"{self.server_url}/api/mcp/execute",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=self.config["timeout"])
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        
                        # Add metadata
                        result = data.get("result", {})
                        
                        # DEBUG: Log result structure
                        if "incidents" in result:
                            logger.info(f"🔍 MCP DEBUG - Tool {tool_name} returned {len(result.get('incidents', []))} incidents")
                        
                        result["tool"] = tool_name
                        result["parameters"] = parameters
                        result["timestamp"] = datetime.now().isoformat()
                        result["success"] = data.get("success", True)
                        
                        return result
                    else:
                        error_text = await response.text()
                        raise MCPClientError(f"Server returned {response.status}: {error_text}")
                        
        except asyncio.TimeoutError:
            raise MCPClientError(f"Tool {tool_name} timed out after {self.config['timeout']}s")
        except aiohttp.ClientError as e:
            raise MCPClientError(f"Network error executing {tool_name}: {str(e)}")
    
    async def execute_multiple_tools(self, tool_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute multiple tools in parallel"""
        logger.info(f"🔧 Executing {len(tool_requests)} MCP tools in parallel")
        
        tasks = []
        for request in tool_requests:
            task = asyncio.create_task(
                self._execute_tool_with_error_handling(
                    request["name"],
                    request["parameters"]
                )
            )
            tasks.append((request["name"], task))
        
        results = []
        for tool_name, task in tasks:
            try:
                result = await task
                results.append({
                    "tool_name": tool_name,
                    "success": True,
                    "result": result
                })
            except Exception as e:
                logger.error(f"❌ Parallel execution failed for {tool_name}: {str(e)}")
                results.append({
                    "tool_name": tool_name,
                    "success": False,
                    "error": str(e)
                })
        
        return results
    
    async def _execute_tool_with_error_handling(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool with comprehensive error handling"""
        try:
            return await self.execute_tool(tool_name, parameters)
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "tool": tool_name
            }
    
    async def list_available_tools(self) -> Dict[str, Any]:
        """Get list of available MCP tools from the Node.js server"""
        try:
            logger.info("📋 Fetching available MCP tools")
            
            tools = await self._get_available_tools()
            
            return {
                "tools": tools,
                "count": len(tools)
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch tools list: {str(e)}")
            raise MCPClientError(f"Failed to fetch tools list: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """Check the health status of the MCP server"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.server_url}/health",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as response:
                    if response.status == 200:
                        return {
                            "status": "healthy",
                            "server_url": self.server_url,
                            "timestamp": datetime.now().isoformat()
                        }
                    else:
                        return {
                            "status": "unhealthy",
                            "server_url": self.server_url,
                            "error": f"HTTP {response.status}",
                            "timestamp": datetime.now().isoformat()
                        }
        except Exception as e:
            return {
                "status": "unreachable",
                "server_url": self.server_url,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }


class MCPClientManager:
    """Manager for MCP client instances"""
    
    def __init__(self, server_url: str = "http://localhost:8080"):
        self.server_url = server_url
        self.clients = {}
        self.connection_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "average_response_time": 0.0
        }
    
    async def get_client(self, session_id: str = "default") -> MCPClient:
        """Get or create MCP client for a session"""
        if session_id not in self.clients:
            client = MCPClient(server_url=self.server_url)
            self.clients[session_id] = client
            logger.info(f"✅ Created MCP client for session {session_id}")
        
        return self.clients[session_id]
    
    async def cleanup_session(self, session_id: str):
        """Cleanup MCP client for a session"""
        if session_id in self.clients:
            del self.clients[session_id]
            logger.info(f"🧹 Cleaned up MCP client for session {session_id}")
    
    async def cleanup_all_sessions(self):
        """Cleanup all MCP client sessions"""
        self.clients.clear()
        logger.info("🧹 Cleaned up all MCP client sessions")
