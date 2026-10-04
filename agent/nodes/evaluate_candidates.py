"""
agent/nodes/evaluate_candidates.py
Node: evaluate_candidates

Responsibility:
  Deterministic routing decision after search_metadata returns a candidate pool.
  Sets image_search_warranted based on:
    - media_reference is not None  (image was uploaded by user)
    - candidate_count <= MAX_IMAGE_CANDIDATES  (pool small enough to scan)
    - any candidate has thumbnail_available = True  (checked via candidate_ids
      proxy — in Phase 5 always False since we have no candidate metadata)

  This is a pure computation node — no LLM, no MCP calls.
  The actual routing is done by candidate_router (conditional edge in graph.py).

Inputs consumed:
  state.candidate_count, state.media_reference, state.candidate_ids

Outputs produced:
  image_search_warranted — bool

Phase 5 status: FULL IMPLEMENTATION (deterministic).
"""

from __future__ import annotations

import logging

from agent.state import WayfindState
from app.config import get_settings

logger = logging.getLogger(__name__)

# Significance threshold for triggering biometric search (must have candidate match alignment)
SIGNIFICANT_MATCH_THRESHOLD = 0.50


def evaluate_candidates(state: WayfindState) -> dict:
    """Decide whether image matching is warranted for this candidate pool.
    
    Guardrail: Biometric matching is ONLY triggered when:
      1. An image is attached (media_reference is set)
      2. Candidate pool is small and pre-filtered (candidate_count <= MAX_IMAGE_CANDIDATES)
      3. There is a SIGNIFICANT initial match of metadata attributes (significance_score >= 0.60)
         to avoid unnecessary or ungrounded biometric scans.
    """
    settings = get_settings()
    max_img = settings.max_image_candidates

    candidate_count  = state.get("candidate_count", 0)
    media_reference  = state.get("media_reference")
    criteria         = state.get("child_search_criteria")

    # Compute deterministic metadata significance score from criteria completeness & attributes
    significance_score = _compute_significance_score(criteria, candidate_count)

    image_warranted = (
        candidate_count > 0
        and media_reference is not None
        and candidate_count <= max_img
        and significance_score >= SIGNIFICANT_MATCH_THRESHOLD
    )

    logger.info(
        "Session %s: candidates=%d media=%s significance=%.2f → image_warranted=%s",
        state.get("session_id"),
        candidate_count,
        "yes" if media_reference else "no",
        significance_score,
        image_warranted,
    )

    return {
        "image_search_warranted": image_warranted,
    }


def _compute_significance_score(criteria: Any, candidate_count: int) -> float:
    """Deterministic significance score calculation without LLM."""
    if candidate_count == 0:
        return 0.0

    score = 0.50  # Base significance for a non-empty pre-filtered candidate pool

    if criteria is not None:
        # Check criteria completeness
        has_age = getattr(criteria, "age", None) is not None
        has_gender = getattr(criteria, "gender", None) is not None
        has_location = getattr(criteria, "last_seen_location", None) is not None
        has_features = bool(getattr(criteria, "identifying_features", None))

        if has_gender:
            score += 0.15
        if has_age:
            score += 0.15
        if has_location:
            score += 0.10
        if has_features:
            score += 0.10

    return min(1.0, score)
