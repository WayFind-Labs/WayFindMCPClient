"""
agent/state.py
WayfindState — the single shared state TypedDict that flows through the LangGraph graph.

Design rules:
  - Every node receives the full state and returns a PARTIAL dict (only the keys it updates).
  - LangGraph merges partial updates using the reducer annotations defined here.
  - conversation_history uses add_messages so turns are appended, not replaced.
  - agent_events accumulates output events within a single turn; the route handler
    drains and resets this list before returning to ShelterAppUiBackend.
  - No field may contain PII that should reach the frontend. The route handler
    exposes only agent_events — never the raw state dict.

Field ownership by phase:
  Phase 4  — this file (all fields declared here)
  Phase 5  — nodes write to these fields
  Phase 11 — graph wires the nodes and drives state transitions
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages

from schemas.child import ChildSearchCriteria, FoundChildReport
from schemas.evidence import ConfidenceTier, MatchEvidence
from schemas.image import ImageMatch
from schemas.location import Location

# ── Intent enum ───────────────────────────────────────────────────────────────

class Intent(StrEnum):
    """Possible high-level intents detected from the user's message.

    MISSING_CHILD  — user is searching for a child they reported missing
    FOUND_CHILD    — user has found an unaccompanied child
    SHELTER_SEARCH — user wants nearby shelters or support organisations
    GUIDANCE       — user needs procedural guidance (what to do, how to report)
    CASE_STATUS    — user wants a status update on a previously submitted report
    UNKNOWN        — intent could not be determined; agent will ask for clarification
    """

    MISSING_CHILD  = "missing_child"
    FOUND_CHILD    = "found_child"
    SHELTER_SEARCH = "shelter_search"
    GUIDANCE       = "guidance"
    CASE_STATUS    = "case_status"
    UNKNOWN        = "unknown"


# ── State ─────────────────────────────────────────────────────────────────────

class WayfindState(TypedDict):
    """Complete state that passes through every node in the LangGraph graph.

    Each node receives this full state and returns a dict containing only the
    keys it modifies.  LangGraph merges partial updates automatically.

    Annotations:
      Annotated[list[dict], add_messages]
        — Uses LangGraph's add_messages reducer so new messages are appended
          rather than replacing the existing list.

    Groups:
      ── Session identity
      ── Conversation
      ── Intent detection
      ── Structured data extraction
      ── Completeness / follow-up
      ── Media
      ── Search pipeline (missing child)
      ── Evidence evaluation
      ── Output events (v2)
      ── Error tracking
    """

    # ── Session identity ──────────────────────────────────────────────────────
    session_id: str
    """UUID assigned by ShelterAppUiBackend. This service never generates session IDs."""

    # ── Conversation ──────────────────────────────────────────────────────────
    user_prompt: str
    """The user's most recent text input for this turn."""

    conversation_history: Annotated[list[dict], add_messages]
    """Full conversation turns in {role, content} format.
    add_messages reducer appends new messages; existing turns are never overwritten.
    """

    turn_count: int
    """Number of turns completed so far (incremented by the route handler before graph runs)."""

    # ── Intent detection ──────────────────────────────────────────────────────
    intent: Intent | None
    """Detected intent from the understand_intent node. None until first turn completes."""

    intent_confidence: float | None
    """LLM-reported confidence in the detected intent (0.0–1.0). None until detected."""

    # ── Structured data extraction ────────────────────────────────────────────
    child_search_criteria: ChildSearchCriteria | None
    """Incrementally built search criteria for MISSING_CHILD intent.
    Merged across turns — never reset mid-conversation.
    """

    found_child_report: FoundChildReport | None
    """Incrementally built report for FOUND_CHILD intent.
    ``media_reference`` inside this model is set from ``state.media_reference``.
    """

    # ── Completeness / follow-up ──────────────────────────────────────────────
    missing_information: list[str]
    """Field names that are still required before the agent can proceed.
    Example: ["age", "last_seen_location"]
    Populated by check_completeness; cleared when criteria is sufficient.
    """

    followup_question: str | None
    """LLM-generated natural-language follow-up question targeting missing_information.
    Set by check_completeness; consumed and cleared by ask_followup.
    """

    user_location: Location | None
    """User's current or reported location, used for shelter/support searches."""

    # ── Media ─────────────────────────────────────────────────────────────────
    media_reference: str | None
    """Opaque internal media ID issued by ShelterAppUiBackend after safety scan + storage.
    Never a raw file path, URL, or base64 string.
    Passed to image_match_candidates via MCP tool.
    """

    # ── Search pipeline (missing child) ───────────────────────────────────────
    candidate_ids: list[str]
    """Case IDs returned by search_child_records MCP tool.
    Never contains PII — only internal identifiers.
    """

    candidate_count: int
    """len(candidate_ids). Evaluated by evaluate_candidates to decide routing."""

    image_match_results: list[ImageMatch]
    """Similarity scores per candidate from image_match_candidates MCP tool.
    Empty list if image search was not performed or failed.
    """

    # ── Evidence evaluation ───────────────────────────────────────────────────
    match_evidence: MatchEvidence | None
    """Computed by evaluate_evidence (deterministic, no LLM).
    Contains the composite score and component scores for the top candidate.
    """

    confidence_tier: ConfidenceTier | None
    """LOW | UNCERTAIN | HIGH. Drives the route_by_confidence conditional edge."""

    image_search_warranted: bool
    """True if media_reference is set AND candidate_count <= MAX_IMAGE_CANDIDATES.
    Evaluated by evaluate_candidates before image_match is called.
    """

    # ── Review / submission ───────────────────────────────────────────────────
    review_required: bool
    """Set to True by human_review node. Indicates this case is pending staff review."""

    case_reference: str | None
    """Reference ID returned after a found-child report submission or human review submission.
    Surfaced to the user via a submission_complete or review_pending agent event.
    """

    # ── Final response (legacy field — kept for compatibility) ─────────────────
    final_response: str | None
    """Natural-language response text produced by generate_response.
    Used as fallback if agent_events is empty after graph execution.
    Nodes that want to return text should prefer appending to agent_events.
    """

    # ── Output events (v2) ────────────────────────────────────────────────────
    agent_events: list[dict[str, Any]]
    """Structured output events accumulated by nodes during a single graph execution.

    Each event is a dict matching AgentEvent schema in schemas/event.py:
        { "type": "assistant_message", "content": "..." }
        { "type": "request_information", "fields": [...] }
        { "type": "request_image", "message": "..." }
        { "type": "search_started" }
        { "type": "search_results", "results": [...] }
        { "type": "review_pending", "case_reference": "..." }
        { "type": "submission_complete", "record_id": "..." }
        { "type": "error", "message": "..." }

    The route handler in app/routes/agent.py drains this list after each turn
    and resets it to [] before saving state. Nodes must NOT reset this field —
    only append to it.
    """

    # ── Per-turn form data ────────────────────────────────────────────────────
    last_form_data: dict[str, Any] | None
    """Raw structured key-value data from a user_form_response event.
    Set by the route handler's _merge_event. Consumed by extract_structured_data.
    Reset to None after extraction.
    """

    # ── Error tracking ────────────────────────────────────────────────────────
    errors: list[str]
    """Internal error messages accumulated during graph execution.
    Never returned to the frontend. Used by generate_response to decide
    whether to produce an error event.
    """

    tool_failures: list[str]
    """Names of MCP tools that failed during this turn.
    Example: ["search_child_records", "image_match_candidates"]
    Used by generate_response to produce appropriate fallback messaging.
    """


# ── Initial state factory ─────────────────────────────────────────────────────

def initial_state(session_id: str) -> WayfindState:
    """Return a blank WayfindState for a new session.

    Used by agent/runner.py when no existing session state is found.
    All fields are set to their zero/None/empty values.

    Args:
        session_id: UUID assigned by ShelterAppUiBackend.

    Returns:
        A fully initialised WayfindState dict ready for graph invocation.
    """
    return WayfindState(
        session_id             = session_id,
        user_prompt            = "",
        conversation_history   = [],
        turn_count             = 0,
        intent                 = None,
        intent_confidence      = None,
        child_search_criteria  = None,
        found_child_report     = None,
        missing_information    = [],
        followup_question      = None,
        user_location          = None,
        media_reference        = None,
        candidate_ids          = [],
        candidate_count        = 0,
        image_match_results    = [],
        match_evidence         = None,
        confidence_tier        = None,
        image_search_warranted = False,
        review_required        = False,
        case_reference         = None,
        final_response         = None,
        agent_events           = [],
        last_form_data         = None,
        errors                 = [],
        tool_failures          = [],
    )


# ── Routing helpers ───────────────────────────────────────────────────────────
# These are the router functions used as conditional edge selectors in graph.py.
# They are defined here (next to the state) rather than in graph.py so they can
# be unit-tested independently of the graph wiring.

def completeness_router(state: WayfindState) -> str:
    """Decide whether to ask a follow-up question or proceed to intent routing.

    Returns:
        "incomplete" — missing_information is non-empty; route to ask_followup
        "sufficient" — all required fields present; route to route_intent
    """
    if state.get("missing_information"):
        return "incomplete"
    return "sufficient"


def intent_router(state: WayfindState) -> str:
    """Map the detected intent to the next node name.

    Returns one of:
        "missing_child" | "found_child" | "shelter_search" |
        "guidance"      | "case_status" | "unknown"
    """
    intent = state.get("intent")
    if intent is None:
        return "unknown"
    return intent.value if isinstance(intent, Intent) else str(intent)


def candidate_router(state: WayfindState) -> str:
    """Decide next step after search_metadata returns a candidate pool.

    Returns:
        "no_candidates"   — nothing found; route to no_match
        "image_warranted" — pool small enough + image available; route to image_match
        "no_image"        — skip image; route straight to evaluate_evidence
    """
    if state.get("candidate_count", 0) == 0:
        return "no_candidates"
    if state.get("image_search_warranted", False):
        return "image_warranted"
    return "no_image"


def confidence_router(state: WayfindState) -> str:
    """Map confidence tier to the next node.

    Returns:
        "low"       — below uncertain_threshold; route to no_match
        "uncertain" — between thresholds; route to human_review
        "high"      — above high_threshold; route to human_review (priority)
    """
    tier = state.get("confidence_tier")
    if tier == ConfidenceTier.HIGH:
        return "high"
    if tier == ConfidenceTier.UNCERTAIN:
        return "uncertain"
    return "low"
