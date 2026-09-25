"""
agent/nodes/get_case_status.py
Node: get_case_status_node

Responsibility:
  Returns the public-facing status of a previously submitted report using the
  get_case_status MCP tool.

  Security rules:
    - Returns ONLY public-safe status fields (no staff notes, no match scores,
      no candidate details, no internal case data)
    - Never confirms or denies that a match exists — only reflects the
      submission status

Inputs consumed:
  state.case_reference

Outputs produced:
  agent_events — assistant_message with status text appended

Phase 5 status: STUB — returns placeholder status until MCP wired in Phase 6.
"""

from __future__ import annotations

import logging

from agent.dependencies import get_mcp_client
from agent.state import WayfindState

logger = logging.getLogger(__name__)

_NO_REF_MSG = (
    "I couldn't find a case reference in your message. "
    "Your reference number looks like WF-XXXXXXXX-XXXX. "
    "Could you provide it so I can check your case status?"
)
_NOT_FOUND_MSG = (
    "We couldn't find a case matching that reference number. "
    "Please double-check the reference and try again."
)


async def get_case_status_node(state: WayfindState) -> dict:
    """Look up and emit the public case status."""
    existing_events = state.get("agent_events", [])
    case_reference  = state.get("case_reference")

    if not case_reference:
        logger.info("Session %s: get_case_status — no case_reference in state", state.get("session_id"))
        return {
            "agent_events": existing_events + [
                {"type": "assistant_message", "content": _NO_REF_MSG},
                {"type": "request_information", "fields": ["case_reference"]},
            ]
        }

    mcp = get_mcp_client()

    if mcp is not None:
        try:
            result = await mcp.get_case_status(case_reference=case_reference)
            status_text = (
                f"Case {case_reference}: {result.status_label}.\n"
                f"{result.public_message}"
            )
            return {
                "agent_events": existing_events + [
                    {"type": "assistant_message", "content": status_text}
                ]
            }
        except Exception as exc:
            logger.error("get_case_status MCP call failed: %s", exc)
            return {
                "agent_events":  existing_events + [
                    {"type": "assistant_message", "content": _NOT_FOUND_MSG}
                ],
                "tool_failures": state.get("tool_failures", []) + ["get_case_status"],
                "errors":        state.get("errors", []) + [str(exc)],
            }

    # ── Phase 5 stub ──────────────────────────────────────────────────────────
    logger.info("Session %s: get_case_status_node STUB for ref=%s", state.get("session_id"), case_reference)
    stub_msg = (
        f"Case {case_reference}: Under Review.\n"
        "Your report has been received and is being reviewed by our team. "
        "We will follow up if a match is found."
    )
    return {
        "agent_events": existing_events + [
            {"type": "assistant_message", "content": stub_msg}
        ]
    }
