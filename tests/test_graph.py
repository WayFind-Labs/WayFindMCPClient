"""
tests/test_graph.py
Comprehensive integration tests for the compiled LangGraph workflow (Phase 11).

Tests the StateGraph topology, node transitions, conditional routing logic,
and full workflow execution for all supported intent pipelines.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langgraph.graph.state import CompiledStateGraph

from agent.dependencies import set_llm, set_mcp_client
from agent.graph import build_graph
from agent.runner import get_graph, reset_graph, run_agent
from agent.state import Intent, WayfindState, initial_state
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport
from schemas.evidence import ConfidenceTier, MatchEvidence
from schemas.image import ImageMatch


@pytest.fixture(autouse=True)
def clean_graph_and_deps():
    """Ensure graph singleton and dependencies are reset before and after each test."""
    reset_graph()
    set_llm(None)
    set_mcp_client(None)
    yield
    reset_graph()
    set_llm(None)
    set_mcp_client(None)


def test_build_graph_structure():
    """Verify that build_graph compiles cleanly and registers all required nodes."""
    graph = build_graph()
    assert isinstance(graph, CompiledStateGraph)

    expected_nodes = [
        "understand_intent",
        "extract_structured_data",
        "check_completeness",
        "ask_followup",
        "route_intent",
        "search_metadata",
        "evaluate_candidates",
        "image_match",
        "evaluate_evidence",
        "route_by_confidence",
        "human_review",
        "no_match",
        "found_child_extract",
        "safety_guidance",
        "submit_found_child",
        "search_support_node",
        "get_guidance_node",
        "get_case_status_node",
        "generate_response",
    ]
    for node in expected_nodes:
        assert node in graph.nodes


def test_runner_singleton_caching():
    """Verify get_graph returns a singleton and reset_graph clears it."""
    g1 = get_graph()
    g2 = get_graph()
    assert g1 is g2

    reset_graph()
    g3 = get_graph()
    assert g3 is not g1


@pytest.mark.asyncio
async def test_graph_missing_child_incomplete_stops_at_followup():
    """Missing child with insufficient information triggers completeness check and stops at ask_followup."""
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.MISSING_CHILD, confidence=0.95)
    )
    mock_llm.extract_child_criteria = AsyncMock(
        return_value=ChildSearchCriteria(gender="female")  # missing age and location
    )
    mock_llm.generate_followup_question = AsyncMock(
        return_value="How old is she and where was she last seen?"
    )
    set_llm(mock_llm)

    state = initial_state("sess-incomplete-1")
    state["user_prompt"] = "My daughter is missing"

    result = await run_agent(state)

    assert result["intent"] == Intent.MISSING_CHILD
    assert "age" in result["missing_information"]
    assert "last_seen_location" in result["missing_information"]
    assert len(result["agent_events"]) >= 1

    event_types = [e["type"] for e in result["agent_events"]]
    assert "assistant_message" in event_types
    assert "request_information" in event_types


@pytest.mark.asyncio
async def test_graph_missing_child_happy_path_human_review():
    """Missing child with complete info and candidate match flows through search -> review -> generate_response."""
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.MISSING_CHILD, confidence=0.95)
    )
    mock_llm.extract_child_criteria = AsyncMock(
        return_value=ChildSearchCriteria(
            gender="male",
            age=AgeRange(exact=8),
            last_seen_location="Gulberg",
        )
    )
    mock_llm.generate_final_response = AsyncMock(
        return_value="We found potential record matches and submitted them for verification."
    )
    set_llm(mock_llm)

    mock_mcp = MagicMock()
    mock_mcp.search_child_records = AsyncMock(
        return_value=MagicMock(
            candidates=[MagicMock(case_id="CASE-GULBERG-001")],
            total_candidates=1,
            truncated=False,
        )
    )
    set_mcp_client(mock_mcp)

    state = initial_state("sess-mc-happy")
    state["user_prompt"] = "Looking for an 8 year old boy lost in Gulberg"

    result = await run_agent(state)

    assert result["intent"] == Intent.MISSING_CHILD
    assert len(result["missing_information"]) == 0
    assert result["candidate_count"] == 1
    assert result["candidate_ids"] == ["CASE-GULBERG-001"]
    assert result["review_required"] is True
    assert result["confidence_tier"] in (ConfidenceTier.HIGH, ConfidenceTier.UNCERTAIN)

    event_types = [e["type"] for e in result["agent_events"]]
    assert "search_started" in event_types
    assert "review_pending" in event_types


@pytest.mark.asyncio
async def test_graph_missing_child_no_candidates_routes_to_no_match():
    """Missing child with complete info but 0 candidates routes to no_match."""
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.MISSING_CHILD, confidence=0.95)
    )
    mock_llm.extract_child_criteria = AsyncMock(
        return_value=ChildSearchCriteria(
            gender="female",
            age=AgeRange(exact=6),
            last_seen_location="DHA Phase 5",
        )
    )
    set_llm(mock_llm)

    mock_mcp = MagicMock()
    mock_mcp.search_child_records = AsyncMock(
        return_value=MagicMock(candidates=[], total_candidates=0, truncated=False)
    )
    set_mcp_client(mock_mcp)

    state = initial_state("sess-mc-nomatch")
    state["user_prompt"] = "My 6yo daughter went missing in DHA Phase 5"

    result = await run_agent(state)

    assert result["intent"] == Intent.MISSING_CHILD
    assert result["candidate_count"] == 0
    assert result["review_required"] is False

    event_types = [e["type"] for e in result["agent_events"]]
    assert "search_started" in event_types
    assert "assistant_message" in event_types
    msg = [e["content"] for e in result["agent_events"] if e["type"] == "assistant_message"][0]
    assert "searched our current records" in msg.lower() or "not find" in msg.lower()


@pytest.mark.asyncio
async def test_graph_missing_child_with_image_runs_image_match():
    """When media_reference is present and candidate_count <= MAX_IMAGE_CANDIDATES, image_match runs."""
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.MISSING_CHILD, confidence=0.95)
    )
    mock_llm.extract_child_criteria = AsyncMock(
        return_value=ChildSearchCriteria(
            gender="female",
            age=AgeRange(exact=10),
            last_seen_location="Model Town",
        )
    )
    set_llm(mock_llm)

    mock_mcp = MagicMock()
    mock_mcp.search_child_records = AsyncMock(
        return_value=MagicMock(
            candidates=[MagicMock(case_id="CASE-MT-01")],
            total_candidates=1,
            truncated=False,
        )
    )
    mock_mcp.image_match_candidates = AsyncMock(
        return_value=MagicMock(
            matches=[
                ImageMatch(
                    candidate_case_id="CASE-MT-01",
                    similarity_score=0.92,
                    confidence="high",
                    matched_features=["face"],
                    model_version="1.0",
                )
            ]
        )
    )
    set_mcp_client(mock_mcp)

    state = initial_state("sess-mc-image")
    state["user_prompt"] = "10yo girl lost near Model Town"
    state["media_reference"] = "media-uuid-999"

    result = await run_agent(state)

    assert result["image_search_warranted"] is True
    assert len(result["image_match_results"]) > 0
    assert result["image_match_results"][0].similarity_score == 0.92
    assert result["review_required"] is True


@pytest.mark.asyncio
async def test_graph_found_child_pipeline():
    """Found child intent extracts report, gets safety guidance, and submits found child report."""
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.FOUND_CHILD, confidence=0.98)
    )
    mock_llm.extract_found_child_report = AsyncMock(
        return_value=FoundChildReport(
            found_location="Liberty Market",
            approx_age=AgeRange(exact=5),
            gender="male",
        )
    )
    set_llm(mock_llm)

    mock_mcp = MagicMock()
    mock_mcp.get_guidance = AsyncMock(
        return_value=MagicMock(
            guidance="Stay in a safe public location and call emergency services.",
            next_steps=["Contact police"],
            topic="found_child",
        )
    )
    mock_mcp.submit_found_child_report = AsyncMock(
        return_value=MagicMock(case_reference="WF-FOUND-2026-0001", next_steps=["Wait for police"])
    )
    set_mcp_client(mock_mcp)

    state = initial_state("sess-fc-1")
    state["user_prompt"] = "I found a lost boy around 5 at Liberty Market"

    result = await run_agent(state)

    assert result["intent"] == Intent.FOUND_CHILD
    assert result["case_reference"] == "WF-FOUND-2026-0001"

    event_types = [e["type"] for e in result["agent_events"]]
    assert "submission_complete" in event_types


@pytest.mark.asyncio
async def test_graph_shelter_search_pipeline():
    """Shelter search intent calls search_support tool and produces search_results event."""
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.SHELTER_SEARCH, confidence=0.9)
    )
    set_llm(mock_llm)

    mock_mcp = MagicMock()
    mock_mcp.search_support = AsyncMock(
        return_value=MagicMock(
            locations=[
                MagicMock(
                    name="Child Protection Bureau Shelter",
                    address="Ferozepur Road",
                    support_type="shelter",
                )
            ],
            total_locations=1,
        )
    )
    set_mcp_client(mock_mcp)

    state = initial_state("sess-shelter-1")
    state["user_prompt"] = "Where is the nearest shelter in Lahore?"

    result = await run_agent(state)

    assert result["intent"] == Intent.SHELTER_SEARCH
    event_types = [e["type"] for e in result["agent_events"]]
    assert "search_results" in event_types


@pytest.mark.asyncio
async def test_graph_guidance_pipeline():
    """Guidance intent retrieves knowledge base guidance."""
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.GUIDANCE, confidence=0.9)
    )
    set_llm(mock_llm)

    mock_mcp = MagicMock()
    mock_mcp.get_guidance = AsyncMock(
        return_value=MagicMock(
            guidance="Follow emergency protocol: file an immediate police report.",
            next_steps=["Go to police station"],
            topic="missing_child",
        )
    )
    set_mcp_client(mock_mcp)

    state = initial_state("sess-guidance-1")
    state["user_prompt"] = "What should I do if my child goes missing?"

    result = await run_agent(state)

    assert result["intent"] == Intent.GUIDANCE
    event_types = [e["type"] for e in result["agent_events"]]
    assert "assistant_message" in event_types


@pytest.mark.asyncio
async def test_graph_case_status_pipeline():
    """Case status intent calls get_case_status and returns status."""
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.CASE_STATUS, confidence=0.95)
    )
    set_llm(mock_llm)

    mock_mcp = MagicMock()
    mock_mcp.get_case_status = AsyncMock(
        return_value=MagicMock(
            case_reference="WF-2026-0042",
            status="under_review",
            last_updated="2026-09-25T12:00:00Z",
            public_message="Case is currently under active review by welfare staff.",
        )
    )
    set_mcp_client(mock_mcp)

    state = initial_state("sess-status-1")
    state["user_prompt"] = "What is the status of case WF-2026-0042?"

    result = await run_agent(state)

    assert result["intent"] == Intent.CASE_STATUS
    event_types = [e["type"] for e in result["agent_events"]]
    assert "assistant_message" in event_types
