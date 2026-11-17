"""General guidance uses the same grounded conversation path as found-child help."""

from __future__ import annotations

from agent.nodes.safety_guidance import safety_guidance
from agent.state import WayfindState


async def get_guidance_node(state: WayfindState) -> dict:
    """Answer the current question using runtime knowledge and recent dialogue."""
    return await safety_guidance(state)
