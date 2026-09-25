"""
tests/test_internal_api.py
Tests for the internal API contract (Phase 15):
- POST /internal/sessions/{session_id}/events
- GET /health
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app

INTERNAL_KEY = "changeme-dev-secret"
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
