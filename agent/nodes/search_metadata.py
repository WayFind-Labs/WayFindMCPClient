"""
agent/nodes/search_metadata.py
Node: search_metadata

Responsibility:
  Calls the search_child_records MCP tool with the accumulated
  ChildSearchCriteria. Stores the returned candidate pool (case IDs only).
  Emits a search_started event before calling the tool.

  On tool failure: appends to tool_failures and errors; emits an error event.
  The graph continues — subsequent nodes check tool_failures.

Inputs consumed:
  state.child_search_criteria

Outputs produced:
  candidate_ids   — list of case ID strings
  candidate_count — len(candidate_ids)
  agent_events    — search_started event (always), error event (on failure)
  tool_failures   — tool name appended on failure
  errors          — error detail appended on failure

Phase 5 status: STUB — returns empty candidate pool until MCP wired in Phase 6.
"""

from __future__ import annotations

import logging

from agent.dependencies import get_mcp_client
from agent.state import WayfindState
from schemas.child import ChildSearchCriteria

logger = logging.getLogger(__name__)

_TOOL_NAME = "search_child_records"
_UNAVAILABLE_MSG = (
    "Our records search is temporarily unavailable. "
    "Please try again in a few moments."
)


async def search_metadata(state: WayfindState) -> dict:
    """Search intake records by metadata and store the candidate pool."""
    existing_events = state.get("agent_events", [])
    events = existing_events + [{"type": "search_started"}]

    criteria = state.get("child_search_criteria")
    if criteria is None:
        logger.warning("Session %s: search_metadata called with no criteria", state.get("session_id"))
        return {
            "agent_events":     events,
            "candidate_ids":    [],
            "candidate_count":  0,
        }

    mcp = get_mcp_client()

    if mcp is not None:
        # ── Phase 6+ real implementation ──────────────────────────────────────
        try:
            if isinstance(criteria, dict):
                criteria = ChildSearchCriteria(**criteria)
            result = await mcp.search_child_records(criteria=criteria)
            candidate_ids = [c.case_id for c in result.candidates]
            logger.info(
                "Session %s: search_metadata found %d candidates (truncated=%s)",
                state.get("session_id"), result.total_candidates, result.truncated,
            )
            return {
                "agent_events":    events,
                "candidate_ids":   candidate_ids,
                "candidate_count": result.total_candidates,
            }
        except Exception as exc:
            logger.error("search_metadata MCP call failed: %s", exc)
            return {
                "agent_events":   events + [{"type": "error", "message": _UNAVAILABLE_MSG}],
                "candidate_ids":  [],
                "candidate_count": 0,
                "tool_failures":  state.get("tool_failures", []) + [_TOOL_NAME],
                "errors":         state.get("errors", []) + [str(exc)],
            }

    # ── Phase 5 stub ──────────────────────────────────────────────────────────
    logger.info("Session %s: search_metadata STUB — MCP not wired", state.get("session_id"))
    return {
        "agent_events":    events,
        "candidate_ids":   [],
        "candidate_count": 0,
    }
