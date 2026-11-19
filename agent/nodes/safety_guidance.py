"""Found-child guidance grounded in the packaged runtime knowledge document.

This node only emits guidance; it does not submit a report or notify anyone.
The graph still controls when it runs and delivers accumulated events.
"""

from __future__ import annotations

import logging

from agent.dependencies import get_llm
from agent.state import Intent, WayfindState
from mcp_client.conversation_context import INITIAL_FOUND_SAFETY, UNAVAILABLE_GUIDANCE

logger = logging.getLogger(__name__)


async def safety_guidance(state: WayfindState) -> dict:
    """Generate contextual guidance or disclose model unavailability."""
    if state.get("intent") == Intent.FOUND_CHILD:
        if state.get("found_safety_delivered"):
            return {}
        return {
            "agent_events": state.get("agent_events", []) + [
                {"type": "assistant_message", "content": INITIAL_FOUND_SAFETY}
            ],
            "found_safety_delivered": True,
        }
    guidance_text = UNAVAILABLE_GUIDANCE
    llm = get_llm()
    if llm is not None:
        try:
            text = await llm.generate_guidance_response(state)
            if isinstance(text, str) and text.strip():
                guidance_text = text.strip()
        except Exception:
            # Do not log raw prompts, locations, provider bodies or keys.
            logger.warning("Contextual guidance unavailable; returning static safety help")

    first_found_turn = state.get("intent") == Intent.FOUND_CHILD and not state.get("found_safety_delivered")
    events = state.get("agent_events", []) + (
        [{"type": "assistant_message", "content": INITIAL_FOUND_SAFETY}] if first_found_turn else []
    )
    events.append({"type": "assistant_message", "content": guidance_text})
    updates = {"agent_events": events}
    if first_found_turn:
        updates["found_safety_delivered"] = True
    return updates
