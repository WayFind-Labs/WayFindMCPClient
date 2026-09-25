"""
schemas/
Shared Pydantic v2 models used by every layer:
LangGraph nodes, MCP Client, FastMCP tools, and service clients.

Import from here so import paths stay stable as the package grows.
"""

from schemas.candidates import Candidate, CandidateSearchResult
from schemas.case import CaseStatusResult, FoundChildSubmissionResult
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport, HeightRange
from schemas.evidence import ConfidenceTier, MatchEvidence
from schemas.guidance import GuidanceResult, GuidanceSource
from schemas.image import ImageMatch, ImageMatchResult
from schemas.location import Location
from schemas.review import HumanReviewSubmission
from schemas.support import SupportLocation, SupportResult

__all__ = [
    # child
    "AgeRange",
    "HeightRange",
    "ChildSearchCriteria",
    "FoundChildReport",
    # location
    "Location",
    # evidence
    "ConfidenceTier",
    "MatchEvidence",
    # candidates
    "Candidate",
    "CandidateSearchResult",
    # image
    "ImageMatch",
    "ImageMatchResult",
    # support
    "SupportLocation",
    "SupportResult",
    # guidance
    "GuidanceSource",
    "GuidanceResult",
    # case
    "CaseStatusResult",
    "FoundChildSubmissionResult",
    # review
    "HumanReviewSubmission",
]
