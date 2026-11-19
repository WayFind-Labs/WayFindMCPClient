"""
tests/test_internal_api.py
Tests for the internal API contract (Phase 15):
- POST /internal/sessions/{session_id}/events
- GET /health
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.config import get_settings
from app.main import create_app
from app.routes.agent import _initial_state
from app.session import MemorySessionStore

INTERNAL_KEY = get_settings().shelter_backend_api_key
WRONG_KEY = "invalid-key-xyz"


@pytest.mark.asyncio
async def test_internal_api_health_endpoint():
    """GET /health returns 200 with service status, exempt from authentication."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"
        assert data["service"] == "wayfind-agent"


@pytest.mark.asyncio
async def test_agent_readiness_rejects_missing_configuration(monkeypatch):
    settings = Settings(
        _env_file=None,
        groq_api_key="",
        postgres_service_url="",
        session_backend="memory",
        mcp_server_url="",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/ready")).status_code == 403
        response = await client.get("/ready", headers={"X-Internal-Key": settings.shelter_backend_api_key})
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["missing"]
    assert "REDIS_URL" in response.json()["missing"]


@pytest.mark.asyncio
async def test_agent_readiness_checks_redis_and_mcp(monkeypatch):
    settings = Settings(
        _env_file=None,
        shelter_backend_api_key="synthetic-internal-key",
        groq_api_key="synthetic-provider-key",
        postgres_service_url="http://gateway.internal",
        session_backend="redis",
        redis_url="redis://example.invalid:6379/0",
        mcp_transport="sse",
        mcp_server_url="http://mcp.internal/sse",
    )
    monkeypatch.setattr("app.main.get_settings", lambda: settings)
    probe = AsyncMock()
    monkeypatch.setattr("app.main._probe_mcp", probe)
    redis = SimpleNamespace(ping=AsyncMock(return_value=True))
    app = create_app()
    app.state.llm = SimpleNamespace(_llm=object())
    app.state.session_store = SimpleNamespace(_ensure_client=AsyncMock(return_value=redis))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/ready", headers={"X-Internal-Key": settings.shelter_backend_api_key})
    assert response.status_code == 200
    redis.ping.assert_awaited_once()
    probe.assert_awaited_once_with(settings.mcp_server_url)


@pytest.mark.asyncio
async def test_cancel_and_stale_confirmation_never_run_submission_graph():
    app = create_app()
    store = MemorySessionStore()
    app.state.session_store = store
    app.state.graph_runner = AsyncMock()
    state = _initial_state("draft-session")
    state["found_draft_id"] = "draft-current"
    state["found_child_report"] = {"found_location": "Synthetic market"}
    await store.set("draft-session", state)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        stale = await client.post(
            "/internal/sessions/draft-session/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={"event": {"type": "user_form_response", "form_data": {"confirm_found_report": True, "draft_id": "old-draft"}}},
        )
        assert stale.json()[0]["type"] == "error"
        assert (await store.get("draft-session"))["found_child_report"] is not None

        canceled = await client.post(
            "/internal/sessions/draft-session/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={"event": {"type": "user_form_response", "form_data": {"cancel_found_report": True, "draft_id": "draft-current"}}},
        )
    assert "No report was recorded" in canceled.json()[0]["content"]
    saved = await store.get("draft-session")
    assert saved["found_child_report"] is None
    assert saved["found_draft_id"] is None
    assert saved["intent"] == "found_child"
    assert saved["found_safety_delivered"] is True
    app.state.graph_runner.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_new_report_replaces_prior_draft_and_reference():
    app = create_app()
    store = MemorySessionStore()
    app.state.session_store = store
    app.state.graph_runner = AsyncMock()
    state = _initial_state("new-report-session")
    state["found_draft_id"] = "old-draft"
    state["found_child_report"] = {"found_location": "Old location"}
    state["case_reference"] = "WF-OLD-CASE"
    await store.set("new-report-session", state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/sessions/new-report-session/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={"event": {"type": "user_form_response", "form_data": {"new_found_report": True}}},
        )
    assert response.status_code == 200
    saved = await store.get("new-report-session")
    assert saved["found_draft_id"] != "old-draft"
    assert saved["found_child_report"] is None
    assert saved["case_reference"] is None
    assert saved["intent"] == "found_child"
    assert saved["found_safety_delivered"] is True
    assert saved["conversation_history"][-1]["content"] == "Tell me where you found the child."
    assert response.json()[0]["draft_id"] == saved["found_draft_id"]
    app.state.graph_runner.assert_not_awaited()


@pytest.mark.asyncio
async def test_snapshot_restores_only_review_or_committed_receipt():
    app = create_app()
    store = MemorySessionStore()
    app.state.session_store = store
    state = _initial_state("resume-session")
    state["found_draft_id"] = "resume-draft"
    state["found_child_report"] = {"found_location": "Synthetic market"}
    await store.set("resume-session", state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/internal/sessions/resume-session/snapshot")).status_code == 403
        missing = await client.get("/internal/sessions/other-session/snapshot", headers={"X-Internal-Key": INTERNAL_KEY})
        review = await client.get("/internal/sessions/resume-session/snapshot", headers={"X-Internal-Key": INTERNAL_KEY})
        assert missing.json() == []
        assert review.json()[0]["type"] == "request_confirmation"
        assert review.json()[0]["draft_id"] == "resume-draft"
        state["case_reference"] = "WF-SYNTHETIC"
        state["found_child_report"]["received_at"] = "2026-11-19T00:00:00Z"
        await store.set("resume-session", state)
        receipt = await client.get("/internal/sessions/resume-session/snapshot", headers={"X-Internal-Key": INTERNAL_KEY})
    assert receipt.json()[0]["type"] == "submission_complete"
    assert receipt.json()[0]["record_id"] == "WF-SYNTHETIC"


@pytest.mark.asyncio
async def test_snapshot_restores_chat_question_without_a_form():
    app = create_app()
    store = MemorySessionStore()
    app.state.session_store = store
    state = _initial_state("chat-resume")
    state["found_child_report"] = {"found_location": "unknown"}
    state["missing_information"] = ["found_location", "reporter_name", "reporter_contact"]
    state["conversation_history"] = [{"role": "assistant", "content": "Where did you find the child?"}]
    await store.set("chat-resume", state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/internal/sessions/chat-resume/snapshot", headers={"X-Internal-Key": INTERNAL_KEY})
    assert response.status_code == 200
    assert [event["type"] for event in response.json()] == ["assistant_message"]
    assert "where you found the child" in response.json()[0]["content"]


@pytest.mark.asyncio
async def test_snapshot_restores_optional_skip_and_clear_draft_actions():
    app = create_app()
    store = MemorySessionStore()
    app.state.session_store = store
    state = _initial_state("optional-resume")
    state["found_draft_id"] = "optional-draft"
    state["found_child_report"] = {"found_location": "Synthetic market"}
    state["missing_information"] = ["age"]
    await store.set("optional-resume", state)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/internal/sessions/optional-resume/snapshot", headers={"X-Internal-Key": INTERNAL_KEY})
    event = response.json()[0]
    assert event["type"] == "assistant_message"
    assert event["optional_field"] == "age"
    assert event["draft_id"] == "optional-draft"


@pytest.mark.asyncio
async def test_internal_api_auth_validation():
    """Verify auth behavior on POST /internal/sessions/{id}/events."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Missing key -> 403
        r1 = await client.post(
            "/internal/sessions/s-auth/events",
            json={"event": {"type": "user_message", "content": "hello"}},
        )
        assert r1.status_code == 403

        # Wrong key -> 403
        r2 = await client.post(
            "/internal/sessions/s-auth/events",
            headers={"X-Internal-Key": WRONG_KEY},
            json={"event": {"type": "user_message", "content": "hello"}},
        )
        assert r2.status_code == 403

        # Correct key -> 200
        r3 = await client.post(
            "/internal/sessions/s-auth/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={"event": {"type": "user_message", "content": "Where is the nearest shelter?"}},
        )
        assert r3.status_code == 200
        assert isinstance(r3.json(), list)


@pytest.mark.asyncio
async def test_internal_api_invalid_payload_rejected():
    """Missing required event field returns 422 Unprocessable Entity."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        res = await client.post(
            "/internal/sessions/s-bad/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={"invalid_key": {}},
        )
        assert res.status_code == 422


@pytest.mark.asyncio
async def test_internal_api_multiturn_persistence():
    """Verify session state persistence across multiple sequential HTTP calls."""
    app = create_app()
    session_id = "s-multiturn-http"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Turn 1
        r1 = await client.post(
            f"/internal/sessions/{session_id}/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={"event": {"type": "user_message", "content": "My daughter went missing"}},
        )
        assert r1.status_code == 200
        events1 = r1.json()
        assert len(events1) >= 1

        # Turn 2
        r2 = await client.post(
            f"/internal/sessions/{session_id}/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={"event": {"type": "user_message", "content": "She is 7 years old and in Saddar"}},
        )
        assert r2.status_code == 200
        events2 = r2.json()
        assert len(events2) >= 1
