"""
agent/nodes/no_match.py
Node: no_match

Responsibility:
  Produces a safe, empathetic no-match response when:
    - search_metadata returned 0 candidates, OR
    - evaluate_evidence scored the top candidate as LOW confidence

  Next steps are sourced from static_guidance.yaml when available,
  otherwise from hardcoded safe defaults.

  Safe language rules:
    - Never say "your child is not in our system" (implies absence of any record)
    - Always clarify the database covers only registered partner-shelter cases
    - Always provide actionable next steps

Inputs consumed:
  state.child_search_criteria (for context in message)

Outputs produced:
  final_response — no-match message text
  agent_events   — assistant_message event appended

Phase 5 status: FULL IMPLEMENTATION (no LLM / MCP needed).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from agent.state import WayfindState

logger = logging.getLogger(__name__)

_DEFAULT_MESSAGE = (
    "We searched our current records and did not find a child matching the "
    "information provided. This does not mean the child is absent from all "
    "records — our database covers only registered cases from partner shelters."
)

_DEFAULT_NEXT_STEPS = [
    "File a police report if you have not already done so.",
    "Contact local child-welfare organisations in your area.",
    "Submit a report through Wayfind so we can monitor for future matches.",
]


@lru_cache(maxsize=1)
def _load_no_match_content() -> tuple[str, list[str]]:
    """Load no-match message and next steps from static_guidance.yaml if available."""
    yaml_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "static_guidance.yaml")
    )
    try:
        import yaml  # type: ignore[import-untyped]
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        mc = data.get("missing_child", {})
        message    = mc.get("no_match_message", _DEFAULT_MESSAGE).strip()
        next_steps = mc.get("next_steps", _DEFAULT_NEXT_STEPS)
        return message, next_steps
    except FileNotFoundError:
        return _DEFAULT_MESSAGE, _DEFAULT_NEXT_STEPS
    except Exception as exc:
        logger.warning("Failed to load static_guidance.yaml: %s", exc)
        return _DEFAULT_MESSAGE, _DEFAULT_NEXT_STEPS


def no_match(state: WayfindState) -> dict:
    """Produce the no-match response with actionable next steps."""
    message, next_steps = _load_no_match_content()

    steps_text = "\n".join(f"• {s}" for s in next_steps)
    full_message = f"{message}\n\nWhat you can do next:\n{steps_text}"

    existing_events = state.get("agent_events", [])

    logger.info(
        "Session %s: no_match response generated",
        state.get("session_id"),
    )

    return {
        "final_response": full_message,
        "agent_events":   existing_events + [
            {"type": "assistant_message", "content": full_message}
        ],
    }
