"""
agent/nodes/image_match.py
Node: image_match

Responsibility:
  Calls the image_match_candidates MCP tool with the pre-filtered candidate
  pool and the media_id from ShelterAppUiBackend.

  IMPORTANT CONSTRAINTS (enforced in code):
    - candidate_case_ids MUST be non-empty (validated before call)
    - media_reference MUST be set (validated before call)
    - Never called against the full database — only against candidate_ids

  On failure: logs, sets flag, and lets the graph continue to evaluate_evidence
  with image_similarity=None (metadata-only scoring).

Inputs consumed:
  state.media_reference, state.candidate_ids

Outputs produced:
  image_match_results — list[ImageMatch]
  tool_failures       — appended on failure
  errors              — appended on failure

Phase 5 status: STUB — returns empty results until MCP wired in Phase 6.
"""

from __future__ import annotations

import logging

from agent.dependencies import get_mcp_client
from agent.state import WayfindState

logger = logging.getLogger(__name__)

_TOOL_NAME = "image_match_candidates"


async def image_match(state: WayfindState) -> dict:
    """Compare the uploaded image against the pre-filtered candidate pool."""
    media_reference = state.get("media_reference")
    candidate_ids   = state.get("candidate_ids", [])

    # Guard: should never reach here without both, but be defensive
    if not media_reference:
        logger.warning("Session %s: image_match called without media_reference", state.get("session_id"))
        return {"image_match_results": [], "image_search_warranted": False}

    if not candidate_ids:
        logger.warning("Session %s: image_match called with empty candidate_ids", state.get("session_id"))
        return {"image_match_results": [], "image_search_warranted": False}

    mcp = get_mcp_client()

    if mcp is not None:
        # ── Phase 6+ real implementation ──────────────────────────────────────
        try:
            result = await mcp.image_match_candidates(
                media_id=media_reference,
                candidate_case_ids=candidate_ids,
            )
            logger.info(
                "Session %s: image_match searched %d candidates",
                state.get("session_id"), result.candidates_searched,
            )
            return {"image_match_results": result.matches}
        except Exception as exc:
            logger.error("image_match MCP call failed: %s — continuing without image scores", exc)
            return {
                "image_match_results": [],
                "tool_failures": state.get("tool_failures", []) + [_TOOL_NAME],
                "errors":        state.get("errors", []) + [str(exc)],
            }

    # ── Phase 5 stub ──────────────────────────────────────────────────────────
    logger.info("Session %s: image_match STUB — MCP not wired", state.get("session_id"))
    return {"image_match_results": []}
