"""
schemas/image.py
Return types from the image_match_candidates MCP tool.

Security rules:
  - ``query_media_id`` is an internal backend ID — never a URL or path.
  - ``match_regions`` are model-generated descriptors, not raw image coordinates
    that could reconstruct biometric data.
  - Image matching is ONLY called against a pre-filtered candidate set
    (MAX_IMAGE_CANDIDATES limit). Never against the full database.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ImageMatch(BaseModel):
    """Result for a single candidate image comparison."""

    candidate_case_id: str = Field(description="Internal case ID of the compared candidate.")
    similarity_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Cosine or embedding similarity between query image and candidate thumbnail.",
    )
    model_version: str = Field(
        description="Identifier of the image embedding model used (e.g. 'facenet-v2', 'clip-vit-l14').",
    )
    match_regions: list[str] = Field(
        default_factory=list,
        description=(
            "Plain-English descriptors of matching facial / physical regions "
            "(e.g. 'facial structure', 'hair colour'). Never raw coordinates."
        ),
    )


class ImageMatchResult(BaseModel):
    """Aggregated results from a single image matching call."""

    matches: list[ImageMatch] = Field(
        description="All candidate comparisons, ordered by similarity_score descending.",
    )
    query_media_id: str = Field(
        description="Internal media ID of the uploaded query image. Never a raw URL.",
    )
    candidates_searched: int = Field(
        ge=0,
        description="Number of candidate thumbnails actually compared.",
    )
