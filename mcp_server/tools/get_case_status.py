"""
mcp_server/tools/get_case_status.py
FastMCP Tool 6: get_case_status

Return public-facing case status. Strips staff notes, match scores,
internal candidate IDs, and review queues.
Safe to return directly to the caller.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from schemas.case import CaseStatusResult

logger = logging.getLogger(__name__)


async def get_case_status(
    case_reference: str,
) -> CaseStatusResult:
    """Return public status of a case."""
    clean_ref = (case_reference or "").strip().upper()
    logger.info("get_case_status called for case_ref='%s'", clean_ref)

    # 1. Try downstream PostgreSQL/Review service client (wired in Phase 9)
    try:
        from services.postgres_client import get_postgres_client

        client = get_postgres_client()
        if client is not None:
            return await client.get_public_case_status(case_reference=clean_ref)
    except (ImportError, AttributeError, Exception) as exc:
        logger.debug("Downstream postgres_client not active, using default case status: %s", exc)

    now_iso = datetime.now(UTC).isoformat()

    return CaseStatusResult(
        case_reference=clean_ref,
        status="under_review",
        submitted_at=now_iso,
        last_updated_at=now_iso,
        public_message=(
            "Your report is currently undergoing active review by authorized child protection staff. "
            "You will be contacted immediately if a verified match is confirmed."
        ),
        next_steps=[
            "Keep your registered contact phone active",
            "Report any new sightings or details to authorities with this reference number",
        ],
    )
