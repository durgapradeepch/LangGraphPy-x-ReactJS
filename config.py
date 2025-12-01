"""
Configuration settings for the LangGraph application
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# MCP Server Configuration
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:3001")
MCP_SERVER_ENABLED = os.getenv("MCP_SERVER_ENABLED", "true").lower() == "true"

# Application Settings
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# LangGraph Settings
LANGGRAPH_CHECKPOINT_ENABLED = True
LANGGRAPH_THREAD_ID = "default"

# Feature Flags
USE_ENHANCED_MODE = os.getenv("USE_ENHANCED_MODE", "true").lower() == "true"
ENABLE_MCP_TOOLS = os.getenv("ENABLE_MCP_TOOLS", "true").lower() == "true"

# Tool Execution Settings
MAX_TOOL_RETRIES = int(os.getenv("MAX_TOOL_RETRIES", "3"))
TOOL_TIMEOUT = int(os.getenv("TOOL_TIMEOUT", "60"))

# LLM Settings
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.0"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2000"))
