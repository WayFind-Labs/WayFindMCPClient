"""
agent/nodes/route_by_confidence.py
Node: route_by_confidence

Responsibility:
  Pass-through node. Its sole purpose is to be a named graph node so the
  conditional edge (confidence_router, defined in agent/state.py) has a
  source to attach to.

  The actual routing decision is made by confidence_router:
    g.add_conditional_edges("route_by_confidence", confidence_router, {...})

  This node returns an empty dict — no state modifications.

Phase 5 status: FULL IMPLEMENTATION (pass-through).
"""

from __future__ import annotations

from agent.state import WayfindState


def route_by_confidence(state: WayfindState) -> dict:
    """Pass-through node for the confidence-tier conditional edge."""
    return {}
