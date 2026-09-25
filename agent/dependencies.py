"""
agent/dependencies.py
Shared runtime clients injected into LangGraph nodes.

This module holds module-level references to the LLM wrapper and MCP client.
Both are initialised to None at import time and wired up during application
startup (Phase 6 / Phase 11 lifespan hook).

Pattern:
  Nodes import get_llm() / get_mcp_client() and check for None.
  If None, they return a stub response (Phase 5 behaviour).
  Once wired (Phase 6+), the real clients are used.

Usage (from a node):
    from agent.dependencies import get_llm, get_mcp_client

    llm = get_llm()
    if llm is None:
        # return stub
"""

from __future__ import annotations

from typing import Any

# ── Module-level singletons (set by lifespan / Phase 11) ─────────────────────

_llm_client: Any | None = None
_mcp_client: Any | None = None


def get_llm() -> Any | None:
    """Return the WayfindLLM instance, or None if not yet initialised (Phase 5)."""
    return _llm_client


def get_mcp_client() -> Any | None:
    """Return the WayfindMCPClient instance, or None if not yet initialised (Phase 5)."""
    return _mcp_client


def set_llm(client: Any) -> None:
    """Wire the LLM client. Called once during lifespan startup (Phase 6)."""
    global _llm_client
    _llm_client = client


def set_mcp_client(client: Any) -> None:
    """Wire the MCP client. Called once during lifespan startup (Phase 6)."""
    global _mcp_client
    _mcp_client = client
