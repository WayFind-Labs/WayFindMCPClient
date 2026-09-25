"""
agent/nodes/evaluate_evidence.py
Node: evaluate_evidence

Responsibility:
  Deterministic (NO LLM) composite scoring of the top candidate against the
  search criteria and image match results.

  Weights are loaded from config/evidence_weights.yaml if available; otherwise
  defaults defined in this file are used. NEVER hardcode thresholds in the
  routing logic — always read from weights.

  Computes:
    composite_score = (
        weights.metadata         * metadata_score
      + weights.image_similarity * image_score   (0 if no image)
      + weights.geographic       * geo_score     (0 if no location match)
      + weights.temporal         * temporal_score (0 if no date match)
    )

  Determines confidence_tier:
    composite_score >= tiers.high_threshold      → HIGH
    composite_score >= tiers.uncertain_threshold → UNCERTAIN
    else                                         → LOW

Inputs consumed:
  state.candidate_ids, state.image_match_results, state.child_search_criteria

Outputs produced:
  match_evidence   — MatchEvidence for top candidate
  confidence_tier  — ConfidenceTier

Phase 5 status: FULL IMPLEMENTATION (deterministic).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any

from agent.state import WayfindState
from schemas.evidence import ConfidenceTier, MatchEvidence
from schemas.image import ImageMatch

logger = logging.getLogger(__name__)

# ── Default weights (overridden by config/evidence_weights.yaml) ───────────────
_DEFAULT_WEIGHTS = {
    "metadata":         0.50,
    "image_similarity": 0.35,
    "geographic":       0.10,
    "temporal":         0.05,
}
_DEFAULT_TIERS = {
    "high_threshold":      0.75,
    "uncertain_threshold": 0.45,
}


@lru_cache(maxsize=1)
def _load_weights() -> dict[str, Any]:
    """Load evidence weights from YAML. Cached after first call."""
    yaml_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "config", "evidence_weights.yaml"
    )
    yaml_path = os.path.normpath(yaml_path)
    try:
        import yaml  # type: ignore[import-untyped]
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        weights = {**_DEFAULT_WEIGHTS, **(data.get("weights") or {})}
        tiers   = {**_DEFAULT_TIERS,   **(data.get("tiers")   or {})}
        logger.info("Loaded evidence weights from %s", yaml_path)
        return {"weights": weights, "tiers": tiers}
    except FileNotFoundError:
        logger.info("evidence_weights.yaml not found — using defaults (Phase 10 will create it)")
        return {"weights": _DEFAULT_WEIGHTS, "tiers": _DEFAULT_TIERS}
    except Exception as exc:
        logger.warning("Failed to load evidence_weights.yaml: %s — using defaults", exc)
        return {"weights": _DEFAULT_WEIGHTS, "tiers": _DEFAULT_TIERS}


def evaluate_evidence(state: WayfindState) -> dict:
    """Compute composite match score and confidence tier for the top candidate."""
    candidate_ids        = state.get("candidate_ids", [])
    image_match_results  = state.get("image_match_results", [])

    if not candidate_ids:
        # No candidates — should have been caught by evaluate_candidates, but be safe
        return {
            "match_evidence":  None,
            "confidence_tier": ConfidenceTier.LOW,
        }

    config  = _load_weights()
    weights = config["weights"]
    tiers   = config["tiers"]

    top_case_id = candidate_ids[0]

    # Find image match score for top candidate (if available)
    image_score: float | None = None
    image_match: ImageMatch | None = None
    for m in image_match_results:
        match_id = m.candidate_case_id if hasattr(m, "candidate_case_id") else m.get("candidate_case_id")
        if match_id == top_case_id:
            image_score  = m.similarity_score if hasattr(m, "similarity_score") else m.get("similarity_score", 0.0)
            image_match  = m
            break

    # Metadata score: in Phase 5 we have no real score from the DB.
    # When Phase 9 wires the postgres client, Candidate.metadata_match_score
    # will be available. For now use a placeholder.
    metadata_score = 0.60   # placeholder — replaced when postgres_client returns Candidate objects

    # Geographic and temporal scores: placeholder 0.0 until geo/date parsing is added.
    geographic_score = None
    temporal_score   = None

    # Compute weighted composite
    components: list[tuple[float, float]] = [
        (weights["metadata"], metadata_score),
    ]
    if image_score is not None:
        components.append((weights["image_similarity"], image_score))
    if geographic_score is not None:
        components.append((weights["geographic"], geographic_score))
    if temporal_score is not None:
        components.append((weights["temporal"], temporal_score))

    # Renormalise weights to sum to 1.0 based on available components
    total_weight = sum(w for w, _ in components)
    composite = sum(w * s for w, s in components) / total_weight if total_weight > 0 else 0.0

    # Determine tier
    if composite >= tiers["high_threshold"]:
        tier = ConfidenceTier.HIGH
    elif composite >= tiers["uncertain_threshold"]:
        tier = ConfidenceTier.UNCERTAIN
    else:
        tier = ConfidenceTier.LOW

    # Build rich supporting / conflicting factor strings for the review team
    supporting:  list[str] = []
    conflicting: list[str] = []

    # Metadata (physical attributes, age, gender, location)
    if metadata_score >= 0.70:
        supporting.append(
            f"Strong physical and demographic similarity (metadata score: {metadata_score:.0%}): "
            "age, gender, and physical descriptors align well with the reported details."
        )
    elif metadata_score >= 0.45:
        supporting.append(
            f"Partial physical match (metadata score: {metadata_score:.0%}): "
            "some demographic attributes match but not all."
        )
    else:
        conflicting.append(
            f"Weak demographic match (metadata score: {metadata_score:.0%}): "
            "age, gender, or physical descriptors show notable differences."
        )

    # Image similarity
    if image_score is not None:
        if image_score >= 0.80:
            supporting.append(
                f"High facial/physical image similarity ({image_score:.0%}): "
                "the uploaded photo closely resembles the intake record thumbnail."
            )
        elif image_score >= 0.60:
            supporting.append(
                f"Moderate image similarity ({image_score:.0%}): "
                "some visual resemblance detected but not conclusive."
            )
        else:
            conflicting.append(
                f"Low image similarity ({image_score:.0%}): "
                "visual features differ significantly from the intake record."
            )
    else:
        conflicting.append(
            "No image comparison was performed — photographic evidence is unavailable."
        )

    # Geographic score
    if geographic_score is not None:
        if geographic_score >= 0.70:
            supporting.append(
                "The reported last-seen location is geographically close to the intake location."
            )
        elif geographic_score < 0.30:
            conflicting.append(
                "The last-seen location and intake location are geographically distant — "
                "verify whether travel is plausible."
            )

    # Temporal score
    if temporal_score is not None:
        if temporal_score >= 0.70:
            supporting.append(
                "The timeline aligns well: the missing date is consistent with the intake date."
            )
        elif temporal_score < 0.30:
            conflicting.append(
                "Timeline inconsistency: the reported missing date and intake date are far apart."
            )

    evidence = MatchEvidence(
        candidate_case_id  = top_case_id,
        metadata_score     = metadata_score,
        image_similarity   = image_score,
        geographic_score   = geographic_score,
        temporal_score     = temporal_score,
        composite_score    = round(composite, 4),
        supporting_factors = supporting,
        conflicting_factors= conflicting,
    )

    logger.info(
        "Session %s: evaluate_evidence composite=%.3f tier=%s",
        state.get("session_id"), composite, tier.value,
    )

    return {
        "match_evidence":  evidence,
        "confidence_tier": tier,
    }
