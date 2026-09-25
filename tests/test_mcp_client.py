"""
tests/test_mcp_client.py
Unit tests for WayfindLLM and WayfindMCPClient (Phase 6).
"""

import pytest

from agent.dependencies import set_llm, set_mcp_client
from agent.nodes.extract_structured_data import extract_structured_data
from agent.nodes.get_case_status import get_case_status_node
from agent.nodes.get_guidance import get_guidance_node
from agent.nodes.safety_guidance import safety_guidance
from agent.nodes.search_metadata import search_metadata
from agent.nodes.search_support import search_support_node
from agent.nodes.submit_found_child import submit_found_child
from agent.nodes.understand_intent import understand_intent
from agent.state import Intent, initial_state
from mcp_client.client import WayfindMCPClient
from mcp_client.llm import IntentResult, WayfindLLM
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport
from schemas.location import Location


@pytest.fixture
def llm():
    """LLM instance in fallback / local mode (no live API key needed)."""
    return WayfindLLM(provider="gemini", api_key="")


@pytest.fixture
def mcp():
    """MCP client in local / in-process mode."""
    return WayfindMCPClient(transport="inprocess")


# ── WayfindLLM Tests ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_extract_intent_missing(llm):
    result = await llm.extract_intent(
        conversation_history=[],
        prompt="I am looking for my lost son who went missing yesterday.",
    )
    assert isinstance(result, IntentResult)
    assert result.intent == Intent.MISSING_CHILD
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_llm_extract_intent_found(llm):
    result = await llm.extract_intent(
        conversation_history=[],
        prompt="I found an unaccompanied little girl near the park.",
    )
    assert isinstance(result, IntentResult)
    assert result.intent == Intent.FOUND_CHILD
    assert result.confidence > 0.5


@pytest.mark.asyncio
async def test_llm_extract_intent_case_status(llm):
    result = await llm.extract_intent(
        conversation_history=[],
        prompt="Can you tell me the update on case WF-20260925-0042?",
    )
    assert isinstance(result, IntentResult)
    assert result.intent == Intent.CASE_STATUS
    assert result.case_reference == "WF-20260925-0042"


@pytest.mark.asyncio
async def test_llm_extract_child_criteria_merge(llm):
    existing = ChildSearchCriteria(gender="female")
    updated = await llm.extract_child_criteria(
        existing_criteria=existing,
        prompt="She is 6 years old and was last seen near Central Station.",
        form_data=None,
    )
    assert updated.gender == "female"
    assert updated.age.exact == 6
    assert "Central Station" in (updated.last_seen_location or "")


@pytest.mark.asyncio
async def test_llm_extract_found_child_report(llm):
    existing = FoundChildReport(found_location="unknown")
    updated = await llm.extract_found_child_report(
        existing_report=existing,
        prompt="Found a young boy at Liberty Market.",
        form_data={"location": "Liberty Market Lahore"},
        media_reference="media-safe-12345",
    )
    assert updated.gender == "male"
    assert "Liberty Market" in updated.found_location
    assert updated.media_reference == "media-safe-12345"


@pytest.mark.asyncio
async def test_llm_generate_followup_question(llm):
    q = await llm.generate_followup_question(["gender", "last_seen_location"])
    assert "gender" in q.lower()
    assert "last seen" in q.lower() or "where" in q.lower()


# ── WayfindMCPClient Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mcp_search_child_records(mcp):
    criteria = ChildSearchCriteria(gender="male", age=AgeRange(exact=7))
    res = await mcp.search_child_records(criteria)
    assert hasattr(res, "candidates")
    assert hasattr(res, "total_candidates")


@pytest.mark.asyncio
async def test_mcp_image_match_candidates(mcp):
    res = await mcp.image_match_candidates(
        media_id="media-123",
        candidate_case_ids=["case-001", "case-002"],
    )
    assert res.query_media_id == "media-123"
    assert res.candidates_searched == 2


@pytest.mark.asyncio
async def test_mcp_submit_found_child(mcp):
    report = FoundChildReport(
        gender="female",
        found_location="Sector G-9",
    )
    res = await mcp.submit_found_child_report(report)
    assert res.case_reference.startswith("WF-FOUND-")
    assert res.guidance


@pytest.mark.asyncio
async def test_mcp_search_support(mcp):
    loc = Location(label="Rawalpindi")
    res = await mcp.search_support(location=loc)
    assert len(res.locations) > 0


@pytest.mark.asyncio
async def test_mcp_get_guidance(mcp):
    res = await mcp.get_guidance("What to do if I found a child?", topic="found_child")
    assert res.guidance
    assert res.guidance_text


@pytest.mark.asyncio
async def test_mcp_get_case_status(mcp):
    res = await mcp.get_case_status("WF-20260925-0042")
    assert res.case_reference == "WF-20260925-0042"
    assert res.status == "under_review"
    assert res.status_label == "Under Review"


# ── Node Integration with Wired Clients ─────────────────────────────────────

@pytest.mark.asyncio
async def test_nodes_with_wired_clients(llm, mcp):
    set_llm(llm)
    set_mcp_client(mcp)

    # 1. understand_intent node
    state = initial_state("test-session")
    state["user_prompt"] = "I lost my 5 year old daughter at City Mall."
    out_intent = await understand_intent(state)
    assert out_intent["intent"] == Intent.MISSING_CHILD

    # 2. extract_structured_data node
    state = {**state, **out_intent}
    out_extract = await extract_structured_data(state)
    assert out_extract["child_search_criteria"].gender == "female"
    assert out_extract["child_search_criteria"].age.exact == 5

    # 3. search_metadata node
    state = {**state, **out_extract}
    out_search = await search_metadata(state)
    assert "agent_events" in out_search

    # 4. safety_guidance node
    out_safety = await safety_guidance(state)
    assert any(e.get("type") == "assistant_message" for e in out_safety["agent_events"])

    # 5. submit_found_child node
    found_state = initial_state("test-found")
    found_state["user_prompt"] = "I found a child"
    found_state["found_child_report"] = FoundChildReport(found_location="Bus Stand")
    out_submit = await submit_found_child(found_state)
    assert "case_reference" in out_submit
    assert any(e.get("type") == "submission_complete" for e in out_submit["agent_events"])

    # 6. search_support node
    sup_state = initial_state("test-sup")
    sup_state["user_prompt"] = "Lahore"
    out_sup = await search_support_node(sup_state)
    assert any(e.get("type") == "search_results" for e in out_sup["agent_events"])

    # 7. get_guidance node
    guid_state = initial_state("test-guid")
    guid_state["user_prompt"] = "What are the steps?"
    out_guid = await get_guidance_node(guid_state)
    assert any(e.get("type") == "assistant_message" for e in out_guid["agent_events"])

    # 8. get_case_status node
    status_state = initial_state("test-status")
    status_state["case_reference"] = "WF-20260925-0042"
    out_status = await get_case_status_node(status_state)
    assert any(e.get("type") == "assistant_message" for e in out_status["agent_events"])
