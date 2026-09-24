"""
schemas/candidates.py
Return types from the search_child_records MCP tool.

Design rules:
  - No PII is returned. Only coarse metadata and internal case IDs.
  - thumbnail_available signals whether the image pipeline can be called.
  - The LangGraph evaluate_candidates node uses candidate_count and
    thumbnail_available to decide whether image matching is warranted.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    """Coarse metadata for a single candidate case from intake records.

    All fields except ``case_id`` and ``metadata_match_score`` are optional —
    the intake record may not have complete data.

    PII rules: No names, no contact details, no identifying narratives.
    """

    case_id: str = Field(description="Internal opaque case identifier.")
    age_at_intake: int | None = Field(
        default=None,
        ge=0,
        le=120,
        description="Age (in years) recorded at the time of intake.",
    )
    gender: str | None = Field(
        default=None,
        description='Gender recorded at intake. Values: "male" | "female" | "unknown".',
    )
    height_cm: float | None = Field(
        default=None,
        ge=0.0,
        le=300.0,
        description="Height in centimetres recorded at intake.",
    )
    hair_color: str | None = Field(default=None, description="Hair colour recorded at intake.")
    intake_location: str | None = Field(
        default=None,
        description="Name or region of the shelter/location where the child was taken in.",
    )
    intake_date: str | None = Field(
        default=None,
        description="ISO 8601 date (YYYY-MM-DD) of intake.",
    )
    metadata_match_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Coarse match score returned by the PostgreSQL search service.",
    )
    thumbnail_available: bool = Field(
        description="Whether a photo is available for image-match comparison.",
    )


class CandidateSearchResult(BaseModel):
    """Aggregated result from search_child_records.

    ``truncated`` is True when the backend returned more results than
    MAX_CANDIDATE_POOL — the agent must note this in its evaluation.
    """

    candidates: list[Candidate] = Field(description="Ordered list of candidate records (best match first).")
    total_candidates: int = Field(
        ge=0,
        description="Total number of records matching the criteria before pool cap.",
    )
    search_summary: str = Field(
        description="Human-readable summary of the search parameters used (for audit/logging).",
    )
    truncated: bool = Field(
        description="True if total_candidates exceeded MAX_CANDIDATE_POOL and results were capped.",
    )
