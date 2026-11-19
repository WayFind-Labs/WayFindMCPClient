"""
mcp_server/tools/get_case_status.py
FastMCP Tool 6: get_case_status

Internal status tool retained for later activation. It requires a real
downstream result and never fabricates a review state.
"""

from __future__ import annotations

import logging
from schemas.case import CaseStatusResult

logger = logging.getLogger(__name__)


async def get_case_status(
    case_reference: str,
) -> CaseStatusResult:
    """Return public status of a case."""
    clean_ref = (case_reference or "").strip().upper()
    logger.info("get_case_status called for case_ref='%s'", clean_ref)

    from services.postgres_client import get_postgres_client

    client = get_postgres_client()
    if client is None:
        raise RuntimeError("Case status service is unavailable")
    return await client.get_public_case_status(case_reference=clean_ref)
