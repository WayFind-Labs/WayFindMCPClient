"""
app/routes/agent.py
Internal event endpoint — POST /internal/sessions/{session_id}/events

Contract (v2 — internal only, called by ShelterAppUiBackend):

  Request:   POST /internal/sessions/{session_id}/events
             Header: X-Internal-Key: <shared secret>
             Body:   {
                       "event": {
                         "type":      "user_message" | "user_image" | "user_form_response",
                         "content":   "string | null",
                         "media_id":  "string | null",
                         "form_data": {} | null
                       }
                     }

  Response:  JSON array of AgentEvent objects, e.g.:
             [
               { "type": "assistant_message", "content": "..." },
               { "type": "request_information", "fields": ["age", "location"] },
               { "type": "search_started" },
               { "type": "review_pending", "case_reference": "WF-..." }
             ]

Session lifecycle:
  - session_id is owned and managed by ShelterAppUiBackend
  - This service stores WayfindState keyed by session_id
  - State is loaded, updated, and saved on every call
  - If session_id is unknown, a fresh WayfindState is created

Security:
  - X-Internal-Key auth is enforced by middleware in app/main.py
  - Internal WayfindState is never returned to the caller
  - All errors produce a safe AgentEvent(type="error", message=...)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.session import SessionStore

logger = logging.getLogger(__name__)

router = APIRouter()

SAFE_ERROR_EVENT = {"type": "error", "message": "Something went wrong. Please try again."}


# ── Request / Response models ──────────────────────────────────────────────────

class IncomingEvent(BaseModel):
    """A single event sent by ShelterAppUiBackend on behalf of the user."""

    type: str = Field(
        description="Event type: user_message | user_image | user_form_response",
    )
    content: str | None = Field(
        default=None,
        max_length=4000,
        description="User's text content. Required for user_message.",
    )
    media_id: str | None = Field(
        default=None,
        description=(
            "Opaque media ID issued by ShelterAppUiBackend after safety scan and storage. "
            "Never a raw file path or object-storage URL."
        ),
    )
    form_data: dict[str, Any] | None = Field(
        default=None,
        description="Structured follow-up form answers keyed by field name.",
    )


class InternalRequest(BaseModel):
    """Body of POST /internal/sessions/{session_id}/events."""

    event: IncomingEvent


class AgentEvent(BaseModel):
    """A single output event produced by the agent, returned to ShelterAppUiBackend."""

    type: str
    content: str | None = None
    fields: list[str] | None = None          # request_information
    message: str | None = None               # request_image | error
    results: list[dict[str, Any]] | None = None  # search_results
    record_id: str | None = None             # submission_complete
    case_reference: str | None = None        # review_pending


# ── Dependency injection ───────────────────────────────────────────────────────

def get_session_store(request: Request) -> SessionStore:
    """Retrieve the session store attached to app.state at startup."""
    return request.app.state.session_store  # type: ignore[no-any-return]


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post(
    "/sessions/{session_id}/events",
    response_model=list[AgentEvent],
    summary="Send a user event to the Wayfind agent",
    responses={
        200: {"description": "List of agent events produced by this turn"},
        400: {"description": "Invalid event type or missing required fields"},
        403: {"description": "Invalid or missing X-Internal-Key"},
        500: {"description": "Internal server error (safe error event returned)"},
    },
)
async def handle_event(
    session_id: str,
    body: InternalRequest,
    request: Request,
) -> JSONResponse:
    """Internal agent event handler.

    Steps:
      1. Load existing WayfindState for session_id (or create fresh state)
      2. Merge incoming event into state
      3. Run LangGraph graph  ← wired in Phase 11
      4. Collect agent_events from resulting state
      5. Save updated state to session store
      6. Return list[AgentEvent]
    """
    store: SessionStore = get_session_store(request)

    # ── 1. Load or initialise state ────────────────────────────────────────────
    raw_state: dict[str, Any] | None = await store.get(session_id)
    is_new = raw_state is None

    if is_new:
        logger.info("New agent session: %s", session_id)

    state: dict[str, Any] = raw_state or _initial_state(session_id)

    # ── 2. Merge incoming event into state ─────────────────────────────────────
    event = body.event
    state = _merge_event(state, event)

    # ── 3. Run LangGraph graph ─────────────────────────────────────────────────
    # NOTE: Graph runner is wired in Phase 11.
    # Until then, return a placeholder so the endpoint is testable end-to-end.
    try:
        graph_runner = getattr(request.app.state, "graph_runner", None)
        if graph_runner is not None:
            state = await graph_runner(state)
        else:
            # Phase 3 placeholder — replaced once agent/ is wired up (Phase 11)
            state["agent_events"] = [
                {
                    "type": "assistant_message",
                    "content": (
                        "Agent graph not yet initialised. "
                        "This message will be replaced in Phase 11."
                    ),
                }
            ]
    except Exception:
        logger.exception("LangGraph execution error for session %s", session_id)
        # Persist whatever partial state we have so the session isn't lost
        await store.set(session_id, _serialise_state(state))
        return JSONResponse(content=[SAFE_ERROR_EVENT])

    # ── 4. Collect agent events ────────────────────────────────────────────────
    raw_events: list[dict[str, Any]] = state.get("agent_events", [])

    # Fallback: if no events were produced but final_response is set, wrap it
    if not raw_events and state.get("final_response"):
        raw_events = [{"type": "assistant_message", "content": state["final_response"]}]

    if not raw_events:
        raw_events = [SAFE_ERROR_EVENT]

    # Reset agent_events for next turn (events are consumed per turn)
    state["agent_events"] = []

    # ── 5. Persist updated state ───────────────────────────────────────────────
    await store.set(session_id, _serialise_state(state))

    # ── 6. Return events ───────────────────────────────────────────────────────
    events = [AgentEvent(**e) for e in raw_events]
    return JSONResponse(content=[e.model_dump(exclude_none=True) for e in events])


# ── Helpers ────────────────────────────────────────────────────────────────────

def _merge_event(state: dict[str, Any], event: IncomingEvent) -> dict[str, Any]:
    """Merge the incoming event into WayfindState.

    - user_message:       sets user_prompt, appends to conversation_history
    - user_image:         sets media_reference from media_id
    - user_form_response: sets user_prompt from form summary, merges form_data
    """
    state["turn_count"] = state.get("turn_count", 0) + 1

    if event.type == "user_message":
        content = event.content or ""
        state["user_prompt"] = content
        state["conversation_history"] = state.get("conversation_history", []) + [
            {"role": "user", "content": content}
        ]

    elif event.type == "user_image":
        if event.media_id:
            state["media_reference"] = event.media_id
            logger.info(
                "Session %s: image attached (media_id=%s)",
                state.get("session_id"),
                event.media_id,
            )

    elif event.type == "user_form_response":
        # form_data keys are field names (e.g. "age", "clothing")
        form = event.form_data or {}
        # Build a human-readable summary for the conversation history
        summary = "; ".join(f"{k}: {v}" for k, v in form.items())
        state["user_prompt"] = summary
        state["conversation_history"] = state.get("conversation_history", []) + [
            {"role": "user", "content": summary}
        ]
        # Also store raw form data for structured extraction node
        state["last_form_data"] = form

    else:
        logger.warning(
            "Session %s: unknown event type %r — ignoring",
            state.get("session_id"),
            event.type,
        )

    return state


def _initial_state(session_id: str) -> dict[str, Any]:
    """Build a blank WayfindState-shaped dict for a new session.

    Full TypedDict is defined in agent/state.py (Phase 4).
    We use a plain dict here so app/ has no import dependency on agent/.
    """
    return {
        "session_id":              session_id,
        "user_prompt":             "",
        "conversation_history":    [],
        "turn_count":              0,
        "intent":                  None,
        "intent_confidence":       None,
        "child_search_criteria":   None,
        "found_child_report":      None,
        "missing_information":     [],
        "followup_question":       None,
        "user_location":           None,
        "media_reference":         None,
        "candidate_ids":           [],
        "candidate_count":         0,
        "image_match_results":     [],
        "match_evidence":          None,
        "confidence_tier":         None,
        "image_search_warranted":  False,
        "review_required":         False,
        "case_reference":          None,
        "final_response":          None,
        "agent_events":            [],   # v2: accumulated output events per turn
        "last_form_data":          None,
        "errors":                  [],
        "tool_failures":           [],
    }


def _serialise_state(state: dict[str, Any]) -> dict[str, Any]:
    """Prepare state for JSON serialisation into the session store.

    Pydantic model instances inside the state are converted to dicts.
    Enum values are converted to their string values.
    Unknown types fall back to str() via json.dumps default.
    """
    import json

    raw = json.dumps(state, default=_json_default)
    return json.loads(raw)  # type: ignore[no-any-return]


def _json_default(obj: Any) -> Any:
    """Custom JSON serialiser for types not handled by default."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "value"):
        return obj.value
    return str(obj)
