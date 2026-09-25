"""
agent/runner.py
LangGraph graph runner and execution lifecycle.

Manages the compiled StateGraph singleton and provides the async execution entrypoint
used by the FastAPI internal agent endpoint.
"""

from __future__ import annotations

import logging
from typing import Any

from langgraph.graph.state import CompiledStateGraph

from agent.graph import build_graph
from agent.state import WayfindState

logger = logging.getLogger(__name__)

_graph: CompiledStateGraph | None = None


def get_graph() -> CompiledStateGraph:
    """Retrieve or build the singleton compiled LangGraph instance."""
    global _graph
    if _graph is None:
        logger.info("Compiling Wayfind LangGraph instance...")
        _graph = build_graph()
    return _graph


def reset_graph() -> None:
    """Clear the cached compiled graph singleton (useful for testing)."""
    global _graph
    _graph = None


async def run_agent(state: WayfindState | dict[str, Any]) -> dict[str, Any]:
    """Execute one turn of the Wayfind agent workflow.

    Args:
        state: The current session's WayfindState dict or TypedDict.

    Returns:
        The resulting updated WayfindState dict after running the graph.
    """
    graph = get_graph()
    session_id = state.get("session_id", "unknown")
    logger.info("Executing LangGraph turn for session: %s", session_id)

    result = await graph.ainvoke(state)
    return result
