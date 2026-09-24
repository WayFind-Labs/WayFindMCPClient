"""
app/routes/agent.py
POST /api/agent — the single public endpoint consumed by the Wayfind PWA.

Contract (agreed with frontend):
  Request:   POST /api/agent
             Header: X-Session-ID: <uuid>  (omit on first turn)
             Body:   { "prompt": string }

  Response:  { "message": string, "metadata": {} }
             Header: X-Session-ID: <uuid>   (always present — same or new)

Session lifecycle:
  - If X-Session-ID is missing or unknown → create a new session
  - If X-Session-ID matches a stored session → load and continue
  - Session is saved after every turn regardless of outcome

Rate limiting:
  - Tracked per session_id using a sliding window in the session store
  - Returns HTTP 429 if the session exceeds rate_limit_requests_per_minute

Security:
  - Internal WayfindState is never serialised into the response body
  - Stack traces are never returned to the client
  - All errors return the generic safe message defined in SAFE_ERROR_MESSAGE
"""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.session import SessionStore

logger = logging.getLogger(__name__)

router = APIRouter()

SAFE_ERROR_MESSAGE = "Something went wrong. Please try again."


# ── Request / Response models ──────────────────────────────────────────────────

class AgentRequest(BaseModel):
    """Body of POST /api/agent."""

    prompt: str = Field(
        min_length=1,
        max_length=4000,
        description="The user's natural-language message.",
    )


class AgentResponse(BaseModel):
    """Body of the response from POST /api/agent."""

    message: str = Field(description="Natural-language reply to show the user.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional structured metadata (never contains PII or internal state).",
    )


# ── Dependency injection ───────────────────────────────────────────────────────

def get_session_store(request: Request) -> SessionStore:
    """Retrieve the session store attached to app.state at startup."""
    return request.app.state.session_store  # type: ignore[no-any-return]


# ── Rate limiting helper ───────────────────────────────────────────────────────

async def _check_rate_limit(
    session_id: str,
    store: SessionStore,
    settings: Settings,
) -> None:
    """Sliding-window rate limiter keyed to session_id.

    Stores a list of request timestamps under a special key in the session store.
    Raises HTTP 429 if the window limit is exceeded.
    """
    rate_key = f"__rate__{session_id}"
    now = time.time()
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_requests_per_minute

    raw: dict[str, Any] | None = await store.get(rate_key)
    timestamps: list[float] = raw.get("timestamps", []) if raw else []

    # Prune timestamps outside the current window
    timestamps = [t for t in timestamps if now - t < window]

    if len(timestamps) >= limit:
        logger.warning("Rate limit exceeded for session %s", session_id)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please wait before sending another message.",
        )

    timestamps.append(now)
    await store.set(rate_key, {"timestamps": timestamps})


# ── Route ──────────────────────────────────────────────────────────────────────

@router.post(
    "/agent",
    response_model=AgentResponse,
    summary="Send a prompt to the Wayfind agent",
    responses={
        200: {"description": "Agent response with natural-language message"},
        422: {"description": "Invalid request body"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error (safe message only)"},
    },
)
async def agent_endpoint(
    body: AgentRequest,
    request: Request,
    x_session_id: Annotated[str | None, Header()] = None,
    store: SessionStore = Depends(get_session_store),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    """Main agent endpoint.

    Steps:
      1. Resolve or create session ID
      2. Rate-limit check
      3. Load existing WayfindState from session (or build initial state)
      4. Merge new prompt into state
      5. Run LangGraph graph  ← wired in Phase 11
      6. Save updated state to session
      7. Return { message, metadata }
    """
    # ── 1. Resolve session ─────────────────────────────────────────────────────
    is_new_session = False
    if x_session_id:
        session_id = x_session_id
        existing = await store.get(session_id)
        if existing is None:
            # Unknown session ID — treat as new (don't reveal this to the client)
            logger.info("Unknown session ID %s — starting new session", session_id)
            session_id = store.new_session_id()
            is_new_session = True
    else:
        session_id = store.new_session_id()
        is_new_session = True
        logger.info("New session started: %s", session_id)

    # ── 2. Rate limit ──────────────────────────────────────────────────────────
    await _check_rate_limit(session_id, store, settings)

    # ── 3. Load or initialise state ────────────────────────────────────────────
    raw_state: dict[str, Any] | None = await store.get(session_id) if not is_new_session else None

    state: dict[str, Any] = raw_state or _initial_state(session_id)

    # ── 4. Merge new prompt into state ─────────────────────────────────────────
    state["user_prompt"] = body.prompt
    state["turn_count"] = state.get("turn_count", 0) + 1
    state["conversation_history"] = state.get("conversation_history", []) + [
        {"role": "user", "content": body.prompt}
    ]

    # ── 5. Run LangGraph graph ─────────────────────────────────────────────────
    # NOTE: Graph runner is wired in Phase 11.
    # Until then, return a placeholder so the endpoint is testable end-to-end.
    try:
        graph_runner = getattr(request.app.state, "graph_runner", None)
        if graph_runner is not None:
            state = await graph_runner(state)
        else:
            # Phase 3 placeholder — replaced once agent/ is wired up
            state["final_response"] = (
                "Agent graph not yet initialised. "
                "This message will be replaced in Phase 11."
            )
    except Exception as exc:
        logger.exception("LangGraph execution error for session %s", session_id)
        # Persist whatever partial state we have so the session isn't lost
        await store.set(session_id, _serialise_state(state))
        return _error_response(session_id)

    # ── 6. Persist updated state ───────────────────────────────────────────────
    await store.set(session_id, _serialise_state(state))

    # ── 7. Build response ──────────────────────────────────────────────────────
    message: str = state.get("final_response") or SAFE_ERROR_MESSAGE

    response_body = AgentResponse(message=message, metadata={})

    response = JSONResponse(content=response_body.model_dump())
    response.headers["X-Session-ID"] = session_id
    return response


# ── Helpers ────────────────────────────────────────────────────────────────────

def _initial_state(session_id: str) -> dict[str, Any]:
    """Build a blank WayfindState-shaped dict for a new session.

    Full TypedDict is defined in agent/state.py (Phase 4).
    We use a plain dict here so app/ has no import dependency on agent/.
    """
    return {
        "session_id": session_id,
        "user_prompt": "",
        "conversation_history": [],
        "turn_count": 0,
        "intent": None,
        "intent_confidence": None,
        "child_search_criteria": None,
        "found_child_report": None,
        "missing_information": [],
        "followup_question": None,
        "user_location": None,
        "media_reference": None,
        "candidate_ids": [],
        "candidate_count": 0,
        "image_match_results": [],
        "match_evidence": None,
        "confidence_tier": None,
        "image_search_warranted": False,
        "review_required": False,
        "case_reference": None,
        "final_response": None,
        "errors": [],
        "tool_failures": [],
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


def _error_response(session_id: str) -> JSONResponse:
    """Return the safe generic error message, preserving session ID."""
    response = JSONResponse(
        content=AgentResponse(message=SAFE_ERROR_MESSAGE, metadata={}).model_dump(),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
    response.headers["X-Session-ID"] = session_id
    return response
