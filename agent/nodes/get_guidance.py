"""
agent/nodes/get_guidance.py
Node: get_guidance_node

Responsibility:
  Retrieves contextual guidance from the Wayfind knowledge base (RAG) via the
  get_guidance MCP tool. Falls back to static content if MCP unavailable.

Inputs consumed:
  state.user_prompt, state.intent

Outputs produced:
  agent_events — assistant_message with guidance text appended

Phase 5 status: STUB with static fallback — MCP wired in Phase 6.
"""

from __future__ import annotations

import logging

from agent.dependencies import get_mcp_client
from agent.state import WayfindState

logger = logging.getLogger(__name__)

_STATIC_GUIDANCE = (
    "Here is some general guidance:\n\n"
    "• If you have found an unaccompanied child, stay with them in a safe, "
    "public place and contact local police immediately.\n"
    "• If a child is missing, file a police report as soon as possible and "
    "submit a report through Wayfind so we can monitor our records.\n"
    "• Authorised shelters and NGOs are listed in our support directory — "
    "ask me to search for one near you."
)


async def get_guidance_node(state: WayfindState) -> dict:
    """Fetch guidance from RAG or static content and emit an assistant message."""
    existing_events = state.get("agent_events", [])
    query           = state.get("user_prompt", "")
    guidance_text   = _STATIC_GUIDANCE

    mcp = get_mcp_client()
    if mcp is not None:
        try:
            result = await mcp.get_guidance(query=query, topic=None)
            guidance_text = result.guidance_text
        except Exception as exc:
            logger.warning("get_guidance_node MCP call failed, using static: %s", exc)

    logger.info("Session %s: get_guidance_node returning guidance", state.get("session_id"))

    return {
        "agent_events": existing_events + [
            {"type": "assistant_message", "content": guidance_text}
        ]
    }
