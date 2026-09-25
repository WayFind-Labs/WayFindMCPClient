"""
agent/nodes/route_intent.py
Node: route_intent

Responsibility:
  Pass-through node. Its sole purpose is to be a named graph node so the
  conditional edge (intent_router, defined in agent/state.py) has a source
  to attach to.

  The actual routing decision is made by intent_router in the conditional edge:
    g.add_conditional_edges("route_intent", intent_router, {...})

  This node returns an empty dict — no state modifications.

Phase 5 status: FULL IMPLEMENTATION (nothing to implement — pass-through).
"""

from __future__ import annotations

from agent.state import WayfindState


def route_intent(state: WayfindState) -> dict:
    """Pass-through node for the intent routing conditional edge."""
    return {}
