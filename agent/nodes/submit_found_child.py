"""
agent/nodes/submit_found_child.py
Node: submit_found_child

Responsibility:
  Submits the completed FoundChildReport via the submit_found_child_report
  MCP tool. Returns a case_reference and next-steps message.

  Safe language rules:
    - Never cross-reference this with existing records here
    - Never imply the child has been identified
    - Always provide the case_reference for follow-up

Inputs consumed:
  state.found_child_report

Outputs produced:
  case_reference — reference ID from submission
  agent_events   — submission_complete + assistant_message events appended
  tool_failures  — appended on failure
  errors         — appended on failure

Phase 5 status: STUB — generates fake case_reference until MCP wired in Phase 6.
"""

from __future__ import annotations

import logging
import uuid

from agent.dependencies import get_mcp_client
from agent.state import WayfindState
from schemas.child import FoundChildReport

logger = logging.getLogger(__name__)

_TOOL_NAME = "submit_found_child_report"
_SUCCESS_MSG = (
    "Your report has been submitted. Reference number: {ref}.\n\n"
    "Our team will review the details and follow up if a match is found in our records. "
    "Please keep the child safe and in contact with local authorities."
)
_FAILURE_MSG = (
    "We were unable to submit your report at this moment due to a technical issue. "
    "Please try again shortly or contact your local child-welfare authority directly."
)


async def submit_found_child(state: WayfindState) -> dict:
    """Submit the found-child report and emit a submission_complete event."""
    existing_events = state.get("agent_events", [])
    report = state.get("found_child_report")

    if report is None:
        logger.error("Session %s: submit_found_child called with no report", state.get("session_id"))
        return {
            "agent_events": existing_events + [
                {"type": "error", "message": _FAILURE_MSG}
            ],
            "errors": state.get("errors", []) + ["submit_found_child: no report in state"],
        }

    mcp = get_mcp_client()

    if mcp is not None:
        try:
            if isinstance(report, dict):
                report = FoundChildReport(**report)
            result = await mcp.submit_found_child_report(report=report)
            case_ref = result.case_reference
            logger.info("Session %s: report submitted, case_reference=%s", state.get("session_id"), case_ref)
            return {
                "case_reference": case_ref,
                "agent_events":   existing_events + [
                    {"type": "submission_complete", "record_id": case_ref},
                    {"type": "assistant_message", "content": _SUCCESS_MSG.format(ref=case_ref)},
                ],
            }
        except Exception as exc:
            logger.error("submit_found_child MCP call failed: %s", exc)
            return {
                "agent_events":  existing_events + [{"type": "error", "message": _FAILURE_MSG}],
                "tool_failures": state.get("tool_failures", []) + [_TOOL_NAME],
                "errors":        state.get("errors", []) + [str(exc)],
            }

    # ── Phase 5 stub ──────────────────────────────────────────────────────────
    case_ref = f"WF-FOUND-{uuid.uuid4().hex[:8].upper()}"
    logger.info("Session %s: submit_found_child STUB — case_reference=%s", state.get("session_id"), case_ref)
    return {
        "case_reference": case_ref,
        "agent_events":   existing_events + [
            {"type": "submission_complete", "record_id": case_ref},
            {"type": "assistant_message", "content": _SUCCESS_MSG.format(ref=case_ref)},
        ],
    }
