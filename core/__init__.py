"""
Core module - State management, configuration, and logging
"""

from core.state import (
    ChatState,
    create_initial_state,
    update_state_context,
    add_mcp_result,
    calculate_state_health,
)
from core.config import (
    OPENAI_API_KEY,
    LLM_MODEL,
    MCP_SERVER_URL,
    MCP_SERVER_ENABLED,
    DEBUG,
    LOG_LEVEL,
    USE_ENHANCED_MODE,
    ENABLE_MCP_TOOLS,
    MAX_TOOL_RETRIES,
    TOOL_TIMEOUT,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)
from core.logger import logger, set_files_message_color

__all__ = [
    # State management
    "ChatState",
    "create_initial_state",
    "update_state_context",
    "add_mcp_result",
    "calculate_state_health",
    # Configuration
    "OPENAI_API_KEY",
    "LLM_MODEL",
    "MCP_SERVER_URL",
    "MCP_SERVER_ENABLED",
    "DEBUG",
    "LOG_LEVEL",
    "USE_ENHANCED_MODE",
    "ENABLE_MCP_TOOLS",
    "MAX_TOOL_RETRIES",
    "TOOL_TIMEOUT",
    "LLM_TEMPERATURE",
    "LLM_MAX_TOKENS",
    # Logging
    "logger",
    "set_files_message_color",
]
