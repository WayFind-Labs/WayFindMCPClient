"""
mcp_client/
Wayfind MCP Client package — manages LLM interactions and FastMCP tool calls.

Components:
  - WayfindLLM: Provider-agnostic LLM wrapper (Gemini / OpenAI / fallback)
    with strict Pydantic structured output.
  - WayfindMCPClient: Client connection to the FastMCP tool server with typed methods.
"""

from mcp_client.client import WayfindMCPClient
from mcp_client.llm import IntentResult, WayfindLLM

__all__ = [
    "WayfindLLM",
    "IntentResult",
    "WayfindMCPClient",
]
