"""
tests/test_config.py
Tests for configuration files (Phase 10):
- config/evidence_weights.yaml
- config/static_guidance.yaml
"""

import os
import pytest
import yaml

from agent.nodes.evaluate_evidence import _load_weights, evaluate_evidence
from agent.nodes.no_match import _load_no_match_content, no_match
from mcp_server.tools.get_guidance import get_guidance
from schemas.evidence import ConfidenceTier


def test_evidence_weights_yaml_structure():
    """Verify evidence_weights.yaml exists and has required sections and valid weights."""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "evidence_weights.yaml"
    )
    config_path = os.path.normpath(config_path)
    assert os.path.exists(config_path), f"{config_path} must exist"

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "weights" in data
    weights = data["weights"]
    assert "metadata" in weights
    assert "image_similarity" in weights
    assert "geographic" in weights
    assert "temporal" in weights

    total_weight = sum(weights.values())
    assert pytest.approx(total_weight, 0.01) == 1.0

    assert "tiers" in data
    tiers = data["tiers"]
    assert "high_threshold" in tiers
    assert "uncertain_threshold" in tiers
    assert tiers["high_threshold"] > tiers["uncertain_threshold"]

    assert "candidate_pool" in data
    pool = data["candidate_pool"]
    assert pool["max_metadata_results"] == 50
    assert pool["max_image_candidates"] == 20


def test_static_guidance_yaml_structure():
    """Verify static_guidance.yaml exists and has all required topics and next steps."""
    config_path = os.path.join(
        os.path.dirname(__file__), "..", "config", "static_guidance.yaml"
    )
    config_path = os.path.normpath(config_path)
    assert os.path.exists(config_path), f"{config_path} must exist"

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "found_child" in data
    assert "guidance" in data["found_child"]
    assert "next_steps" in data["found_child"]
    assert len(data["found_child"]["next_steps"]) > 0

    assert "missing_child" in data
    assert "no_match_message" in data["missing_child"]
    assert "next_steps" in data["missing_child"]
    assert len(data["missing_child"]["next_steps"]) > 0


def test_evaluate_evidence_loads_config():
    """Verify evaluate_evidence node loads and uses evidence_weights.yaml."""
    _load_weights.cache_clear()
    weights_dict = _load_weights()
    assert weights_dict["weights"]["metadata"] == 0.50
    assert weights_dict["weights"]["image_similarity"] == 0.35
    assert weights_dict["tiers"]["high_threshold"] == 0.75

    state = {
        "session_id": "test-session",
        "candidate_ids": ["CASE-123"],
        "image_match_results": [],
    }
    result = evaluate_evidence(state)
    assert result["match_evidence"] is not None
    assert result["confidence_tier"] in (ConfidenceTier.HIGH, ConfidenceTier.UNCERTAIN, ConfidenceTier.LOW)


def test_no_match_loads_config():
    """Verify no_match node loads static_guidance.yaml."""
    _load_no_match_content.cache_clear()
    msg, steps = _load_no_match_content()
    assert "searched our current records" in msg
    assert len(steps) > 0

    state = {"session_id": "test-session", "agent_events": []}
    res = no_match(state)
    assert "final_response" in res
    assert len(res["agent_events"]) == 1


@pytest.mark.asyncio
async def test_get_guidance_tool_uses_static_yaml():
    """Verify get_guidance tool integrates with static_guidance.yaml."""
    res = await get_guidance(query="what to do", topic="found_child")
    assert res.topic == "found_child"
    assert "police" in res.guidance.lower()
    assert len(res.next_steps) > 0
