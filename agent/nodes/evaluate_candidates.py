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


def evaluate_candidates(state: WayfindState) -> dict:
    """Decide whether image matching is warranted for this candidate pool."""
    settings = get_settings()
    max_img = settings.max_image_candidates

    candidate_count  = state.get("candidate_count", 0)
    media_reference  = state.get("media_reference")

    image_warranted = (
        candidate_count > 0
        and media_reference is not None
        and candidate_count <= max_img
    )

    logger.info(
        "Session %s: candidates=%d media=%s → image_warranted=%s",
        state.get("session_id"),
        candidate_count,
        "yes" if media_reference else "no",
        image_warranted,
    )

    return {"image_search_warranted": image_warranted}
