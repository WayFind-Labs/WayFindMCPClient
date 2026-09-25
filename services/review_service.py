"""
services/review_service.py
Internal human review queue submission service client.

This service is called by the `human_review` LangGraph node when a candidate
match is classified as UNCERTAIN or HIGH confidence.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

import httpx

from app.config import get_settings
from schemas.evidence import ConfidenceTier, MatchEvidence
from schemas.review import HumanReviewSubmission

logger = logging.getLogger(__name__)


class ReviewService:
    """Async client for the internal Human Review queue."""

    def __init__(self, base_url: str = "", timeout: float = 10.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def submit(
        self,
        candidate_case_ids: list[str],
        evidence: MatchEvidence,
        session_id: str,
        priority: bool = False,
        evidence_package: dict[str, Any] | None = None,
    ) -> HumanReviewSubmission:
        """Submit candidate match with full evidence package for staff review."""
        review_id = f"REV-{uuid.uuid4().hex[:8].upper()}"
        session_prefix = (session_id or "ANON")[:8].upper()
        case_ref = f"WF-{session_prefix}-{uuid.uuid4().hex[:4].upper()}"
        now_iso = datetime.now(UTC).isoformat()
        tier = evidence.confidence_tier if hasattr(evidence, "confidence_tier") else (
            ConfidenceTier.HIGH if priority else ConfidenceTier.UNCERTAIN
        )

        payload = {
            "review_id": review_id,
            "case_reference": case_ref,
            "confidence_tier": tier.value if hasattr(tier, "value") else str(tier),
            "candidate_case_ids": candidate_case_ids,
            "evidence": evidence.model_dump(exclude_none=True),
            "session_id": session_id,
            "priority": priority,
            "evidence_package": evidence_package or {},
        }

        if self.base_url:
            try:
                client = self._get_client()
                response = await client.post(
                    "/api/reviews/submit",
                    json=payload,
                )
                if response.status_code in (200, 201):
                    return HumanReviewSubmission.model_validate(response.json())
            except Exception as exc:
                logger.warning("ReviewService submit failed over HTTP: %s", exc)

        logger.info(
            "Review submitted (mock): review_id=%s, case_ref=%s, tier=%s, priority=%s",
            review_id,
            case_ref,
            tier,
            priority,
        )

        return HumanReviewSubmission(
            review_id=review_id,
            case_reference=case_ref,
            confidence_tier=tier,
            candidate_case_ids=candidate_case_ids,
            evidence=evidence,
            session_id=session_id,
            submitted_at=now_iso,
            estimated_review_hours=2 if priority else 6,
        )


@lru_cache(maxsize=1)
def get_review_service() -> ReviewService:
    """Return singleton ReviewService configured from settings."""
    settings = get_settings()
    url = getattr(settings, "review_service_url", "")
    return ReviewService(base_url=url)
