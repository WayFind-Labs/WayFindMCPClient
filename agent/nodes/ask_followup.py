"""
agent/nodes/ask_followup.py
Node: ask_followup

Responsibility:
  Terminate the current graph run and return the follow-up question to the
  caller. Appends two agent events:
    1. assistant_message — the question text for the user
    2. request_information — the list of field names (for the frontend to
       optionally render a structured form instead of free text)

  Does NOT call any MCP tool or LLM.
  Does NOT advance the search or submission pipeline.
  Graph routes to END after this node — the session is saved, and the next
  user turn will resume the graph from the beginning.

Inputs consumed:
  state.followup_question, state.missing_information,
  state.conversation_history

Outputs produced:
  agent_events   — two events appended
  final_response — set to followup_question for legacy compatibility
  conversation_history — assistant turn appended

Phase 5 status: FULL IMPLEMENTATION.
"""

from __future__ import annotations

import logging

from agent.state import WayfindState

logger = logging.getLogger(__name__)

_FALLBACK_QUESTION = (
    "Could you please provide more information so I can help you better?"
)


def ask_followup(state: WayfindState) -> dict:
    """Emit a follow-up question and terminate the current graph run."""
    question = state.get("followup_question") or _FALLBACK_QUESTION
    missing  = state.get("missing_information", [])

    logger.info(
        "Session %s: ask_followup — missing=%s",
        state.get("session_id"), missing,
    )

    # Build new events (appended to existing agent_events)
    existing_events = state.get("agent_events", [])

    new_events = [
        {"type": "assistant_message", "content": question},
    ]
    if missing:
        new_events.append({"type": "request_information", "fields": missing})

    # Append assistant turn to conversation history
    updated_history = state.get("conversation_history", []) + [
        {"role": "assistant", "content": question}
    ]

    return {
        "agent_events":           existing_events + new_events,
        "final_response":         question,
        "conversation_history":   updated_history,
        "followup_question":      None,   # consumed — reset for next turn
    }
