"""
agent/nodes/human_review.py
Node: human_review

Responsibility:
  Submits a candidate match — along with the full evidence package explaining
  WHY the agent believes it is a potential match — to the human-review queue.

  THE AI NEVER CONFIRMS A MATCH. It only submits evidence for staff to review.
  This applies to BOTH confidence tiers that reach this node:
    - UNCERTAIN (possible match):  standard-priority review
    - HIGH      (probable match):  priority review with strong evidence

  What is submitted to the review queue:
    - candidate_ids          — the pre-filtered candidate pool
    - match_evidence         — composite score + all component scores
    - supporting_factors     — plain-English reasons the agent suspects a match
    - conflicting_factors    — plain-English reasons for doubt
    - confidence_tier        — UNCERTAIN or HIGH
    - session_id             — for staff to pull full context if needed

  What the USER sees:
    - A confirmation that a "possible" or "probable" match was found
    - The case_reference for follow-up
    - A clear statement that STAFF will verify — the AI has NOT confirmed anything
    - The KEY reasons the agent flagged this (no raw scores — plain English only)

  What the USER never sees:
    - Candidate names, PII, case details
    - Internal confidence scores or thresholds
    - Any implication the child has been found or identified

Inputs consumed:
  state.candidate_ids, state.match_evidence, state.confidence_tier,
  state.session_id, state.child_search_criteria

Outputs produced:
  review_required — True
  case_reference  — reference ID from review service
  agent_events    — review_pending + assistant_message events appended

Phase 5 status: STUB with correct evidence package structure.
  Real review_service call is wired in Phase 9.
"""

from __future__ import annotations

import logging
from typing import Any

from agent.state import WayfindState
from schemas.evidence import ConfidenceTier, MatchEvidence

logger = logging.getLogger(__name__)

# ── Message templates ─────────────────────────────────────────────────────────
# "possible" for UNCERTAIN, "probable" for HIGH — never "confirmed"

_MSG_UNCERTAIN = (
    "We found a possible match in our records.\n\n"
    "Our system has detected some similarities and has submitted this case for "
    "staff review. A member of our team will carefully examine the details "
    "before taking any action.\n\n"
    "{reasons}"
    "Your reference number is {ref}. "
    "You can use this to check your case status at any time. "
    "Please do not take any independent action based on this — our team will "
    "contact you once the review is complete."
)

_MSG_HIGH = (
    "We found a probable match in our records with several strong indicators.\n\n"
    "This case has been submitted for PRIORITY staff review. Our team will "
    "examine all details carefully and will only act after thorough verification. "
    "Nothing is finalised until a staff member has reviewed and approved it.\n\n"
    "{reasons}"
    "Your reference number is {ref}. "
    "Please keep this safe — our team will follow up with you directly."
)

_REASONS_HEADER = "Key reasons our system flagged this:\n"


async def human_review(state: WayfindState) -> dict:
    """Build and submit a full evidence package for human review."""
    existing_events = state.get("agent_events", [])
    confidence_tier = state.get("confidence_tier")
    match_evidence  = state.get("match_evidence")
    candidate_ids   = state.get("candidate_ids", [])

    # ── Build the evidence package to submit ───────────────────────────────────
    evidence_package = _build_evidence_package(
        match_evidence=match_evidence,
        candidate_ids=candidate_ids,
        confidence_tier=confidence_tier,
        session_id=state.get("session_id", ""),
    )

    # ── Phase 9: wire review_service ──────────────────────────────────────────
    from services.review_service import get_review_service

    review_service = get_review_service()
    is_priority = (confidence_tier == ConfidenceTier.HIGH)
    case_reference: str | None = None
    state_errors = state.get("errors", [])
    state_failures = state.get("tool_failures", [])

    try:
        submission = await review_service.submit(
            candidate_case_ids=candidate_ids,
            evidence=match_evidence or MatchEvidence(candidate_case_id=""),
            session_id=state.get("session_id", ""),
            priority=is_priority,
            evidence_package=evidence_package,
        )
        case_reference = submission.case_reference
    except Exception as exc:
        import uuid
        logger.error("human_review service submission failed: %s — using local reference fallback", exc)
        case_reference = f"WF-REV-{uuid.uuid4().hex[:8].upper()}"
        state_errors = state_errors + [f"review_service failed: {exc}"]
        state_failures = state_failures + ["review_service"]

    logger.info(
        "Session %s: human_review submitted — tier=%s case_reference=%s evidence_factors=%d",
        state.get("session_id"),
        confidence_tier.value if confidence_tier else "unknown",
        case_reference,
        len(evidence_package.get("supporting_factors", [])),
    )

    # ── Build user-facing message ──────────────────────────────────────────────
    # Show supporting factors in plain English — NO scores, NO internal IDs
    supporting = evidence_package.get("supporting_factors", [])
    reasons_text = ""
    if supporting:
        bullet_points = "\n".join(f"  • {f}" for f in supporting[:4])  # cap at 4 bullets
        reasons_text  = f"{_REASONS_HEADER}{bullet_points}\n\n"

    is_high = (confidence_tier == ConfidenceTier.HIGH)
    template = _MSG_HIGH if is_high else _MSG_UNCERTAIN
    message  = template.format(ref=case_reference, reasons=reasons_text)

    return {
        "review_required": True,
        "case_reference":  case_reference,
        "agent_events":    existing_events + [
            {
                "type":           "review_pending",
                "case_reference": case_reference,
            },
            {
                "type":    "assistant_message",
                "content": message,
            },
        ],
    }


# ── Evidence package builder ───────────────────────────────────────────────────

def _build_evidence_package(
    match_evidence: MatchEvidence | dict | None,
    candidate_ids: list[str],
    confidence_tier: ConfidenceTier | None,
    session_id: str,
) -> dict[str, Any]:
    """Assemble the full evidence package for the review service.

    This is what staff see — includes scores, factors, and the candidate pool.
    NEVER returned to the user directly.
    """
    # Normalise MatchEvidence (may be a dict after Redis deserialisation)
    if isinstance(match_evidence, dict):
        try:
            match_evidence = MatchEvidence(**match_evidence)
        except Exception:
            match_evidence = None

    if match_evidence is None:
        return {
            "candidate_ids":      candidate_ids,
            "top_candidate_id":   candidate_ids[0] if candidate_ids else None,
            "composite_score":    None,
            "metadata_score":     None,
            "image_similarity":   None,
            "geographic_score":   None,
            "temporal_score":     None,
            "supporting_factors": [],
            "conflicting_factors":[],
            "confidence_tier":    confidence_tier.value if confidence_tier else "unknown",
            "session_id":         session_id,
            "note":               "No MatchEvidence available — metadata-only submission",
        }

    return {
        "candidate_ids":      candidate_ids,
        "top_candidate_id":   match_evidence.candidate_case_id,
        "composite_score":    match_evidence.composite_score,
        "metadata_score":     match_evidence.metadata_score,
        "image_similarity":   match_evidence.image_similarity,
        "geographic_score":   match_evidence.geographic_score,
        "temporal_score":     match_evidence.temporal_score,
        "supporting_factors": match_evidence.supporting_factors,
        "conflicting_factors":match_evidence.conflicting_factors,
        "confidence_tier":    confidence_tier.value if confidence_tier else "unknown",
        "session_id":         session_id,
    }
