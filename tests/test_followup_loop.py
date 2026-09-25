"""
tests/test_followup_loop.py
Integration tests for Phase 12 — Follow-up loop & multi-turn state persistence.

Verifies that:
1. Multi-turn interactions retain state across turns in SessionStore.
2. Incomplete criteria triggers ask_followup (assistant_message + request_information).
3. Subsequent turns incrementally merge new information without overwriting existing fields.
4. Form responses (user_form_response) properly populate structured criteria.
5. Image intake (user_image with media_id) attaches media to existing state and triggers image matching.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from agent.dependencies import set_llm, set_mcp_client
from agent.runner import reset_graph, run_agent
from agent.state import Intent, WayfindState, initial_state
from app.main import create_app
from app.session import MemorySessionStore
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport
from schemas.image import ImageMatch

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
async def test_multiturn_missing_child_two_turn_flow():
    """Multi-turn text interaction: Turn 1 provides partial info, Turn 2 provides the rest."""
    session_id = "sess-loop-01"
    store = MemorySessionStore()

    # Turn 1: User says "My daughter is missing."
    # Heuristic / LLM extracts gender="female", missing=["age", "last_seen_location"]
    state_turn1 = initial_state(session_id)
    state_turn1["user_prompt"] = "My daughter is missing."
    state_turn1["conversation_history"] = [{"role": "user", "content": "My daughter is missing."}]
    state_turn1["turn_count"] = 1

    result_turn1 = await run_agent(state_turn1)

    assert result_turn1["intent"] == Intent.MISSING_CHILD
    assert result_turn1["child_search_criteria"].gender == "female"
    assert "age" in result_turn1["missing_information"]
    assert "last_seen_location" in result_turn1["missing_information"]

    # Save to session store as API route does
    import json
    from app.routes.agent import _json_default
    raw_saved = json.loads(json.dumps(result_turn1, default=_json_default))
    # Reset agent_events as route does
    raw_saved["agent_events"] = []
    await store.set(session_id, raw_saved)

    # Turn 2: User responds "She's 7 years old and was last seen near Johar Town."
    loaded_state = await store.get(session_id)
    assert loaded_state is not None
    loaded_state["turn_count"] += 1
    loaded_state["user_prompt"] = "She's 7 years old and was last seen near Johar Town."
    loaded_state["conversation_history"].append(
        {"role": "user", "content": "She's 7 years old and was last seen near Johar Town."}
    )

    # Set up MCP client mock for candidate search
    mock_mcp = MagicMock()
    mock_mcp.search_child_records = AsyncMock(
        return_value=MagicMock(
            candidates=[MagicMock(case_id="CASE-JT-007")],
            total_candidates=1,
            truncated=False,
        )
    )
    set_mcp_client(mock_mcp)

    # Mock LLM for structured extraction to merge fields accurately
    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.MISSING_CHILD, confidence=0.98)
    )
    mock_llm.extract_child_criteria = AsyncMock(
        return_value=ChildSearchCriteria(
            gender="female",  # preserved from turn 1
            age=AgeRange(exact=7),
            last_seen_location="Johar Town",
        )
    )
    mock_llm.generate_final_response = AsyncMock(
        return_value="We found potential records matching your search."
    )
    set_llm(mock_llm)

    result_turn2 = await run_agent(loaded_state)

    assert result_turn2["intent"] == Intent.MISSING_CHILD
    assert result_turn2["child_search_criteria"].gender == "female"
    assert result_turn2["child_search_criteria"].age.exact == 7
    assert result_turn2["child_search_criteria"].last_seen_location == "Johar Town"
    assert len(result_turn2["missing_information"]) == 0
    assert result_turn2["candidate_count"] == 1
    assert result_turn2["review_required"] is True

    event_types = [e["type"] for e in result_turn2["agent_events"]]
    assert "search_started" in event_types
    assert "review_pending" in event_types


@pytest.mark.asyncio
async def test_multiturn_form_response_integration():
    """Turn 1 asks for info, Turn 2 provides structured form_data."""
    session_id = "sess-form-02"
    store = MemorySessionStore()

    # Initial state with gender known from Turn 1
    state = initial_state(session_id)
    state["intent"] = Intent.MISSING_CHILD
    state["child_search_criteria"] = ChildSearchCriteria(gender="male")
    state["missing_information"] = ["age", "last_seen_location"]
    state["turn_count"] = 1

    # Turn 2: user submits form_data
    state["turn_count"] = 2
    state["last_form_data"] = {
        "age": 8,
        "location": "Anarkali Bazaar",
        "clothing": ["red shirt", "blue jeans"],
    }
    state["user_prompt"] = "age: 8; location: Anarkali Bazaar; clothing: ['red shirt', 'blue jeans']"

    mock_mcp = MagicMock()
    mock_mcp.search_child_records = AsyncMock(
        return_value=MagicMock(
            candidates=[MagicMock(case_id="CASE-ANARKALI-1")],
            total_candidates=1,
            truncated=False,
        )
    )
    set_mcp_client(mock_mcp)

    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.MISSING_CHILD, confidence=0.95)
    )
    mock_llm.extract_child_criteria = AsyncMock(
        return_value=ChildSearchCriteria(
            gender="male",
            age=AgeRange(exact=8),
            last_seen_location="Anarkali Bazaar",
            clothing=["red shirt", "blue jeans"],
        )
    )
    set_llm(mock_llm)

    result = await run_agent(state)

    assert result["child_search_criteria"].age.exact == 8
    assert result["child_search_criteria"].last_seen_location == "Anarkali Bazaar"
    assert result["child_search_criteria"].clothing == ["red shirt", "blue jeans"]
    assert result["last_form_data"] is None  # consumed and reset
    assert result["candidate_count"] == 1


@pytest.mark.asyncio
async def test_multiturn_image_intake_flow():
    """Turn 1 completes search metadata; Turn 2 attaches media_id which triggers image matching."""
    session_id = "sess-image-03"

    state = initial_state(session_id)
    state["intent"] = Intent.MISSING_CHILD
    state["child_search_criteria"] = ChildSearchCriteria(
        gender="female",
        age=AgeRange(exact=9),
        last_seen_location="Gulberg",
    )
    state["media_reference"] = "media-attachment-1234"
    state["user_prompt"] = "Here is a photo of her"
    state["turn_count"] = 2

    mock_mcp = MagicMock()
    mock_mcp.search_child_records = AsyncMock(
        return_value=MagicMock(
            candidates=[MagicMock(case_id="CASE-GULBERG-09")],
            total_candidates=1,
            truncated=False,
        )
    )
    mock_mcp.image_match_candidates = AsyncMock(
        return_value=MagicMock(
            matches=[
                ImageMatch(
                    candidate_case_id="CASE-GULBERG-09",
                    similarity_score=0.88,
                    confidence="high",
                    matched_features=["facial_structure"],
                    model_version="1.0",
                )
            ]
        )
    )
    set_mcp_client(mock_mcp)

    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        return_value=MagicMock(intent=Intent.MISSING_CHILD, confidence=0.95)
    )
    mock_llm.extract_child_criteria = AsyncMock(
        return_value=state["child_search_criteria"]
    )
    set_llm(mock_llm)

    result = await run_agent(state)

    assert result["image_search_warranted"] is True
    assert len(result["image_match_results"]) == 1
    assert result["image_match_results"][0].similarity_score == 0.88
    assert result["review_required"] is True


@pytest.mark.asyncio
async def test_end_to_end_fastapi_multiturn_events():
    """Test full HTTP endpoint POST /internal/sessions/{id}/events across multiple sequential turns."""
    app = create_app()

    mock_llm = MagicMock()
    mock_llm.extract_intent = AsyncMock(
        side_effect=[
            MagicMock(intent=Intent.MISSING_CHILD, confidence=0.9),
            MagicMock(intent=Intent.MISSING_CHILD, confidence=0.95),
        ]
    )
    mock_llm.extract_child_criteria = AsyncMock(
        side_effect=[
            ChildSearchCriteria(gender="female"),  # Turn 1: only gender
            ChildSearchCriteria(gender="female", age=AgeRange(exact=5), last_seen_location="Saddar"),  # Turn 2
        ]
    )
    mock_llm.generate_followup_question = AsyncMock(
        return_value="Could you please tell me how old she is and where she was last seen?"
    )
    mock_llm.generate_final_response = AsyncMock(
        return_value="We searched records and submitted potential matches for human review."
    )
    set_llm(mock_llm)

    mock_mcp = MagicMock()
    mock_mcp.search_child_records = AsyncMock(
        return_value=MagicMock(
            candidates=[MagicMock(case_id="CASE-SADDAR-5")],
            total_candidates=1,
            truncated=False,
        )
    )
    set_mcp_client(mock_mcp)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        session_id = "http-session-multi-01"

        # Turn 1: user_message
        r1 = await client.post(
            f"/internal/sessions/{session_id}/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={
                "event": {
                    "type": "user_message",
                    "content": "My little girl is missing",
                }
            },
        )
        assert r1.status_code == 200
        events1 = r1.json()
        assert len(events1) >= 2
        event_types1 = [e["type"] for e in events1]
        assert "assistant_message" in event_types1
        assert "request_information" in event_types1

        # Turn 2: user_form_response
        r2 = await client.post(
            f"/internal/sessions/{session_id}/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={
                "event": {
                    "type": "user_form_response",
                    "form_data": {
                        "age": 5,
                        "location": "Saddar",
                    },
                }
            },
        )
        assert r2.status_code == 200
        events2 = r2.json()
        event_types2 = [e["type"] for e in events2]
        assert "search_started" in event_types2
        assert "review_pending" in event_types2
