"""
agent/nodes/generate_response.py
Node: generate_response

Responsibility:
  Final node before END in most pipeline branches. Ensures agent_events is
  non-empty and final_response is set.

  If agent_events already contains a meaningful response (set by earlier nodes
  like human_review, no_match, submit_found_child, etc.) this node is a no-op.

  If agent_events is empty but final_response is set (legacy fallback), wraps
  it into an assistant_message event.

  If both are empty: emits a safe generic error event.

  In Phase 6+: LLM can be used here to produce a final polished response when
  the pipeline completed without a specific message node.

  Safe language rules (always enforced):
    - Never confirm identity ("this is your child")
    - Never reveal match scores or internal case details
    - Always use empathetic, careful language

Phase 5 status: FULL IMPLEMENTATION (template-based; LLM upgrade in Phase 6).
"""

from __future__ import annotations

import logging

from agent.dependencies import get_llm
from agent.state import WayfindState

logger = logging.getLogger(__name__)

_FALLBACK_MSG = (
    "Thank you for using Wayfind. If you have any further questions or "
    "need to submit additional information, please feel free to continue."
)
_ERROR_MSG = "Something went wrong processing your request. Please try again."


async def generate_response(state: WayfindState) -> dict:
    """Ensure agent_events and final_response are populated before graph terminates."""
    existing_events = state.get("agent_events", [])
    final_response  = state.get("final_response")

    # Case 1: pipeline already produced events — nothing to do
    if existing_events:
        # Sync final_response with the last assistant_message for compatibility
        for evt in reversed(existing_events):
            if evt.get("type") == "assistant_message":
                return {
                    "agent_events":   existing_events,
                    "final_response": evt.get("content", final_response),
                }
        return {"agent_events": existing_events}

    # Case 2: final_response set but no events — wrap it
    if final_response:
        logger.info("Session %s: generate_response wrapping final_response into event", state.get("session_id"))
        return {
            "agent_events": [{"type": "assistant_message", "content": final_response}]
        }

    # Case 3: Phase 6+ LLM polishing (when no other node produced a response)
    llm = get_llm()
    if llm is not None:
        try:
            text = await llm.generate_final_response(state)
            return {
                "final_response": text,
                "agent_events": [{"type": "assistant_message", "content": text}],
            }
        except Exception as exc:
            logger.error("generate_response LLM call failed: %s", exc)

    # Case 4: complete fallback — emit a generic helpful message
    tool_failures = state.get("tool_failures", [])
    if tool_failures:
        msg = (
            "We encountered a technical issue while processing your request. "
            "Our team has been notified. Please try again in a moment."
        )
    else:
        msg = _FALLBACK_MSG

    logger.info(
        "Session %s: generate_response emitting fallback (tool_failures=%s)",
        state.get("session_id"), tool_failures,
    )

    return {
        "final_response": msg,
        "agent_events":   [{"type": "assistant_message", "content": msg}],
    }
