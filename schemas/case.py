"""
schemas/case.py
Return types for case-related MCP tool calls.

Security rules:
  - CaseStatusResult exposes ONLY public-safe fields.
  - No staff notes, no match scores, no candidate IDs, no internal state.
  - FoundChildSubmissionResult is returned to the submitter only — it contains
    a case_reference for tracking but no cross-referenced match data.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CaseStatusResult(BaseModel):
    """Public-facing status of a submitted Wayfind case.

    Returned by get_case_status.  Contains ONLY information safe to show
    to the general public — staff-only data is stripped at the service layer.
    """

    case_reference: str = Field(description="The opaque public case reference number.")
    status: str = Field(
        description=(
            "Current public status. "
            "Values: submitted | under_review | closed | no_match | matched_pending_verification"
        ),
    )
    submitted_at: str | None = Field(
        default=None,
        description="ISO 8601 datetime when the case was originally submitted.",
    )
    last_updated_at: str | None = Field(
        default=None,
        description="ISO 8601 datetime of the most recent status update.",
    )
    public_message: str | None = Field(
        default=None,
        description="Optional public message from the Wayfind team about this case.",
    )
    next_steps: list[str] = Field(
        default_factory=list,
        description="Recommended next steps for the user based on current status.",
    )


class FoundChildSubmissionResult(BaseModel):
    """Result returned after successfully submitting a found-child report.

    ``case_reference`` is the tracking number provided to the reporter.
    ``guidance`` and ``next_steps`` tell the reporter what to do now.
    """

    case_reference: str = Field(description="Unique public reference number for the submitted report.")
    submitted_at: str = Field(description="ISO 8601 datetime of submission.")
    guidance: str = Field(
        description="Immediate guidance for the reporter (e.g. stay with the child, contact police).",
    )
    next_steps: list[str] = Field(
        default_factory=list,
        description="Ordered list of recommended actions for the reporter.",
    )
    message: str | None = Field(
        default=None,
        description="Confirmation message to display to the user.",
    )
