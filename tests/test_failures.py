"""
tests/test_failures.py
Tests for Phase 14: Failure states, graceful degradation, and error isolation.

Verifies:
1. Downstream tool failures (metadata search, image matching, guidance, submission, support)
   gracefully degrade without crashing the agent graph.
2. Image match failure falls back to metadata-only composite scoring.
3. Review service submission failure falls back gracefully to a localized case reference.
4. FastAPI exception handling returns clean generic error messages with zero stack trace exposure.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from agent.dependencies import set_llm, set_mcp_client
from agent.nodes.evaluate_evidence import evaluate_evidence
from agent.nodes.human_review import human_review
from agent.nodes.image_match import image_match
from agent.nodes.search_metadata import search_metadata
from agent.nodes.submit_found_child import submit_found_child
from agent.runner import reset_graph, run_agent
from agent.state import Intent, initial_state
from app.main import create_app
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport
from schemas.evidence import ConfidenceTier, MatchEvidence

INTERNAL_KEY = "changeme-dev-secret"


@pytest.fixture(autouse=True)
def clean_deps():
    reset_graph()
    set_llm(None)
    set_mcp_client(None)
    yield
    reset_graph()
    set_llm(None)
    set_mcp_client(None)


@pytest.mark.asyncio
async def test_search_metadata_tool_failure_handling():
    """search_metadata tool failure logs tool_failure and emits safe error event."""
    mock_mcp = MagicMock()
    mock_mcp.search_child_records = AsyncMock(side_effect=RuntimeError("Database connection lost"))
    set_mcp_client(mock_mcp)

    state = initial_state("sess-fail-search")
    state["child_search_criteria"] = ChildSearchCriteria(
        gender="female",
        age=AgeRange(exact=6),
        last_seen_location="Gulberg",
    )

    result = await search_metadata(state)

    assert result["candidate_ids"] == []
    assert result["candidate_count"] == 0
    assert "search_child_records" in result["tool_failures"]
    assert any("Database connection lost" in err for err in result["errors"])

    event_types = [e["type"] for e in result["agent_events"]]
    assert "error" in event_types
    # Verify error message is safe for end user
    err_msg = [e["message"] for e in result["agent_events"] if e["type"] == "error"][0]
    assert "temporarily unavailable" in err_msg


@pytest.mark.asyncio
async def test_image_match_failure_gracefully_falls_back_to_metadata_scoring():
    """image_match tool failure continues to evaluate_evidence without image scores."""
    mock_mcp = MagicMock()
    mock_mcp.image_match_candidates = AsyncMock(side_effect=RuntimeError("Image service timeout"))
    set_mcp_client(mock_mcp)

    state = initial_state("sess-fail-img")
    state["candidate_ids"] = ["CASE-001"]
    state["media_reference"] = "media-abc"

    result = await image_match(state)

    assert result["image_match_results"] == []
    assert "image_match_candidates" in result["tool_failures"]

    # Graph proceeds to evaluate_evidence with empty image results
    state.update(result)
    eval_result = evaluate_evidence(state)
    assert eval_result["match_evidence"] is not None
    assert eval_result["match_evidence"].image_similarity is None
    assert eval_result["confidence_tier"] is not None


@pytest.mark.asyncio
async def test_submit_found_child_tool_failure_handling():
    """submit_found_child tool failure returns safe failure message and logs error."""
    mock_mcp = MagicMock()
    mock_mcp.submit_found_child_report = AsyncMock(side_effect=ConnectionError("Backend unreachable"))
    set_mcp_client(mock_mcp)

    state = initial_state("sess-fail-fc")
    state["found_child_report"] = FoundChildReport(found_location="Liberty Market")

    result = await submit_found_child(state)

    assert "submit_found_child_report" in result["tool_failures"]
    event_types = [e["type"] for e in result["agent_events"]]
    assert "error" in event_types
    err_msg = [e["message"] for e in result["agent_events"] if e["type"] == "error"][0]
    assert "unable to submit your report" in err_msg


@pytest.mark.asyncio
async def test_human_review_service_failure_falls_back_cleanly():
    """human_review handles downstream review service error with local case reference."""
    state = initial_state("sess-fail-rev")
    state["candidate_ids"] = ["CASE-123"]
    state["confidence_tier"] = ConfidenceTier.HIGH
    state["match_evidence"] = MatchEvidence(
        candidate_case_id="CASE-123",
        composite_score=0.85,
        metadata_score=0.9,
    )

    with patch("services.review_service.ReviewService.submit", side_effect=Exception("Review service 503")):
        result = await human_review(state)

    assert result["review_required"] is True
    assert result["case_reference"] is not None
    assert result["case_reference"].startswith("WF-REV-")
    event_types = [e["type"] for e in result["agent_events"]]
    assert "review_pending" in event_types


@pytest.mark.asyncio
async def test_fastapi_unhandled_exception_returns_safe_generic_response():
    """Any unhandled exception inside the internal API returns generic 500 JSON without stack trace."""
    app = create_app()

    # Force an unhandled exception inside graph execution
    with patch("agent.runner.run_agent", side_effect=Exception("Unexpected crash!")):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/internal/sessions/test-crash-sess/events",
                headers={"X-Internal-Key": INTERNAL_KEY},
                json={"event": {"type": "user_message", "content": "Crash me"}},
            )
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["type"] == "error"
            assert "Something went wrong" in data[0]["message"]
            # Ensure internal message is NOT exposed
            assert "Unexpected crash!" not in str(data)
