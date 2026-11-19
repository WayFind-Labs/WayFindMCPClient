"""
tests/test_nodes.py
Unit tests for all 19 LangGraph nodes in isolation (Phase 15).

Verifies input parsing, state transformation, dependency utilization,
and output event production per node.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.dependencies import set_llm, set_mcp_client
from agent.nodes import (
    ask_followup,
    check_completeness,
    evaluate_candidates,
    evaluate_evidence,
    extract_structured_data,
    found_child_extract,
    generate_response,
    get_case_status_node,
    get_guidance_node,
    human_review,
    image_match,
    no_match,
    route_by_confidence,
    route_intent,
    safety_guidance,
    search_metadata,
    search_support_node,
    submit_found_child,
    understand_intent,
)
from agent.state import Intent, initial_state
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport
from schemas.evidence import ConfidenceTier, MatchEvidence
from schemas.image import ImageMatch


@pytest.fixture(autouse=True)
def clean_node_deps():
    set_llm(None)
    set_mcp_client(None)
    yield
    set_llm(None)
    set_mcp_client(None)


@pytest.mark.asyncio
async def test_node_understand_intent_with_llm():
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.MISSING_CHILD, confidence=0.92, case_reference=None)
    )
    set_llm(mock_llm)

    state = initial_state("s1")
    state["user_prompt"] = "My daughter was lost"
    res = await understand_intent(state)
    assert res["intent"] == Intent.MISSING_CHILD
    assert res["intent_confidence"] == 0.92


@pytest.mark.asyncio
async def test_node_extract_structured_data_missing_child():
    mock_llm = MagicMock()
    mock_llm.extract_child_criteria = AsyncMock(
        return_value=ChildSearchCriteria(gender="male", age=AgeRange(exact=7))
    )
    set_llm(mock_llm)

    state = initial_state("s2")
    state["intent"] = Intent.MISSING_CHILD
    state["user_prompt"] = "7yo boy lost"
    res = await extract_structured_data(state)
    assert res["child_search_criteria"].gender == "male"
    assert res["child_search_criteria"].age.exact == 7
    assert res["last_form_data"] is None


@pytest.mark.asyncio
async def test_found_field_statuses_return_with_extracted_draft():
    async def extract(**kwargs):
        kwargs["field_statuses"]["clothing"] = "unknown"
        return FoundChildReport(found_location="Synthetic market")

    mock_llm = MagicMock()
    mock_llm.extract_found_child_report = AsyncMock(side_effect=extract)
    set_llm(mock_llm)
    state = initial_state("status-session")
    state["intent"] = Intent.FOUND_CHILD
    state["user_prompt"] = "I could not see the clothing"
    result = await extract_structured_data(state)
    assert result["found_field_statuses"] == {"clothing": "unknown"}
    assert result["found_child_report"].found_location == "Synthetic market"


@pytest.mark.asyncio
async def test_node_check_completeness():
    state = initial_state("s3")
    state["intent"] = Intent.MISSING_CHILD
    state["child_search_criteria"] = ChildSearchCriteria(gender="female")

    res = await check_completeness(state)
    assert "age" in res["missing_information"]
    assert "last_seen_location" in res["missing_information"]
    assert res["followup_question"] is not None


@pytest.mark.asyncio
async def test_found_optional_details_are_offered_once_and_can_be_skipped():
    set_llm(None)
    state = initial_state("optional-found")
    state["intent"] = Intent.FOUND_CHILD
    state["found_child_report"] = FoundChildReport(found_location="Synthetic market")
    state["found_field_statuses"] = {"approx_age": "unknown", "clothing": "declined"}
    first = await check_completeness(state)
    assert first["missing_information"] == ["current_circumstances"]
    assert "skip" in first["followup_question"].lower()
    from agent.nodes.ask_followup import ask_followup
    state["missing_information"] = first["missing_information"]
    state["followup_question"] = first["followup_question"]
    state["found_draft_id"] = "synthetic-draft"
    offered = ask_followup(state)["agent_events"][-1]
    assert offered["optional_field"] == "current_circumstances"
    assert offered["draft_id"] == "synthetic-draft"
    state["found_optional_questions_asked"] = first["found_optional_questions_asked"]
    state["found_field_statuses"]["current_circumstances"] = "unknown"
    second = await check_completeness(state)
    assert second["missing_information"] == ["identifying_features"]
    state["found_optional_questions_asked"] = second["found_optional_questions_asked"]
    state["found_field_statuses"]["identifying_features"] = "declined"
    complete = await check_completeness(state)
    assert complete["missing_information"] == ["reporter_name", "reporter_contact"]


@pytest.mark.asyncio
async def test_explicitly_unavailable_location_does_not_repeat_location_question():
    from agent.state import completeness_router

    state = initial_state("unknown-location")
    state["intent"] = Intent.FOUND_CHILD
    state["found_child_report"] = FoundChildReport(found_location="unknown")
    state["found_field_statuses"] = {"found_location": "unknown"}
    result = await check_completeness(state)
    state.update(result)
    assert result["followup_question"] is None
    assert completeness_router(state) == "location_unavailable"


def test_node_ask_followup():
    state = initial_state("s4")
    state["followup_question"] = "How old is the child?"
    state["missing_information"] = ["age"]

    res = ask_followup(state)
    assert len(res["agent_events"]) == 2
    types = [e["type"] for e in res["agent_events"]]
    assert "assistant_message" in types
    assert "request_information" in types


def test_first_found_followup_delivers_safety_before_location_request():
    state = initial_state("first-found-followup")
    state["intent"] = Intent.FOUND_CHILD
    state["followup_question"] = "Where did you find the child?"
    state["missing_information"] = ["found_location"]
    first = ask_followup(state)
    assert first["agent_events"][0]["type"] == "assistant_message"
    assert "immediate danger" in first["agent_events"][0]["content"]
    assert first["agent_events"][1]["content"] == "Where did you find the child?"
    assert len(first["agent_events"]) == 2
    assert first["found_safety_delivered"] is True

    state["found_safety_delivered"] = True
    later = ask_followup(state)
    assert len(later["agent_events"]) == 1


def test_node_route_intent():
    state = initial_state("s5")
    res = route_intent(state)
    assert res == {}


@pytest.mark.asyncio
async def test_node_search_metadata():
    mock_mcp = MagicMock()
    mock_mcp.search_child_records = AsyncMock(
        return_value=MagicMock(candidates=[MagicMock(case_id="C-1")], total_candidates=1, truncated=False)
    )
    set_mcp_client(mock_mcp)

    state = initial_state("s6")
    state["child_search_criteria"] = ChildSearchCriteria(
        gender="female",
        age=AgeRange(exact=5),
        last_seen_location="Gulberg",
    )
    res = await search_metadata(state)
    assert res["candidate_ids"] == ["C-1"]
    assert res["candidate_count"] == 1


def test_node_evaluate_candidates():
    state = initial_state("s7")
    state["candidate_count"] = 5
    state["media_reference"] = "media-1"
    res = evaluate_candidates(state)
    assert res["image_search_warranted"] is True


@pytest.mark.asyncio
async def test_node_image_match():
    mock_mcp = MagicMock()
    mock_mcp.image_match_candidates = AsyncMock(
        return_value=MagicMock(
            matches=[
                ImageMatch(
                    candidate_case_id="C-1",
                    similarity_score=0.85,
                    confidence="high",
                    matched_features=["face"],
                    model_version="1.0",
                )
            ],
            candidates_searched=1,
        )
    )
    set_mcp_client(mock_mcp)

    state = initial_state("s8")
    state["candidate_ids"] = ["C-1"]
    state["media_reference"] = "media-1"
    res = await image_match(state)
    assert len(res["image_match_results"]) == 1
    assert res["image_match_results"][0].similarity_score == 0.85


def test_node_evaluate_evidence():
    state = initial_state("s9")
    state["candidate_ids"] = ["C-1"]
    state["image_match_results"] = [
        ImageMatch(
            candidate_case_id="C-1",
            similarity_score=0.9,
            confidence="high",
            matched_features=["face"],
            model_version="1.0",
        )
    ]
    res = evaluate_evidence(state)
    assert res["match_evidence"] is not None
    assert res["confidence_tier"] in (ConfidenceTier.HIGH, ConfidenceTier.UNCERTAIN)


def test_node_route_by_confidence():
    state = initial_state("s10")
    res = route_by_confidence(state)
    assert res == {}


@pytest.mark.asyncio
async def test_node_human_review():
    state = initial_state("s11")
    state["candidate_ids"] = ["C-1"]
    state["confidence_tier"] = ConfidenceTier.HIGH
    state["match_evidence"] = MatchEvidence(
        candidate_case_id="C-1",
        metadata_score=0.85,
        composite_score=0.85,
        supporting_factors=["Strong demographic alignment"],
    )

    res = await human_review(state)
    assert res["review_required"] is True
    assert res["case_reference"] is not None
    event_types = [e["type"] for e in res["agent_events"]]
    assert "review_pending" in event_types


def test_node_no_match():
    state = initial_state("s12")
    res = no_match(state)
    assert "final_response" in res
    assert len(res["agent_events"]) == 1


@pytest.mark.asyncio
async def test_node_found_child_extract():
    state = initial_state("s13")
    state["found_child_report"] = FoundChildReport(found_location="Liberty Market")
    res = await found_child_extract(state)
    assert res["found_child_report"].found_location == "Liberty Market"
    assert res["missing_information"] == []


@pytest.mark.asyncio
async def test_node_safety_guidance():
    state = initial_state("s14")
    res = await safety_guidance(state)
    assert len(res["agent_events"]) == 1
    assert "police" in res["agent_events"][0]["content"].lower()


@pytest.mark.asyncio
async def test_found_safety_survives_model_outage():
    unavailable_llm = MagicMock()
    unavailable_llm.generate_guidance_response = AsyncMock(side_effect=TimeoutError())
    set_llm(unavailable_llm)
    state = initial_state("found-model-outage")
    state["intent"] = Intent.FOUND_CHILD
    res = await safety_guidance(state)
    assert "immediate danger" in res["agent_events"][0]["content"]
    assert len(res["agent_events"]) == 1
    assert res["found_safety_delivered"] is True


@pytest.mark.asyncio
async def test_node_submit_found_child():
    mock_mcp = MagicMock()
    mock_mcp.submit_found_child_report = AsyncMock(
        return_value=MagicMock(case_reference="WF-FOUND-999", submitted_at="2026-11-17T00:00:00Z")
    )
    set_mcp_client(mock_mcp)

    state = initial_state("s15")
    state["found_child_report"] = FoundChildReport(found_location="Mall Road", reporter_name="Synthetic Finder", reporter_contact="+1 202 555 0131")
    review = await submit_found_child(state)
    assert any(event["type"] == "request_confirmation" for event in review["agent_events"])
    assert "Found near: Mall Road" in review["agent_events"][-1]["content"]
    mock_mcp.submit_found_child_report.assert_not_called()
    state["submission_confirmed"] = True
    res = await submit_found_child(state)
    assert res["case_reference"] == "WF-FOUND-999"
    assert next(event for event in res["agent_events"] if event["type"] == "submission_complete")["submitted_at"] == "2026-11-17T00:00:00Z"
    assert next(event for event in res["agent_events"] if event["type"] == "submission_complete")["schema_version"] == "FoundChildIntakeV1"
    receipt_text = next(event["content"] for event in res["agent_events"] if event["type"] == "assistant_message")
    assert "+1 202 555 0131" not in receipt_text
    assert "does not notify authorities" in receipt_text
    assert "reviewed irregularly" in receipt_text
    assert "no guaranteed monitoring" in receipt_text
    first_key = mock_mcp.submit_found_child_report.call_args.kwargs["report"].submission_id
    assert first_key
    await submit_found_child(state)
    assert mock_mcp.submit_found_child_report.call_args.kwargs["report"].submission_id == first_key

    retry_state = {**state, "case_reference": res["case_reference"], "found_child_report": res["found_child_report"]}
    retry = await submit_found_child(retry_state)
    receipt = next(event for event in retry["agent_events"] if event["type"] == "submission_complete")
    assert receipt["record_id"] == res["case_reference"]
    assert receipt["submitted_at"] == "2026-11-17T00:00:00Z"
    assert mock_mcp.submit_found_child_report.await_count == 2
    state["found_draft_id"] = "second-draft"
    await submit_found_child(state)
    assert mock_mcp.submit_found_child_report.call_args.kwargs["report"].submission_id != first_key


@pytest.mark.asyncio
async def test_found_report_cannot_submit_without_finder_contact():
    mock_mcp = MagicMock()
    mock_mcp.submit_found_child_report = AsyncMock()
    set_mcp_client(mock_mcp)
    state = initial_state("no-finder-contact")
    state["found_child_report"] = FoundChildReport(found_location="Synthetic market")
    state["submission_confirmed"] = True
    result = await submit_found_child(state)
    assert "full name" in result["agent_events"][-1]["message"]
    assert result["submission_confirmed"] is False
    mock_mcp.submit_found_child_report.assert_not_called()


@pytest.mark.asyncio
async def test_found_report_review_includes_collected_details():
    state = initial_state("review-details")
    state["found_child_report"] = FoundChildReport(
        found_location="Market", approx_age=AgeRange(min=5, max=7),
        clothing=["red shirt"], identifying_features=["glasses"],
        authorities_contacted=False, reporter_name="Synthetic Finder", reporter_contact="+1 202 555 0131",
    )
    result = await submit_found_child(state)
    summary = result["agent_events"][-1]["content"]
    assert "Approximate age: 5–7" in summary
    assert "Clothing: red shirt" in summary
    assert "Visible features: glasses" in summary
    assert "Authorities contacted: no" in summary
    assert "+1 202 555 0131" in summary


@pytest.mark.asyncio
async def test_found_child_question_interrupts_intake():
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.GUIDANCE, confidence=0.95)
    )
    set_llm(mock_llm)
    state = initial_state("question-during-intake")
    state["intent"] = Intent.FOUND_CHILD
    state["found_child_report"] = FoundChildReport(found_location="Market")
    state["user_prompt"] = "Can I post the child's photo online?"
    result = await understand_intent(state)
    assert result["intent"] == Intent.GUIDANCE
    mock_llm.extract_intent.assert_awaited_once()


@pytest.mark.asyncio
async def test_node_search_support():
    mock_mcp = MagicMock()
    mock_mcp.search_support = AsyncMock(
        return_value=MagicMock(
            locations=[MagicMock(name="Edhi Home", address="Gulberg", support_type="shelter")],
            total_locations=1,
        )
    )
    set_mcp_client(mock_mcp)

    state = initial_state("s16")
    state["user_prompt"] = "Lahore shelters"
    res = await search_support_node(state)
    event_types = [e["type"] for e in res["agent_events"]]
    assert "search_results" in event_types


@pytest.mark.asyncio
async def test_node_get_guidance():
    mock_mcp = MagicMock()
    mock_mcp.get_guidance = AsyncMock(
        return_value=MagicMock(
            guidance="Follow safe protocols",
            next_steps=["Contact authorities"],
            topic="general",
        )
    )
    set_mcp_client(mock_mcp)

    state = initial_state("s17")
    state["user_prompt"] = "How to report"
    res = await get_guidance_node(state)
    event_types = [e["type"] for e in res["agent_events"]]
    assert "assistant_message" in event_types


@pytest.mark.asyncio
async def test_node_get_case_status():
    mock_mcp = MagicMock()
    mock_mcp.get_case_status = AsyncMock()
    set_mcp_client(mock_mcp)

    state = initial_state("s18")
    state["case_reference"] = "WF-001"
    res = await get_case_status_node(state)
    event_types = [e["type"] for e in res["agent_events"]]
    assert "assistant_message" in event_types
    assert "cannot check report status" in res["agent_events"][0]["content"]
    mock_mcp.get_case_status.assert_not_called()


@pytest.mark.asyncio
async def test_node_generate_response():
    state = initial_state("s19")
    state["agent_events"] = [{"type": "search_started"}]
    res = await generate_response(state)
    assert len(res["agent_events"]) >= 1


@pytest.mark.asyncio
async def test_tool_failure_does_not_claim_staff_notification():
    state = initial_state("tool-failure")
    state["tool_failures"] = ["submit_found_child_report"]
    res = await generate_response(state)
    content = res["agent_events"][0]["content"].lower()
    assert "notified" not in content
    assert "contact the appropriate local authority" in content
