"""
mcp_server/tools/submit_found_child_report.py
FastMCP Tool 3: submit_found_child_report

Submit a complete found-child report. Returns a case reference number
and guidance on next steps. Does not cross-reference existing records.
"""

from __future__ import annotations

import logging

from schemas.case import FoundChildSubmissionResult
from schemas.child import FoundChildReport

logger = logging.getLogger(__name__)


async def submit_found_child_report(
    report: FoundChildReport,
) -> FoundChildSubmissionResult:
    """Submit a complete found-child report and return tracking reference."""
    if not report.found_location or report.found_location.strip().lower() in ("unknown", ""):
        raise ValueError("found_location is required to submit a found-child report")

    logger.info(
        "submit_found_child_report called for a report with location=%s",
        bool(report.found_location),
    )

    # 1. Try downstream PostgreSQL service client (wired in Phase 9)
    from services.postgres_client import get_postgres_client

    return await get_postgres_client().submit_found_child(report=report)
