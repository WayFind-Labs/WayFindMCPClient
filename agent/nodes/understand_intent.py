"""
agent/nodes/understand_intent.py
Node: understand_intent

Responsibility:
  Determines the user's high-level intent from their message and conversation
  history. Uses the LLM with structured output to return a typed Intent value
  and a confidence score.

Inputs consumed:
  state.user_prompt, state.conversation_history

Outputs produced:
  intent, intent_confidence
  case_reference (if CASE_STATUS intent detected — extracted from prompt)

LLM behaviour:
  - Returns Intent enum value + float confidence
  - If intent is CASE_STATUS: also extracts case_reference string from prompt
  - If confidence < 0.4 or intent cannot be determined: returns UNKNOWN

Phase 5 status: STUB — returns UNKNOWN until LLM is wired in Phase 6.
"""

from __future__ import annotations

import logging
import re

from agent.dependencies import get_llm
from agent.state import Intent, WayfindState

logger = logging.getLogger(__name__)

# Simple pattern to extract a case reference like "WF-20260925-0042" from text
_CASE_REF_PATTERN = re.compile(r"\bWF-\d{8}-\d{4}\b", re.IGNORECASE)


async def understand_intent(state: WayfindState) -> dict:
    """Detect intent from the current turn's user prompt.

    Phase 6: Replace stub body with:
        llm = get_llm()
        result = await llm.extract_intent(
            conversation_history=state["conversation_history"],
            prompt=state["user_prompt"],
        )
        return {
            "intent": result.intent,
            "intent_confidence": result.confidence,
            "case_reference": result.case_reference,
        }
    """
    llm = get_llm()

    if llm is not None:
        # ── Phase 6+ real implementation ──────────────────────────────────────
        try:
            result = await llm.extract_intent(
                conversation_history=state["conversation_history"],
                prompt=state["user_prompt"],
            )
            updates: dict = {
                "intent": result.intent,
                "intent_confidence": result.confidence,
            }
            if result.intent == Intent.CASE_STATUS and result.case_reference:
                updates["case_reference"] = result.case_reference
            return updates
        except Exception as exc:
            logger.error("understand_intent LLM call failed: %s", exc)
            return {
                "intent": Intent.UNKNOWN,
                "intent_confidence": 0.0,
                "errors": state.get("errors", []) + [f"intent detection failed: {exc}"],
            }

    # ── Phase 5 stub ──────────────────────────────────────────────────────────
    # Heuristic keyword matching — intentionally simple, will be replaced by LLM.
    prompt_lower = state.get("user_prompt", "").lower()
    history = state.get("conversation_history", [])
    all_text = prompt_lower + " ".join(
        m.get("content", "").lower() for m in history if m.get("role") == "user"
    )

    # Detect case reference for CASE_STATUS
    case_match = _CASE_REF_PATTERN.search(state.get("user_prompt", ""))

    if case_match:
        intent = Intent.CASE_STATUS
        confidence = 0.85
    elif any(w in all_text for w in ["found", "found a child", "found a boy", "found a girl", "unaccompanied"]):
        intent = Intent.FOUND_CHILD
        confidence = 0.70
    elif any(w in all_text for w in ["missing", "lost", "looking for", "searching for", "my son", "my daughter", "my child"]):
        intent = Intent.MISSING_CHILD
        confidence = 0.70
    elif any(w in all_text for w in ["shelter", "ngo", "police station", "hospital", "where can i take"]):
        intent = Intent.SHELTER_SEARCH
        confidence = 0.70
    elif any(w in all_text for w in ["what should i do", "how do i", "guide", "help me understand", "procedure"]):
        intent = Intent.GUIDANCE
        confidence = 0.65
    else:
        intent = Intent.UNKNOWN
        confidence = 0.0

    logger.info(
        "Session %s: intent=%s (confidence=%.2f) [STUB — Phase 5]",
        state.get("session_id"),
        intent.value,
        confidence,
    )

    updates = {
        "intent": intent,
        "intent_confidence": confidence,
    }
    if intent == Intent.CASE_STATUS and case_match:
        updates["case_reference"] = case_match.group(0)

    return updates
