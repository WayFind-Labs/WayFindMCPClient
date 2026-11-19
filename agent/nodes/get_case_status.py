"""
agent/nodes/get_case_status.py
Node: get_case_status_node

Responsibility:
  Explain that public status lookup is deferred for the focused MVP.

Inputs consumed:
  none

Outputs produced:
  agent_events — assistant_message explaining the current limitation

Public case-status lookup is deferred for the focused MVP.
"""

from __future__ import annotations

from agent.state import WayfindState


async def get_case_status_node(state: WayfindState) -> dict:
    """Explain that public status lookup is unavailable for this MVP."""
    existing_events = state.get("agent_events", [])
    return {
        "agent_events": existing_events + [
            {"type": "assistant_message", "content": (
                "Wayfind cannot check report status in this MVP. "
                "A Wayfind reference confirms a recorded report, not an official case "
                "or active review. If you need an update or urgent help, contact "
                "the appropriate local authority directly."
            )}
        ]
    }
