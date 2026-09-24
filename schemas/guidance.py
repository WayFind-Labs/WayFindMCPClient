"""
schemas/guidance.py
Return types from the get_guidance MCP tool.

The tool queries the RAG knowledge base first; on failure it falls back
to static_guidance.yaml.  GuidanceResult.is_static_fallback signals which
path was used (for observability — never exposed to end users).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class GuidanceSource(BaseModel):
    """Metadata about a single knowledge-base document used to generate guidance."""

    title: str = Field(description="Title or identifier of the source document.")
    url: str | None = Field(
        default=None,
        description="Public URL of the source, if available.",
    )
    relevance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="RAG retrieval relevance score for this source.",
    )


class GuidanceResult(BaseModel):
    """Structured guidance returned by get_guidance.

    ``guidance`` is the primary answer text.
    ``next_steps`` is an ordered list of actionable steps.
    ``sources`` is populated only when the RAG backend was used.
    ``is_static_fallback`` is True when the RAG service was unavailable.
    """

    guidance: str = Field(
        description="Main guidance text to be included in the agent's response.",
    )
    next_steps: list[str] = Field(
        default_factory=list,
        description="Ordered list of recommended next steps for the user.",
    )
    topic: str | None = Field(
        default=None,
        description=(
            "Topic category of the guidance. "
            "Values: found_child | missing_child | shelter | safety | reporting | emergency"
        ),
    )
    sources: list[GuidanceSource] = Field(
        default_factory=list,
        description="Knowledge-base sources used. Empty when is_static_fallback is True.",
    )
    is_static_fallback: bool = Field(
        default=False,
        description="True when guidance came from static_guidance.yaml due to RAG failure.",
    )
