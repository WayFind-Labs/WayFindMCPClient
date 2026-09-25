"""
agent/nodes/search_support.py
Node: search_support_node

Responsibility:
  Finds nearby authorised child-intake shelters or support organisations
  via the search_support MCP tool, using the user's location.

  If no location is available: asks the user for their location instead of
  proceeding with an empty query.

Inputs consumed:
  state.user_location, state.user_prompt

Outputs produced:
  agent_events — search_results event (or assistant_message if no location)

Phase 5 status: STUB — returns placeholder results until MCP wired in Phase 6.
"""

from __future__ import annotations

import logging

from agent.dependencies import get_mcp_client
from agent.state import WayfindState
from schemas.location import Location

logger = logging.getLogger(__name__)

_NO_LOCATION_MSG = (
    "To find nearby shelters and support centres, I need to know your current "
    "location. Could you tell me which city or neighbourhood you are in?"
)
_NO_RESULTS_MSG = (
    "We could not find registered shelters near your location in our current "
    "database. Please contact local police or child-welfare authorities directly."
)


async def search_support_node(state: WayfindState) -> dict:
    """Search for nearby support organisations and emit results."""
    existing_events = state.get("agent_events", [])
    user_location   = state.get("user_location")

    # Attempt to extract location from prompt if not set
    if user_location is None:
        prompt = state.get("user_prompt", "").strip()
        if prompt:
            user_location = Location(label=prompt)

    if user_location is None:
        return {
            "agent_events": existing_events + [
                {"type": "assistant_message",   "content": _NO_LOCATION_MSG},
                {"type": "request_information", "fields": ["location"]},
            ]
        }

    mcp = get_mcp_client()

    if mcp is not None:
        try:
            result = await mcp.search_support(location=user_location, support_type=None)
            locations_data = [
                {"name": loc.name, "address": loc.address, "type": loc.support_type}
                for loc in (result.locations or [])
            ]
            if not locations_data:
                return {
                    "agent_events": existing_events + [
                        {"type": "assistant_message", "content": _NO_RESULTS_MSG}
                    ]
                }
            return {
                "agent_events": existing_events + [
                    {"type": "search_results", "results": locations_data}
                ]
            }
        except Exception as exc:
            logger.error("search_support_node MCP call failed: %s", exc)
            return {
                "agent_events": existing_events + [
                    {"type": "assistant_message", "content": _NO_RESULTS_MSG}
                ],
                "tool_failures": state.get("tool_failures", []) + ["search_support"],
                "errors":        state.get("errors", []) + [str(exc)],
            }

    # ── Phase 5 stub ──────────────────────────────────────────────────────────
    logger.info("Session %s: search_support_node STUB", state.get("session_id"))
    stub_results = [
        {"name": "Edhi Foundation", "address": "Near your location", "type": "ngo"},
        {"name": "Child Protection Bureau", "address": "Contact local office", "type": "government"},
    ]
    return {
        "agent_events": existing_events + [
            {"type": "search_results", "results": stub_results}
        ]
    }
