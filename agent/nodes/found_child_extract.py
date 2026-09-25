"""
agent/nodes/found_child_extract.py
Node: found_child_extract

Responsibility:
  Handles the FOUND_CHILD pipeline entry. Checks if the FoundChildReport has
  a valid found_location (the only required field). If not, loops back through
  ask_followup. If sufficient, proceeds to safety_guidance.

  In the graph this node does NOT directly call ask_followup — it sets
  missing_information and followup_question and returns, and check_completeness
  (which runs before route_intent) has already assessed completeness.

  For the FOUND_CHILD sub-pipeline, this node re-checks completeness inline
  because check_completeness only runs at the start of the turn (before routing).
  If found_location is missing after extract_structured_data, this node
  sets missing_information + followup_question so ask_followup can be invoked.

Inputs consumed:
  state.found_child_report, state.user_prompt

Outputs produced:
  found_child_report    — merged/updated
  missing_information   — set if found_location still missing
  followup_question     — set if incomplete
  agent_events          — appended if re-asking

Phase 5 status: FULL IMPLEMENTATION for completeness check;
  STUB for LLM extraction (delegates to extract_structured_data patterns).
"""

from __future__ import annotations

import logging

from agent.state import WayfindState
from schemas.child import FoundChildReport

logger = logging.getLogger(__name__)

_FOUND_LOCATION_QUESTION = (
    "Where exactly did you find the child? "
    "Please provide the neighbourhood, landmark, or street name."
)


async def found_child_extract(state: WayfindState) -> dict:
    """Check FoundChildReport completeness; set follow-up if found_location is missing."""
    report = state.get("found_child_report")

    # Coerce dict → model (may happen after Redis deserialisation)
    if isinstance(report, dict):
        report = FoundChildReport(**report)

    # Check required field
    has_location = (
        report is not None
        and report.found_location
        and report.found_location != "unknown"
    )

    if not has_location:
        logger.info(
            "Session %s: found_child_extract — found_location missing, asking follow-up",
            state.get("session_id"),
        )
        existing_events = state.get("agent_events", [])
        return {
            "found_child_report":  report or FoundChildReport(found_location="unknown"),
            "missing_information": ["found_location"],
            "followup_question":   _FOUND_LOCATION_QUESTION,
            "agent_events":        existing_events + [
                {"type": "assistant_message",   "content": _FOUND_LOCATION_QUESTION},
                {"type": "request_information", "fields": ["found_location"]},
            ],
        }

    # Location present — attach media_reference if available and not already set
    media_ref = state.get("media_reference")
    if media_ref and report and not report.media_reference:
        report = report.model_copy(update={"media_reference": media_ref})

    logger.info(
        "Session %s: found_child_extract — report complete, proceeding to safety_guidance",
        state.get("session_id"),
    )

    return {
        "found_child_report":  report,
        "missing_information": [],
        "followup_question":   None,
    }
