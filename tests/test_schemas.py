"""
tests/test_schemas.py
Unit tests for all Pydantic schemas in the schemas/ package (Phase 15).

Verifies serialization, deserialization, optional field handling,
validation rules, and defaults across all domain models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.candidates import Candidate, CandidateSearchResult
from schemas.case import CaseStatusResult
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport, HeightRange
from schemas.evidence import ConfidenceTier, MatchEvidence
from schemas.event import AgentEvent, IncomingEvent, InternalRequest
from schemas.guidance import GuidanceResult, GuidanceSource
from schemas.image import ImageMatch, ImageMatchResult
from schemas.location import Location
from schemas.review import HumanReviewSubmission
from schemas.support import SupportLocation, SupportResult


def test_child_search_criteria_schema():
    """Test ChildSearchCriteria instantiation and defaults."""
    criteria = ChildSearchCriteria()
    assert criteria.gender is None
    assert criteria.clothing == []
    assert criteria.identifying_features == []

    # Partial populated
    c2 = ChildSearchCriteria(
        age=AgeRange(exact=7, min=6, max=8),
        gender="female",
        height=HeightRange(min_cm=110.0, max_cm=130.0),
        last_seen_location="Gulberg",
        clothing=["blue dress"],
    )
    assert c2.gender == "female"
    assert c2.age.exact == 7
    assert c2.height.min_cm == 110.0

    # Serialization / deserialization roundtrip
    dumped = c2.model_dump()
    loaded = ChildSearchCriteria(**dumped)
    assert loaded == c2


def test_found_child_report_schema():
    """Test FoundChildReport schema and validation."""
    report = FoundChildReport(
        found_location="Liberty Market",
        gender="male",
        approx_age=AgeRange(exact=4),
        media_reference="media-uuid-1",
    )
    assert report.found_location == "Liberty Market"
    assert report.gender == "male"
    assert report.media_reference == "media-uuid-1"

    dumped = report.model_dump()
    loaded = FoundChildReport(**dumped)
    assert loaded == report


def test_candidate_and_search_result_schema():
    """Test Candidate and CandidateSearchResult schemas."""
    cand = Candidate(
        case_id="CASE-101",
        age_at_intake=8,
        gender="male",
        height_cm=125.0,
        metadata_match_score=0.85,
        thumbnail_available=True,
    )
    assert cand.case_id == "CASE-101"
    assert cand.metadata_match_score == 0.85

    search_res = CandidateSearchResult(
        candidates=[cand],
        total_candidates=1,
        search_summary="Searched 8yo male",
        truncated=False,
    )
    assert len(search_res.candidates) == 1
    assert search_res.total_candidates == 1


def test_evidence_and_confidence_tier_schema():
    """Test MatchEvidence schema and ConfidenceTier enum."""
    evidence = MatchEvidence(
        candidate_case_id="CASE-202",
        metadata_score=0.75,
        image_similarity=0.82,
        geographic_score=0.9,
        temporal_score=0.6,
        composite_score=0.785,
        supporting_factors=["Strong physical match", "Similar face"],
        conflicting_factors=[],
    )
    assert evidence.candidate_case_id == "CASE-202"
    assert evidence.composite_score == 0.785

    assert ConfidenceTier.HIGH.value == "high"
    assert ConfidenceTier.UNCERTAIN.value == "uncertain"
    assert ConfidenceTier.LOW.value == "low"


def test_image_match_schema():
    """Test ImageMatch and ImageMatchResult schemas."""
    match = ImageMatch(
        candidate_case_id="CASE-303",
        similarity_score=0.91,
        confidence="high",
        matched_features=["eyes", "hair"],
        model_version="1.0",
    )
    res = ImageMatchResult(
        matches=[match],
        query_media_id="media-123",
        candidates_searched=1,
    )
    assert len(res.matches) == 1
    assert res.matches[0].similarity_score == 0.91


def test_event_schemas():
    """Test IncomingEvent, InternalRequest, and AgentEvent schemas."""
    inc = IncomingEvent(
        type="user_message",
        content="Looking for lost boy",
    )
    req = InternalRequest(event=inc)
    assert req.event.type == "user_message"

    agent_event = AgentEvent(
        type="review_pending",
        case_reference="WF-2026-9999",
    )
    assert agent_event.type == "review_pending"
    assert agent_event.case_reference == "WF-2026-9999"

    # Verify JSON exclusion of None
    dumped = agent_event.model_dump(exclude_none=True)
    assert "case_reference" in dumped
    assert "content" not in dumped


def test_location_and_support_schemas():
    """Test Location and SupportResult schemas."""
    loc = Location(
        label="Johar Town, Lahore",
        city="Lahore",
        latitude=31.4697,
        longitude=74.2728,
    )
    assert loc.label == "Johar Town, Lahore"

    sup_loc = SupportLocation(
        name="CPWB Shelter",
        address="Lahore",
        support_type="shelter",
        phone="1121",
    )
    sup_res = SupportResult(
        locations=[sup_loc],
        total_found=1,
        query_location_label="Lahore",
    )
    assert sup_res.total_found == 1
    assert sup_res.locations[0].name == "CPWB Shelter"


def test_guidance_and_case_status_schemas():
    """Test GuidanceResult and CaseStatusResult schemas."""
    guidance = GuidanceResult(
        guidance="Stay with the child.",
        next_steps=["Call police"],
        topic="found_child",
    )
    assert guidance.guidance == "Stay with the child."
    assert guidance.guidance_text == "Stay with the child."

    status = CaseStatusResult(
        case_reference="WF-2026-0001",
        status="under_review",
        public_message="Being processed",
    )
    assert status.case_reference == "WF-2026-0001"
    assert status.status == "under_review"
