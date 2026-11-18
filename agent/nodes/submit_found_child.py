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

The node returns a reference only from a committed gateway receipt.
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
    "Your report was recorded in Wayfind. Reference number: {ref}.\n\n"
    "This does not notify authorities or establish an official case. "
    "Please contact the appropriate local authority directly."
)
_FAILURE_MSG = (
    "We were unable to submit your report at this moment due to a technical issue. "
    "Please try again shortly or contact your local child-welfare authority directly."
)


def found_report_review_text(report: FoundChildReport) -> str:
    """Render only the finder-provided facts for review or session resume."""
    details = [f"Found near: {report.found_location}"]
    age = report.approx_age
    if age.exact is not None:
        details.append(f"Age reported: {age.exact}")
    elif age.min is not None or age.max is not None:
        details.append(f"Approximate age: {age.min if age.min is not None else '?'}–{age.max if age.max is not None else '?'}")
    if report.gender:
        details.append(f"Gender reported: {report.gender}")
    if report.hair_color:
        details.append(f"Hair: {report.hair_color}")
    if report.height.min_cm is not None or report.height.max_cm is not None:
        details.append(f"Approximate height (cm): {report.height.min_cm if report.height.min_cm is not None else '?'}–{report.height.max_cm if report.height.max_cm is not None else '?'}")
    if report.clothing:
        details.append(f"Clothing: {', '.join(report.clothing)}")
    if report.identifying_features:
        details.append(f"Visible features: {', '.join(report.identifying_features)}")
    if report.found_at:
        details.append(f"Found at: {report.found_at}")
    if report.current_circumstances:
        details.append(f"Current situation: {report.current_circumstances}")
    if report.authorities_contacted is not None:
        details.append(f"Authorities contacted: {'yes' if report.authorities_contacted else 'no'}")
    if report.reporter_contact:
        details.append(f"Your contact: {report.reporter_contact}")
    if report.reporter_name:
        details.append(f"Your name: {report.reporter_name}")
    if report.jurisdiction:
        details.append(f"Area reported: {report.jurisdiction}")
    if report.description:
        details.append(f"Other details: {report.description}")
    return "Please review this report before recording it. You can correct details in chat.\n" + "\n".join(details)


async def submit_found_child(state: WayfindState) -> dict:
    """Submit the found-child report and emit a submission_complete event."""
    existing_events = state.get("agent_events", [])
    report = state.get("found_child_report")

    # A follow-up such as “thank you” can re-enter this node while the graph
    # still carries the completed report. Never create a second case reference.
    existing_reference = state.get("case_reference")
    if existing_reference:
        saved_report = state.get("found_child_report")
        submitted_at = (
            saved_report.get("received_at") if isinstance(saved_report, dict)
            else getattr(saved_report, "received_at", None)
        )
        return {
            "agent_events": existing_events + [
                {"type": "submission_complete", "record_id": existing_reference, "submitted_at": submitted_at, "schema_version": "FoundChildIntakeV1"},
                {"type": "assistant_message", "content": f"Your report is already recorded. Reference number: {existing_reference}."}
            ]
        }

    if report is None:
        logger.error("Session %s: submit_found_child called with no report", state.get("session_id"))
        return {
            "agent_events": existing_events + [
                {"type": "error", "message": _FAILURE_MSG}
            ],
            "errors": state.get("errors", []) + ["submit_found_child: no report in state"],
        }

    if not state.get("submission_confirmed"):
        if isinstance(report, dict):
            report = FoundChildReport(**report)
        return {
            "agent_events": existing_events + [{
                "type": "request_confirmation",
                "content": found_report_review_text(report),
                "draft_id": state.get("found_draft_id"),
            }],
        }

    mcp = get_mcp_client()

    if mcp is not None:
        try:
            if isinstance(report, dict):
                report = FoundChildReport(**report)
            if not report.submission_id:
                report = report.model_copy(update={
                    "submission_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"wayfind-found:{state.get('session_id', '')}:{state.get('found_draft_id') or 'legacy'}"))
                })
            result = await mcp.submit_found_child_report(report=report)
            case_ref = result.case_reference
            submitted_at = result.submitted_at if isinstance(result.submitted_at, str) else None
            logger.info("Session %s: report submitted, case_reference=%s", state.get("session_id"), case_ref)
            return {
                "case_reference": case_ref,
                "found_child_report": report.model_copy(update={"received_at": submitted_at}),
                "agent_events":   existing_events + [
                    {"type": "submission_complete", "record_id": case_ref, "submitted_at": submitted_at, "schema_version": "FoundChildIntakeV1"},
                    {"type": "assistant_message", "content": _SUCCESS_MSG.format(ref=case_ref)},
                ],
            }
        except Exception as exc:
            logger.error("submit_found_child MCP call failed: %s", exc)
            return {
                "agent_events":  existing_events + [{"type": "error", "message": _FAILURE_MSG}],
                "submission_confirmed": False,
                "tool_failures": state.get("tool_failures", []) + [_TOOL_NAME],
                "errors":        state.get("errors", []) + [str(exc)],
            }

    logger.error("Session %s: found-child submission unavailable: MCP client missing", state.get("session_id"))
    return {
        "agent_events": existing_events + [{"type": "error", "message": _FAILURE_MSG}],
        "submission_confirmed": False,
        "tool_failures": state.get("tool_failures", []) + [_TOOL_NAME],
        "errors": state.get("errors", []) + ["submit_found_child: MCP client unavailable"],
    }
