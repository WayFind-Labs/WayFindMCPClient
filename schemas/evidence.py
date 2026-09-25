"""
schemas/evidence.py
Models for match scoring and confidence classification.

Weights are loaded at runtime from config/evidence_weights.yaml.
Thresholds are NEVER hardcoded in Python.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ConfidenceTier(StrEnum):
    """Three-tier classification of match confidence.

    LOW      — below uncertain_threshold → generate no-match response
    UNCERTAIN — above uncertain_threshold but below high_threshold → human review
    HIGH     — above high_threshold → human review (priority)
    """

    LOW = "low"
    UNCERTAIN = "uncertain"
    HIGH = "high"


class MatchEvidence(BaseModel):
    """Structured evidence record for a single candidate match.

    Computed by the ``evaluate_evidence`` LangGraph node (deterministic — no LLM).
    All scores are normalised to 0.0–1.0.

    ``supporting_factors`` and ``conflicting_factors`` are plain-English strings
    for use in the human-review submission and audit log only — never exposed
    to the end user verbatim.
    """

    candidate_case_id: str = Field(description="Internal case ID of the matched candidate.")
    metadata_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Weighted metadata similarity score (age, gender, location, time, physical).",
    )
    image_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Cosine or embedding similarity from image matching. None if not performed.",
    )
    geographic_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Normalised proximity score between search location and intake location.",
    )
    temporal_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Normalised recency/time-alignment score between missing date and intake date.",
    )
    composite_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description=(
            "Weighted composite of all component scores using evidence_weights.yaml. "
            "Computed after all components are available."
        ),
    )
    supporting_factors: list[str] = Field(
        default_factory=list,
        description="Plain-English factors that increase match confidence.",
    )
    conflicting_factors: list[str] = Field(
        default_factory=list,
        description="Plain-English factors that reduce match confidence.",
    )
