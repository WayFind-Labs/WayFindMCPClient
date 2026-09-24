"""
schemas/review.py
Models for internal human-review queue submissions.

This is NOT an MCP tool — the human_review LangGraph node calls
services/review_service.py directly (internal HTTP only).

The review submission includes:
  - The top candidate IDs being flagged for review
  - The full MatchEvidence record (scores + factors)
  - The session ID for traceability
  - The confidence tier that triggered the review
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from schemas.evidence import ConfidenceTier, MatchEvidence


class HumanReviewSubmission(BaseModel):
    """Record created when a match is submitted for human review.

    Returned by the review service after a successful queue submission.
    The ``review_id`` is used internally by staff — it is NOT the same as
    the ``case_reference`` shown to end users.
    """

    review_id: str = Field(description="Internal review queue ID. Never exposed to end users.")
    case_reference: str = Field(
        description="Public-facing case reference number returned to the end user.",
    )
    confidence_tier: ConfidenceTier = Field(
        description="The confidence tier that triggered this review (UNCERTAIN or HIGH).",
    )
    candidate_case_ids: list[str] = Field(
        description="Internal case IDs of candidates flagged for review.",
    )
    evidence: MatchEvidence = Field(
        description="Full evidence record for the top candidate.",
    )
    session_id: str = Field(
        description="Session ID of the user conversation that triggered this review.",
    )
    submitted_at: str = Field(
        description="ISO 8601 datetime of queue submission.",
    )
    estimated_review_hours: int | None = Field(
        default=None,
        ge=0,
        description="Estimated hours until a staff member reviews this case.",
    )
