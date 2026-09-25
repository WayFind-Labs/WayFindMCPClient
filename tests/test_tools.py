"""
tests/test_tools.py
Comprehensive unit tests for the 6 FastMCP tools (Phase 8).
"""

import pytest

from mcp_server.tools.get_case_status import get_case_status
from mcp_server.tools.get_guidance import get_guidance
from mcp_server.tools.image_match_candidates import image_match_candidates
from mcp_server.tools.search_child_records import search_child_records
from mcp_server.tools.search_support import search_support
from mcp_server.tools.submit_found_child_report import submit_found_child_report
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport
from schemas.location import Location

# ── Tool 1: search_child_records ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_child_records_with_criteria():
    criteria = ChildSearchCriteria(gender="male", age=AgeRange(exact=6), last_seen_location="Liberty")
    res = await search_child_records(criteria)
    assert res.total_candidates >= 1
    assert len(res.candidates) >= 1
    assert res.candidates[0].gender == "male"
    assert res.truncated is False
    assert "gender=male" in res.search_summary


@pytest.mark.asyncio
async def test_search_child_records_empty_criteria():
    criteria = ChildSearchCriteria()
    res = await search_child_records(criteria)
    assert res.total_candidates == 0
    assert len(res.candidates) == 0
    assert res.truncated is False


# ── Tool 2: image_match_candidates ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_image_match_candidates_valid():
    res = await image_match_candidates(
        media_id="media-sec-001",
        candidate_case_ids=["case-101", "case-102"],
    )
    assert res.query_media_id == "media-sec-001"
    assert res.candidates_searched == 2
    assert len(res.matches) == 2
    assert res.matches[0].similarity_score >= res.matches[1].similarity_score


@pytest.mark.asyncio
async def test_image_match_candidates_empty_pool():
    res = await image_match_candidates(media_id="media-sec-001", candidate_case_ids=[])
    assert res.candidates_searched == 0
    assert len(res.matches) == 0


@pytest.mark.asyncio
async def test_image_match_candidates_empty_media_id():
    res = await image_match_candidates(media_id="", candidate_case_ids=["case-101"])
    assert res.candidates_searched == 0
    assert len(res.matches) == 0


# ── Tool 3: submit_found_child_report ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_found_child_report_success():
    report = FoundChildReport(
        gender="female",
        found_location="G-9 Markaz Islamabad",
        clothing_description="Red sweater and white shoes",
    )
    res = await submit_found_child_report(report)
    assert res.case_reference.startswith("WF-FOUND-")
    assert res.submitted_at is not None
    assert "Stay with the child" in res.guidance
    assert len(res.next_steps) > 0


@pytest.mark.asyncio
async def test_submit_found_child_report_missing_location():
    report = FoundChildReport(found_location="")
    with pytest.raises(ValueError, match="found_location is required"):
        await submit_found_child_report(report)


# ── Tool 4: search_support ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_support_all():
    loc = Location(label="Lahore")
    res = await search_support(location=loc)
    assert res.total_found >= 2
    assert res.query_location_label == "Lahore"


@pytest.mark.asyncio
async def test_search_support_filtered_shelter():
    loc = Location(label="Karachi")
    res = await search_support(location=loc, support_type="shelter")
    assert all(loc_item.support_type == "shelter" for loc_item in res.locations)


@pytest.mark.asyncio
async def test_search_support_filtered_police():
    loc = Location(label="Rawalpindi")
    res = await search_support(location=loc, support_type="police")
    assert all(loc_item.support_type == "police" for loc_item in res.locations)


# ── Tool 5: get_guidance ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_guidance_found_child():
    res = await get_guidance(query="I found a lost child", topic="found_child")
    assert "Stay with the child" in res.guidance
    assert res.topic == "found_child"
    assert res.is_static_fallback is True


@pytest.mark.asyncio
async def test_get_guidance_missing_child():
    res = await get_guidance(query="My daughter is missing", topic="missing_child")
    assert "police" in res.guidance.lower()
    assert res.topic == "missing_child"


@pytest.mark.asyncio
async def test_get_guidance_generic():
    res = await get_guidance(query="What is Wayfind?", topic=None)
    assert res.guidance
    assert len(res.next_steps) > 0


# ── Tool 6: get_case_status ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_case_status_valid():
    res = await get_case_status("WF-20260925-0042")
    assert res.case_reference == "WF-20260925-0042"
    assert res.status == "under_review"
    assert res.status_label == "Under Review"
    assert res.public_message
    assert len(res.next_steps) > 0
