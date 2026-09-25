"""
tests/test_security.py
Security and internal boundary tests (Phase 13).

Verifies:
1. Internal auth enforcement via X-Internal-Key (403 on missing/invalid, 200 on valid).
2. Health endpoint is exempt from authentication.
3. Response isolation: output is strictly list[AgentEvent], never internal WayfindState.
4. Opaque media ID validation (rejects URLs and file paths).
5. FastMCP image comparison tool abuse prevention on empty candidate sets.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.main import create_app
from mcp_server.tools.image_match_candidates import image_match_candidates
from schemas.event import IncomingEvent

INTERNAL_KEY = "changeme-dev-secret"
WRONG_KEY = "wrong-unauthorized-key"


@pytest.mark.asyncio
async def test_auth_missing_internal_key_rejected():
    """Requests without X-Internal-Key header must receive 403 Forbidden."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/sessions/test-sess-auth-01/events",
            json={"event": {"type": "user_message", "content": "Hello"}},
        )
        assert response.status_code == 403
        data = response.json()
        assert data.get("message") == "Forbidden."


@pytest.mark.asyncio
async def test_auth_invalid_internal_key_rejected():
    """Requests with incorrect X-Internal-Key header must receive 403 Forbidden."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/sessions/test-sess-auth-02/events",
            headers={"X-Internal-Key": WRONG_KEY},
            json={"event": {"type": "user_message", "content": "Hello"}},
        )
        assert response.status_code == 403
        data = response.json()
        assert data.get("message") == "Forbidden."


@pytest.mark.asyncio
async def test_auth_valid_internal_key_accepted():
    """Requests with valid X-Internal-Key header must succeed."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/sessions/test-sess-auth-03/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={"event": {"type": "user_message", "content": "Where is the nearest shelter?"}},
        )
        assert response.status_code == 200
        assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_health_endpoint_auth_exempt():
    """Health endpoint /health must be accessible without authentication."""
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "wayfind-agent"}


@pytest.mark.asyncio
async def test_response_contains_no_internal_state_leaks():
    """Verify that agent endpoint response exposes ONLY AgentEvent fields and no internal state."""
    app = create_app()
    forbidden_state_keys = {
        "conversation_history",
        "child_search_criteria",
        "found_child_report",
        "tool_failures",
        "errors",
        "turn_count",
        "candidate_ids",
        "match_evidence",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/internal/sessions/test-sess-leak-check/events",
            headers={"X-Internal-Key": INTERNAL_KEY},
            json={"event": {"type": "user_message", "content": "I found a child in Saddar"}},
        )
        assert response.status_code == 200
        events = response.json()
        assert isinstance(events, list)
        for evt in events:
            assert isinstance(evt, dict)
            assert "type" in evt
            for key in forbidden_state_keys:
                assert key not in evt, f"Internal state key '{key}' leaked in event response!"


def test_opaque_media_id_validation():
    """Ensure IncomingEvent rejects raw paths or URLs in media_id."""
    # Valid opaque media ID
    event = IncomingEvent(type="user_image", media_id="media-uuid-20260925-0042")
    assert event.media_id == "media-uuid-20260925-0042"

    # Reject URLs
    with pytest.raises(ValidationError):
        IncomingEvent(type="user_image", media_id="https://example.com/photo.jpg")

    with pytest.raises(ValidationError):
        IncomingEvent(type="user_image", media_id="http://insecure.site/pic.png")

    # Reject file paths
    with pytest.raises(ValidationError):
        IncomingEvent(type="user_image", media_id="/var/data/uploads/image.jpg")

    with pytest.raises(ValidationError):
        IncomingEvent(type="user_image", media_id="C:\\Windows\\system32\\image.png")


@pytest.mark.asyncio
async def test_image_match_tool_rejects_empty_candidate_pool():
    """image_match_candidates tool safely handles empty candidate case IDs without unrestricted matching."""
    res = await image_match_candidates(media_id="media-1234", candidate_case_ids=[])
    assert res.candidates_searched == 0
    assert len(res.matches) == 0

    res_empty_media = await image_match_candidates(media_id="", candidate_case_ids=["CASE-1", "CASE-2"])
    assert res_empty_media.candidates_searched == 0
    assert len(res_empty_media.matches) == 0
