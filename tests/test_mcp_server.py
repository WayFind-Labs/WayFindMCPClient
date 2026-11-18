"""
tests/test_mcp_server.py
Unit tests for FastMCP server and tool registration (Phase 7).
"""

import pytest

from mcp_server.server import mcp
from mcp_server.tools.get_case_status import get_case_status
from mcp_server.tools.get_guidance import get_guidance
from mcp_server.tools.image_match_candidates import image_match_candidates
from mcp_server.tools.search_child_records import search_child_records
from mcp_server.tools.search_support import search_support
from mcp_server.tools.submit_found_child_report import submit_found_child_report
from schemas.child import ChildSearchCriteria, FoundChildReport
from schemas.location import Location


def test_mcp_server_initialization():
    assert mcp.name == "wayfind"


@pytest.mark.asyncio
async def test_tool_search_child_records():
    criteria = ChildSearchCriteria(gender="male")
    res = await search_child_records(criteria)
    assert res.total_candidates >= 1
    assert "male" in res.search_summary


@pytest.mark.asyncio
async def test_tool_image_match_candidates():
    res = await image_match_candidates(
        media_id="test-media-1",
        candidate_case_ids=["case-1", "case-2"],
    )
    assert res.query_media_id == "test-media-1"
    assert res.candidates_searched == 2


@pytest.mark.asyncio
async def test_tool_submit_found_child_report():
    report = FoundChildReport(
        gender="female",
        found_location="Liberty Market",
    )
    from unittest.mock import AsyncMock, patch
    from schemas.case import FoundChildSubmissionResult

    receipt = FoundChildSubmissionResult(
        case_reference="WF-FOUND-TEST", submitted_at="2026-11-17T00:00:00Z",
        guidance="Contact authorities directly", next_steps=[], message="Recorded",
    )
    with patch("services.postgres_client.get_postgres_client") as get_client:
        get_client.return_value.submit_found_child = AsyncMock(return_value=receipt)
        res = await submit_found_child_report(report)
    assert res.case_reference == receipt.case_reference


@pytest.mark.asyncio
async def test_tool_search_support():
    loc = Location(label="Islamabad")
    res = await search_support(loc)
    assert len(res.locations) >= 2


@pytest.mark.asyncio
async def test_tool_get_guidance():
    res = await get_guidance("What to do?", topic="safety")
    assert res.guidance
    assert res.topic == "safety"


@pytest.mark.asyncio
async def test_tool_get_case_status(monkeypatch):
    monkeypatch.setattr("services.postgres_client.get_postgres_client", lambda: None)
    with pytest.raises(RuntimeError, match="unavailable"):
        await get_case_status("WF-20260925-0042")
