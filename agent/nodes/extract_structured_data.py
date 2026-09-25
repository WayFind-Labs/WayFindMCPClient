"""
agent/nodes/extract_structured_data.py
Node: extract_structured_data

Responsibility:
  Merge the user's latest message into the structured criteria/report being
  built incrementally across turns. Uses the LLM with structured output.

  For MISSING_CHILD: builds/merges ChildSearchCriteria
  For FOUND_CHILD:   builds/merges FoundChildReport

LLM discipline (enforced in the prompt — NOT by code validators):
  - NEVER invent values the user did not state
  - Leave fields None if user said nothing or "I don't know"
  - Set [] only if user explicitly said "none" for clothing/features
  - age.exact only for exact age; age.min/max for approximate
  - Do not reset fields already filled in previous turns

Inputs consumed:
  state.intent, state.user_prompt, state.child_search_criteria,
  state.found_child_report, state.last_form_data, state.media_reference

Outputs produced:
  child_search_criteria (for MISSING_CHILD)
  found_child_report    (for FOUND_CHILD)
  last_form_data        (reset to None after consumption)

Phase 5 status: STUB — returns unchanged criteria until LLM wired in Phase 6.
"""

from __future__ import annotations

import logging
from typing import Any

from agent.dependencies import get_llm
from agent.state import Intent, WayfindState
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport

logger = logging.getLogger(__name__)


async def extract_structured_data(state: WayfindState) -> dict:
    """Merge latest user turn into structured criteria or report."""
    intent = state.get("intent")
    llm = get_llm()

    if llm is not None:
        # ── Phase 6+ real implementation ──────────────────────────────────────
        try:
            if intent == Intent.MISSING_CHILD:
                result = await llm.extract_child_criteria(
                    existing_criteria=state.get("child_search_criteria"),
                    prompt=state["user_prompt"],
                    form_data=state.get("last_form_data"),
                )
                return {
                    "child_search_criteria": result,
                    "last_form_data": None,
                }
            elif intent == Intent.FOUND_CHILD:
                result = await llm.extract_found_child_report(
                    existing_report=state.get("found_child_report"),
                    prompt=state["user_prompt"],
                    form_data=state.get("last_form_data"),
                    media_reference=state.get("media_reference"),
                )
                return {
                    "found_child_report": result,
                    "last_form_data": None,
                }
        except Exception as exc:
            logger.error("extract_structured_data LLM call failed: %s", exc)
            return {
                "errors": state.get("errors", []) + [f"data extraction failed: {exc}"],
                "last_form_data": None,
            }
        return {"last_form_data": None}

    # ── Phase 5 stub ──────────────────────────────────────────────────────────
    # Attempt minimal keyword extraction so the pipeline is exercisable.
    # The LLM will do this properly in Phase 6.
    prompt = state.get("user_prompt", "").lower()
    updates: dict[str, Any] = {"last_form_data": None}

    if intent == Intent.MISSING_CHILD:
        existing = state.get("child_search_criteria") or ChildSearchCriteria(found_location="unknown")
        # Coerce to dict for merging
        criteria = _to_missing_criteria(existing)
        criteria = _heuristic_merge_missing(criteria, prompt, state.get("last_form_data"))
        updates["child_search_criteria"] = criteria

    elif intent == Intent.FOUND_CHILD:
        existing = state.get("found_child_report")
        report = _to_found_report(existing)
        report = _heuristic_merge_found(report, prompt, state.get("last_form_data"), state.get("media_reference"))
        updates["found_child_report"] = report

    return updates


# ── Stub helpers ───────────────────────────────────────────────────────────────

def _to_missing_criteria(existing: ChildSearchCriteria | None) -> ChildSearchCriteria:
    if existing is None:
        return ChildSearchCriteria()
    if isinstance(existing, dict):
        return ChildSearchCriteria(**existing)
    return existing


def _to_found_report(existing: FoundChildReport | None) -> FoundChildReport:
    if existing is None:
        return FoundChildReport(found_location="unknown")
    if isinstance(existing, dict):
        return FoundChildReport(**existing)
    return existing


def _heuristic_merge_missing(
    criteria: ChildSearchCriteria,
    prompt: str,
    form_data: dict | None,
) -> ChildSearchCriteria:
    """Very simple keyword merge for Phase 5. LLM replaces this in Phase 6."""
    data = form_data or {}

    # Gender
    if not criteria.gender:
        if "girl" in prompt or "daughter" in prompt or "female" in prompt:
            criteria = criteria.model_copy(update={"gender": "female"})
        elif "boy" in prompt or "son" in prompt or "male" in prompt:
            criteria = criteria.model_copy(update={"gender": "male"})

    # Age from form_data
    if "age" in data and not (criteria.age.exact or criteria.age.min):
        try:
            age_val = int(str(data["age"]).strip())
            criteria = criteria.model_copy(update={"age": AgeRange(exact=age_val)})
        except (ValueError, TypeError):
            pass

    # Location from form_data
    if "location" in data and not criteria.last_seen_location:
        criteria = criteria.model_copy(update={"last_seen_location": str(data["location"])})
    elif "last_seen_location" in data and not criteria.last_seen_location:
        criteria = criteria.model_copy(update={"last_seen_location": str(data["last_seen_location"])})

    return criteria


def _heuristic_merge_found(
    report: FoundChildReport,
    prompt: str,
    form_data: dict | None,
    media_reference: str | None,
) -> FoundChildReport:
    """Very simple keyword merge for Phase 5. LLM replaces this in Phase 6."""
    data = form_data or {}
    updates: dict[str, Any] = {}

    if not report.gender:
        if "girl" in prompt or "female" in prompt:
            updates["gender"] = "female"
        elif "boy" in prompt or "male" in prompt:
            updates["gender"] = "male"

    if report.found_location == "unknown" and "location" in data:
        updates["found_location"] = str(data["location"])

    if media_reference and not report.media_reference:
        updates["media_reference"] = media_reference

    return report.model_copy(update=updates) if updates else report
