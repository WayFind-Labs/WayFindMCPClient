"""
agent/nodes/safety_guidance.py
Node: safety_guidance

Responsibility:
  Retrieves safety guidance for the person who found the child, before the
  report is submitted. Calls the get_guidance MCP tool with topic="found_child".

  Guidance is added to agent_events as an assistant_message BEFORE the
  submission event, so the user sees what to do while the report is being filed.

  Falls back to static_guidance.yaml content if MCP is unavailable.

Inputs consumed:
  state.user_prompt (for context in the guidance query)

Outputs produced:
  agent_events — assistant_message event with guidance text appended

Phase 5 status: STUB with static fallback — real MCP call wired in Phase 6.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from agent.dependencies import get_mcp_client
from agent.state import WayfindState

logger = logging.getLogger(__name__)

_STATIC_GUIDANCE = (
    "While we process your report, please:\n"
    "• Do not leave the child unattended.\n"
    "• Stay in a safe, public location.\n"
    "• Contact local police if you have not already done so.\n"
    "• Do not share the child's photo or details on social media."
)


@lru_cache(maxsize=1)
def _static_found_guidance() -> str:
    yaml_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "static_guidance.yaml")
    )
    try:
        import yaml  # type: ignore[import-untyped]
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data.get("found_child", {}).get("guidance", _STATIC_GUIDANCE).strip()
    except Exception:
        return _STATIC_GUIDANCE


async def safety_guidance(state: WayfindState) -> dict:
    """Fetch and emit safety guidance before submitting the found-child report."""
    existing_events = state.get("agent_events", [])
    guidance_text   = _static_found_guidance()   # fallback

    mcp = get_mcp_client()
    if mcp is not None:
        try:
            result = await mcp.get_guidance(
                query=state.get("user_prompt", "found a child"),
                topic="found_child",
            )
            guidance_text = result.guidance
        except Exception as exc:
            logger.warning("safety_guidance MCP call failed, using static: %s", exc)

    return {
        "agent_events": existing_events + [
            {"type": "assistant_message", "content": guidance_text}
        ]
    }
