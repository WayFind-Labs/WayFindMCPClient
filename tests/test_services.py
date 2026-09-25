"""
tests/test_services.py
Unit tests for downstream service clients (Phase 9).
"""

import pytest

from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport
from schemas.evidence import ConfidenceTier, MatchEvidence
from schemas.location import Location
from services.image_backend_client import ImageBackendClient, get_image_backend_client
from services.media_service import MediaService, get_media_service
from services.postgres_client import PostgresClient, get_postgres_client
from services.rag_client import RagClient, get_rag_client
from services.review_service import ReviewService, get_review_service
from services.support_client import SupportClient, get_support_client

# ── PostgresClient Tests ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_postgres_client_search_and_submit():
    client = PostgresClient()
    criteria = ChildSearchCriteria(gender="female", age=AgeRange(exact=8))
    search_res = await client.search_children(criteria=criteria, max_results=10)
    assert search_res.total_candidates >= 1
    assert search_res.candidates[0].gender == "female"

    report = FoundChildReport(gender="male", found_location="Lahore Railway Station")
    submit_res = await client.submit_found_child(report)
    assert submit_res.case_reference.startswith("WF-FOUND-")

    status_res = await client.get_public_case_status(submit_res.case_reference)
    assert status_res.case_reference == submit_res.case_reference
    assert status_res.status == "under_review"
    await client.close()


# ── RagClient Tests ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rag_client_query():
    client = RagClient()
    res = await client.query(query="What is the missing child procedure?", topic="missing_child")
    assert res.guidance
    assert res.topic == "missing_child"
    assert res.is_static_fallback is True
    await client.close()


# ── ImageBackendClient Tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_image_backend_client_compare():
    client = ImageBackendClient()
    res = await client.compare(media_id="media-001", candidate_case_ids=["case-1", "case-2"])
    assert res.candidates_searched == 2
    assert len(res.matches) == 2
    assert res.matches[0].similarity_score >= res.matches[1].similarity_score
    await client.close()


# ── SupportClient Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_support_client_search():
    client = SupportClient()
    loc = Location(label="Karachi")
    res = await client.search(location=loc, support_type="shelter")
    assert len(res.locations) >= 1
    assert all(item.support_type == "shelter" for item in res.locations)
    await client.close()


# ── MediaService Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_media_service_scan_and_store():
    service = MediaService()
    scan = await service.safety_scan(b"fake-image-bytes", mime_type="image/jpeg")
    assert scan["safe"] is True

    media_id = await service.store(b"fake-image-bytes", mime_type="image/jpeg")
    assert media_id.startswith("media-")
    await service.close()


# ── ReviewService Tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_service_submit():
    service = ReviewService()
    evidence = MatchEvidence(
        candidate_case_id="case-101",
        metadata_score=0.85,
        composite_score=0.88,
        confidence_tier=ConfidenceTier.HIGH,
        supporting_factors=["Matching age and gender", "High facial similarity"],
    )
    submission = await service.submit(
        candidate_case_ids=["case-101"],
        evidence=evidence,
        session_id="session-test-001",
        priority=True,
    )
    assert submission.review_id.startswith("REV-")
    assert submission.case_reference.startswith("WF-")
    assert submission.confidence_tier == ConfidenceTier.HIGH
    assert submission.estimated_review_hours == 2
    await service.close()


# ── Singletons Test ───────────────────────────────────────────────────────────

def test_singleton_getters():
    assert get_postgres_client() is not None
    assert get_rag_client() is not None
    assert get_image_backend_client() is not None
    assert get_support_client() is not None
    assert get_media_service() is not None
    assert get_review_service() is not None
