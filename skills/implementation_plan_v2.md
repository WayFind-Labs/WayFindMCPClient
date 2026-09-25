# Wayfind — WayFindMCPClient Implementation Plan v2

**Repository**: `e:\React\Shelter\WayFindMCPClient`  
**Updated**: 2026-09-25  
**Scope**: Internal agent layer — LangGraph + MCP Client + FastMCP Server

> [!IMPORTANT]
> **Architecture change from v1.** `WayFindMCPClient` is **no longer the public-facing API**.
> A new repository — `ShelterAppUiBackend` (FastAPI) — sits between the Next.js PWA and this layer.
> This repository now exposes an **internal Agent API** consumed only by `ShelterAppUiBackend`.
> The Next.js frontend never calls this service directly.

---

## Background & Goals

Wayfind is a prompt-first public PWA for missing children, found children, and shelter access.
The user types one natural-language message. The backend owns everything else.

`WayFindMCPClient` is the **intelligence layer** of the system. It contains:

- **FastAPI** — Internal API entry point (`POST /internal/sessions/{id}/events`)
- **LangGraph** — Stateful workflow engine with follow-up question loop
- **MCP Client** — LLM wrapper + MCP protocol connection
- **FastMCP Server** — 6 domain-level tools
- **Pydantic schemas** — Shared across all layers
- **Service clients** — HTTP clients to downstream backends
- **Security** — Internal-only; validated against shared API key

It does **not** contain auth, CORS, rate limiting, image intake, or session ownership.
Those live in `ShelterAppUiBackend`.

---

## What Changed vs v1

| Concern | v1 (old) | v2 (new) |
|---------|----------|----------|
| Who calls this service? | Next.js PWA (public) | `ShelterAppUiBackend` (internal) |
| Auth / rate limiting | Lived here | Moved to `ShelterAppUiBackend` |
| Image upload intake | Lived here | Moved to `ShelterAppUiBackend` |
| Session management | Lived here | `ShelterAppUiBackend` owns sessions; passes `session_id` here |
| CORS | Lived here | Moved to `ShelterAppUiBackend` |
| API contract | `POST /api/agent { "prompt" }` | `POST /internal/sessions/{id}/events { "event": {...} }` |
| Phases 1–3 status | Complete | Phase 3 needs minor tweaks (see below) |

**Phases 4–15 are completely unchanged.** The LangGraph graph, all nodes, MCP client, FastMCP server,
schemas, service clients, and config files are identical to v1. Only the API surface and where
the security boundary lives have moved.

---

## Revised Architecture

```text
Next.js PWA (ShelterApp ui)
        |
        |  HTTPS + SSE
        v
ShelterAppUiBackend  [separate repo — port 8001]
FastAPI | Auth | Sessions | Validation | Rate Limiting | Image Intake | CORS
        |
        |  Internal HTTP (Docker network)
        |  POST /internal/sessions/{id}/events
        |  X-Internal-Key: <shared secret>
        v
WayFindMCPClient  [THIS REPO — port 8000, internal only]
Internal Agent API | LangGraph | MCP Client | LLM (Gemini)
        |
        |  MCP protocol (SSE)
        v
FastMCP Server  [same process as above]
        |
   +---------+-----------+--------------+
   |         |           |              |
   v         v           v              v
PostgreSQL  RAG      Image/Vector   Support/Location
(stub)    (stub)      (Qdrant stub)   (stub)
```

---

## Agent Event Protocol

This service receives **input events** and returns **output events**.
It does not understand prompts, HTML, or browser concepts.

### Input event (from ShelterAppUiBackend)

```json
POST /internal/sessions/{session_id}/events
X-Internal-Key: <shared secret>

{
    "event": {
        "type": "user_message",
        "content": "I found a girl around 7 near Saddar",
        "media_id": null,
        "form_data": null
    }
}
```

Event types received:
- `user_message` — plain text from user
- `user_image` — user sent an image (media_id already set by ShelterAppUiBackend)
- `user_form_response` — user filled in a structured follow-up form

### Output events (returned to ShelterAppUiBackend)

```json
[
    { "type": "assistant_message",   "content": "Do you know approximately how old she is?" },
    { "type": "request_information", "fields": ["age", "clothing", "height"] },
    { "type": "request_image",       "message": "If possible, upload a photo." },
    { "type": "search_started" },
    { "type": "search_results",      "results": [...] },
    { "type": "review_pending",      "case_reference": "WF-20260925-0042" },
    { "type": "submission_complete", "record_id": "WF-20260925-0042" },
    { "type": "error",               "message": "Our records service is temporarily unavailable." }
]
```

---

## Target Directory Structure

```text
WayFindMCPClient/
├── skills/
│   ├── wayfind-architecture/
│   │   └── SKILL.md                        DONE (update arch diagram)
│   ├── wayfind-guardrails/
│   │   └── SKILL.md                        DONE
│   ├── implementation_plan.md              v1 — keep for reference
│   └── implementation_plan_v2.md          THIS FILE
│
├── pyproject.toml                           DONE (Phase 1)
├── .env.example                             DONE + add new vars (Phase 1 tweak)
├── .gitignore                               DONE
├── README.md                                DONE (update arch section)
│
├── app/                                     DONE + tweak (Phase 3)
│   ├── __init__.py
│   ├── main.py                              <- remove public CORS, add internal auth middleware
│   ├── config.py                            <- add SHELTER_BACKEND_API_KEY
│   ├── session.py                           <- simplify; session_id passed in by caller
│   └── routes/
│       ├── __init__.py
│       └── agent.py                         <- new event-based internal endpoint
│
├── agent/                                   Phases 4–5
│   ├── __init__.py
│   ├── state.py                             <- WayfindState TypedDict
│   ├── graph.py                             <- LangGraph graph definition
│   ├── runner.py                            <- Compile + invoke graph
│   └── nodes/
│       ├── __init__.py
│       ├── understand_intent.py
│       ├── extract_structured_data.py
│       ├── check_completeness.py
│       ├── ask_followup.py
│       ├── route_intent.py
│       ├── search_metadata.py
│       ├── evaluate_candidates.py
│       ├── image_match.py
│       ├── evaluate_evidence.py
│       ├── route_by_confidence.py
│       ├── human_review.py
│       ├── no_match.py
│       ├── found_child_extract.py
│       ├── safety_guidance.py
│       ├── submit_found_child.py
│       ├── search_support.py
│       ├── get_guidance.py
│       ├── get_case_status.py
│       └── generate_response.py
│
├── mcp_client/                              Phase 6
│   ├── __init__.py
│   ├── client.py                            <- MCP client init + session
│   └── llm.py                              <- LLM wrapper (Gemini)
│
├── mcp_server/                              Phases 7–8
│   ├── __init__.py
│   ├── server.py                            <- FastMCP("wayfind") + tool registration
│   └── tools/
│       ├── __init__.py
│       ├── search_child_records.py
│       ├── image_match_candidates.py
│       ├── submit_found_child_report.py
│       ├── search_support.py
│       ├── get_guidance.py
│       └── get_case_status.py
│
├── schemas/                                 DONE (Phase 2 — unchanged)
│   ├── __init__.py
│   ├── child.py
│   ├── location.py
│   ├── evidence.py
│   ├── candidates.py
│   ├── image.py
│   ├── review.py
│   ├── support.py
│   ├── guidance.py
│   └── case.py
│
├── services/                                Phase 9
│   ├── __init__.py
│   ├── postgres_client.py
│   ├── rag_client.py
│   ├── image_backend_client.py
│   ├── support_client.py
│   ├── media_service.py
│   └── review_service.py
│
├── config/                                  Phase 10
│   ├── evidence_weights.yaml
│   └── static_guidance.yaml
│
└── tests/                                   Phase 15
    ├── __init__.py
    ├── test_schemas.py
    ├── test_nodes.py
    ├── test_tools.py
    └── test_graph.py
```

---

## Phase 1 — Project Setup ✅ COMPLETE

### Additional env vars to add to `.env.example`

```env
# Internal auth (shared secret with ShelterAppUiBackend)
SHELTER_BACKEND_API_KEY=changeme-dev-secret

# Internal server config
INTERNAL_HOST=0.0.0.0
INTERNAL_PORT=8000
```

Everything else from Phase 1 (pyproject.toml, .gitignore, README.md) is unchanged.

---

## Phase 2 — Pydantic Schemas ✅ COMPLETE

All schemas in `schemas/` are unchanged. They are still the single source of truth
shared across LangGraph nodes, MCP client, and FastMCP tools.

### `schemas/child.py`

```python
from pydantic import BaseModel, Field

class AgeRange(BaseModel):
    min: int | None = None
    max: int | None = None
    exact: int | None = None  # Only if user said exactly "9 years old"

class HeightRange(BaseModel):
    min_cm: float | None = None
    max_cm: float | None = None

class ChildSearchCriteria(BaseModel):
    age: AgeRange = Field(default_factory=AgeRange)
    gender: str | None = None              # "male" | "female" | "unknown"
    height: HeightRange = Field(default_factory=HeightRange)
    hair_color: str | None = None
    eye_color: str | None = None
    skin_tone: str | None = None
    clothing: list[str] = []
    identifying_features: list[str] = []
    last_seen_location: str | None = None
    date_missing: str | None = None        # ISO 8601 date
    time_missing: str | None = None        # ISO 8601 time
    description: str | None = None        # free-text remainder

class FoundChildReport(BaseModel):
    approx_age: AgeRange = Field(default_factory=AgeRange)
    gender: str | None = None
    height: HeightRange = Field(default_factory=HeightRange)
    hair_color: str | None = None
    clothing: list[str] = []
    identifying_features: list[str] = []
    found_location: str                    # required
    found_at: str | None = None
    current_circumstances: str | None = None
    authorities_contacted: bool | None = None
    reporter_name: str | None = None
    reporter_contact: str | None = None
    description: str | None = None
    media_reference: str | None = None    # internal media_id from ShelterAppUiBackend
```

### `schemas/event.py` — NEW in v2

```python
from pydantic import BaseModel
from typing import Any

class IncomingEvent(BaseModel):
    type: str                              # "user_message" | "user_image" | "user_form_response"
    content: str | None = None
    media_id: str | None = None           # set by ShelterAppUiBackend after safety scan
    form_data: dict[str, Any] | None = None

class InternalRequest(BaseModel):
    event: IncomingEvent

class AgentEvent(BaseModel):
    type: str
    content: str | None = None
    fields: list[str] | None = None       # for request_information
    message: str | None = None            # for request_image / error
    results: list[dict] | None = None     # for search_results
    record_id: str | None = None          # for submission_complete
    case_reference: str | None = None     # for review_pending
```

---

## Phase 3 — FastAPI Entry Point ✅ COMPLETE (v2 tweaks done)

Phase 3 tweaks are **complete**. The following changes were made:

- **`app/config.py`** — removed `cors_origins`, `secret_key`, `rate_limit_*`; added `shelter_backend_api_key`, `internal_host`, `internal_port`; added validator with dev-key warning
- **`app/main.py`** — replaced `CORSMiddleware` with `X-Internal-Key` middleware (constant-time `hmac.compare_digest`); router mounted under `/internal` prefix; auth-exempt `/health` endpoint added
- **`app/routes/agent.py`** — complete rewrite: `POST /internal/sessions/{session_id}/events`; accepts `IncomingEvent`; handles `user_message`, `user_image`, `user_form_response`; returns `list[AgentEvent]`; `agent_events` and `last_form_data` added to initial state
- **`schemas/event.py`** — new file: `IncomingEvent`, `InternalRequest`, `AgentEvent`
- **`.env.example`** — replaced `SECRET_KEY` / `CORS_ORIGINS` with `SHELTER_BACKEND_API_KEY`, `INTERNAL_HOST`, `INTERNAL_PORT`

---

### Reference — what was implemented (for future readers)

### `app/config.py` — add new field

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Existing fields unchanged ...
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    postgres_service_url: str
    rag_service_url: str
    image_backend_url: str
    support_service_url: str
    review_service_url: str
    session_backend: str = "memory"        # kept for agent-side state if needed
    redis_url: str = ""
    max_candidate_pool: int = 50
    max_image_candidates: int = 20
    media_safety_scan_url: str = ""
    secret_key: str
    mcp_transport: str = "sse"
    mcp_server_url: str = ""

    # NEW in v2 — internal auth
    shelter_backend_api_key: str = "changeme-dev-secret"
    internal_host: str = "0.0.0.0"
    internal_port: int = 8000

    # REMOVED: cors_origins — CORS is now ShelterAppUiBackend's responsibility

    class Config:
        env_file = ".env"
```

### `app/main.py` — replace CORS with internal auth middleware

```python
# REMOVE: CORSMiddleware with public origins
# ADD: Internal key middleware

from fastapi import Request, HTTPException
from app.config import get_settings

async def verify_internal_key(request: Request, call_next):
    """Only allow requests from ShelterAppUiBackend."""
    settings = get_settings()
    key = request.headers.get("X-Internal-Key")
    if key != settings.shelter_backend_api_key:
        return JSONResponse(status_code=403, content={"message": "Forbidden."})
    return await call_next(request)

# app.add_middleware wraps the verify_internal_key above
# Exempt /health from auth check
```

### `app/routes/agent.py` — new internal endpoint

```python
from fastapi import APIRouter, Request
from schemas.event import InternalRequest, AgentEvent

router = APIRouter()

@router.post("/internal/sessions/{session_id}/events", response_model=list[AgentEvent])
async def handle_event(
    session_id: str,
    body: InternalRequest,
    request: Request,
) -> list[AgentEvent]:
    """
    Receive one event from ShelterAppUiBackend.
    Load or create WayfindState for session_id.
    Run LangGraph graph.
    Return list of AgentEvent objects.
    """
    # 1. Load existing WayfindState for session_id (from in-process dict or Redis)
    # 2. Merge incoming event into state (set user_prompt, media_reference, etc.)
    # 3. Run graph: result = await run_agent(state)
    # 4. Save updated state back to session store
    # 5. Convert result to list[AgentEvent]
    # 6. Return events
    ...

@router.get("/health")
async def health():
    return {"status": "ok"}
```

### `app/session.py` — simplified

```python
# v2: session_id is created and owned by ShelterAppUiBackend.
# This layer only stores WayfindState keyed by session_id.
# No JWT, no token issuance.

class AgentSessionStore:
    async def get(self, session_id: str) -> WayfindState | None: ...
    async def put(self, session_id: str, state: WayfindState) -> None: ...
    async def close(self) -> None: ...
```

---

## Phase 4 — LangGraph State ✅ COMPLETE

### `agent/state.py`

```python
from typing import Annotated, TypedDict
from langgraph.graph import add_messages
from schemas.child import ChildSearchCriteria, FoundChildReport
from schemas.location import Location
from schemas.evidence import MatchEvidence, ConfidenceTier
from schemas.image import ImageMatch
from enum import Enum

class Intent(str, Enum):
    MISSING_CHILD  = "missing_child"
    FOUND_CHILD    = "found_child"
    SHELTER_SEARCH = "shelter_search"
    GUIDANCE       = "guidance"
    CASE_STATUS    = "case_status"
    UNKNOWN        = "unknown"

class WayfindState(TypedDict):
    session_id:              str
    user_prompt:             str
    conversation_history:    Annotated[list[dict], add_messages]
    turn_count:              int
    intent:                  Intent | None
    intent_confidence:       float | None
    child_search_criteria:   ChildSearchCriteria | None
    found_child_report:      FoundChildReport | None
    missing_information:     list[str]
    followup_question:       str | None
    user_location:           Location | None
    media_reference:         str | None      # media_id from ShelterAppUiBackend
    candidate_ids:           list[str]
    candidate_count:         int
    image_match_results:     list[ImageMatch]
    match_evidence:          MatchEvidence | None
    confidence_tier:         ConfidenceTier | None
    image_search_warranted:  bool
    review_required:         bool
    case_reference:          str | None
    final_response:          str | None
    agent_events:            list[dict]      # NEW in v2 — accumulated output events
    errors:                  list[str]
    tool_failures:           list[str]
```

> [!NOTE]
> `agent_events` is new in v2. Nodes append structured event dicts to this list
> instead of (or in addition to) setting `final_response`. The route handler
> converts this list into `list[AgentEvent]` to return to `ShelterAppUiBackend`.

---

## Phase 5 — LangGraph Nodes ✅ COMPLETE

Each node is a pure function `(state: WayfindState) -> dict` (partial state update).

### Node: `understand_intent`

- Sends `conversation_history` + `user_prompt` to LLM
- LLM returns: `{ intent, intent_confidence, partial_criteria }` via structured output
- Updates: `intent`, `intent_confidence`
- If `CASE_STATUS` intent: extract `case_reference` from prompt

### Node: `extract_structured_data`

**For MISSING_CHILD intent:**
- LLM receives: existing `child_search_criteria` + new user prompt
- LLM **merges** new information into existing criteria (does not reset)
- LLM must:
  - Fill fields where user provided information
  - Leave fields `None` where user said nothing or "I don't know"
  - Set `[]` where user said "none" for clothing/features
  - Never infer or hallucinate values
- Returns updated `ChildSearchCriteria`
- Critical: `age.exact` only if user said an exact number; use `age.min/max` for "around 9"

**For FOUND_CHILD intent:**
- Same discipline for `FoundChildReport`
- Set `media_reference` from `state["media_reference"]` if set (came from ShelterAppUiBackend)

### Node: `check_completeness`

- Checks `child_search_criteria` against `MINIMUM_REQUIRED = {gender, age_or_range, last_seen_location}`
- Builds `missing_information: list[str]`
- If `missing_information` is non-empty: sets `followup_question`
- Follow-up question:
  - Targets only the most impactful missing fields (max ONE compound question per turn)
  - Natural language (LLM generated, not template)
  - Example: `"Could you tell me approximately how old the child is and where they were last seen?"`

### Node: `ask_followup`

- Appends `followup_question` to `conversation_history`
- Appends to `agent_events`:
  ```python
  {"type": "assistant_message", "content": followup_question}
  ```
- If missing_information indicates structured form fields:
  ```python
  {"type": "request_information", "fields": missing_information}
  ```
- Does **not** call any MCP tool
- Graph terminates → ShelterAppUiBackend streams events → user responds → next turn

### Node: `route_intent`

Conditional edge based on `intent`:
- `MISSING_CHILD`  → `search_metadata`
- `FOUND_CHILD`    → `found_child_extract`
- `SHELTER_SEARCH` → `search_support`
- `GUIDANCE`       → `get_guidance`
- `CASE_STATUS`    → `get_case_status`
- `UNKNOWN`        → `ask_followup` (request clarification)

### Node: `search_metadata`

- Calls MCP tool: `search_child_records(criteria=child_search_criteria)`
- Stores: `candidate_ids`, `candidate_count`
- Appends `{"type": "search_started"}` to `agent_events`
- On tool failure: adds to `tool_failures`, sets fallback event

### Node: `evaluate_candidates`

- If `candidate_count == 0`: route to `no_match`
- If `candidate_count > 0`: check `image_search_warranted`
  - `image_search_warranted = media_reference is not None and candidate_count <= MAX_IMAGE_CANDIDATES`
- Routing: to `image_match` or `evaluate_evidence`

### Node: `image_match`

- Calls MCP tool: `image_match_candidates(media_id=media_reference, candidate_case_ids=candidate_ids)`
- Stores: `image_match_results`
- On failure: sets flag, skips to `evaluate_evidence` with `image_similarity=None`

### Node: `evaluate_evidence`

- **Deterministic — no LLM involved**
- Reads `child_search_criteria`, `candidate_ids`, `image_match_results`
- Computes `MatchEvidence` for top candidate(s)
- Loads weights from `config/evidence_weights.yaml`
- Computes `confidence_tier`
- Never hardcodes thresholds

### Node: `route_by_confidence`

- `LOW`                     → `no_match`
- `UNCERTAIN` or `HIGH`     → `human_review`

### Node: `human_review`

- Calls **internal** `review_service.submit_for_human_review(...)` (NOT an MCP tool)
- Sets `review_required = True`
- Sets `case_reference` from review submission
- Appends to `agent_events`:
  ```python
  {"type": "review_pending", "case_reference": case_reference}
  ```

### Node: `no_match`

- Sets `final_response` to safe no-match message with next steps
- Appends to `agent_events`:
  ```python
  {"type": "assistant_message", "content": no_match_message}
  ```
- Next steps sourced from `static_guidance.yaml`

### Node: `found_child_extract`

- Handles FOUND_CHILD flow: extracts `FoundChildReport` fields
- Checks completeness (required: `found_location`)
- If incomplete → `ask_followup`
- If complete → `safety_guidance`

### Node: `safety_guidance`

- Calls MCP: `get_guidance(query=..., topic="found_child")`
- Appends guidance message to `agent_events` before submitting report

### Node: `submit_found_child`

- Calls MCP: `submit_found_child_report(report=found_child_report)`
- Returns `case_reference` + next steps
- Appends to `agent_events`:
  ```python
  {"type": "submission_complete", "record_id": case_reference}
  ```

### Node: `search_support`

- Calls MCP: `search_support(location=user_location, support_type=...)`
- Appends to `agent_events`:
  ```python
  {"type": "search_results", "results": [...]}
  ```

### Node: `get_guidance`

- Calls MCP: `get_guidance(query=user_prompt, topic=...)`
- Appends result as `assistant_message` to `agent_events`

### Node: `get_case_status`

- Calls MCP: `get_case_status(case_reference=case_reference)`
- Appends status as `assistant_message` to `agent_events`

### Node: `generate_response`

- LLM or template generates final natural-language message from structured state
- Never states confirmed identity
- Always uses safe language ("potential match", "submitted for verification")
- Appends to `agent_events` if not already set

---

## Phase 6 — MCP Client ✅ COMPLETE

### `mcp_client/llm.py`

```python
class WayfindLLM:
    def __init__(self, provider: str, api_key: str): ...

    async def extract_intent(
        self,
        conversation_history: list[dict],
        prompt: str
    ) -> IntentResult:
        """Structured output — returns Intent + confidence."""
        ...

    async def extract_child_criteria(
        self,
        existing_criteria: ChildSearchCriteria | None,
        prompt: str
    ) -> ChildSearchCriteria:
        """Merge-extract — never invents values not in prompt."""
        ...

    async def extract_found_child_report(
        self,
        existing_report: FoundChildReport | None,
        prompt: str
    ) -> FoundChildReport:
        ...

    async def generate_followup_question(
        self,
        missing_fields: list[str],
        context: list[dict]
    ) -> str:
        """Natural language follow-up targeting missing_fields only."""
        ...

    async def generate_final_response(self, state: WayfindState) -> str:
        """Safe, empathetic natural language response from state."""
        ...
```

All outputs are Pydantic models via structured output / function calling.
The LLM **never invents** values for fields the user did not provide.

### `mcp_client/client.py`

```python
class WayfindMCPClient:
    """Manages FastMCP connection and exposes typed tool wrappers."""

    async def startup(self, transport: str, server_url: str) -> None: ...
    async def shutdown(self) -> None: ...

    async def search_child_records(
        self, criteria: ChildSearchCriteria
    ) -> CandidateSearchResult: ...

    async def image_match_candidates(
        self, media_id: str, candidate_case_ids: list[str]
    ) -> ImageMatchResult: ...

    async def submit_found_child_report(
        self, report: FoundChildReport
    ) -> FoundChildSubmissionResult: ...

    async def search_support(
        self, location: Location, support_type: str | None
    ) -> SupportResult: ...

    async def get_guidance(
        self, query: str, topic: str | None
    ) -> GuidanceResult: ...

    async def get_case_status(
        self, case_reference: str
    ) -> CaseStatusResult: ...
```

---

## Phase 7 — FastMCP Server ✅ COMPLETE

### `mcp_server/server.py`

```python
from fastmcp import FastMCP
from mcp_server.tools.search_child_records import search_child_records
from mcp_server.tools.image_match_candidates import image_match_candidates
from mcp_server.tools.submit_found_child_report import submit_found_child_report
from mcp_server.tools.search_support import search_support
from mcp_server.tools.get_guidance import get_guidance
from mcp_server.tools.get_case_status import get_case_status

mcp = FastMCP("wayfind")

mcp.tool()(search_child_records)
mcp.tool()(image_match_candidates)
mcp.tool()(submit_found_child_report)
mcp.tool()(search_support)
mcp.tool()(get_guidance)
mcp.tool()(get_case_status)
```

---

## Phase 8 — FastMCP Tools ✅ COMPLETE

### Tool 1: `search_child_records`

```python
@mcp.tool()
async def search_child_records(
    criteria: ChildSearchCriteria
) -> CandidateSearchResult:
    """
    Search intake records using structured metadata criteria.
    Returns a ranked candidate pool. Does NOT perform image comparison.
    Call this before image_match_candidates to reduce search space.
    Returns case IDs and coarse metadata only — no PII.
    """
    # Calls postgres_client.search_children(criteria)
    # Applies MAX_CANDIDATE_POOL cap
    # Returns CandidateSearchResult
```

### Tool 2: `image_match_candidates`

```python
@mcp.tool()
async def image_match_candidates(
    media_id: str,
    candidate_case_ids: list[str]
) -> ImageMatchResult:
    """
    Compare uploaded media (by secure backend media ID) against a restricted
    candidate set ONLY. Never call against the full database.
    Requires non-empty candidate_case_ids.
    media_id was issued by ShelterAppUiBackend after safety scan and storage.
    """
    # Validates candidate_case_ids is non-empty
    # Calls image_backend_client.compare(media_id, candidate_case_ids)
    # Returns ImageMatchResult
```

### Tool 3: `submit_found_child_report`

```python
@mcp.tool()
async def submit_found_child_report(
    report: FoundChildReport
) -> FoundChildSubmissionResult:
    """
    Submit a complete found-child report. Returns a case reference number
    and guidance on next steps. Does not cross-reference existing records.
    """
    # Calls postgres_client.submit_found_child(report)
    # Returns FoundChildSubmissionResult with case_reference
```

### Tool 4: `search_support`

```python
@mcp.tool()
async def search_support(
    location: Location,
    support_type: str | None = None
) -> SupportResult:
    """
    Find authorized child-intake shelters or support organizations.
    support_type: "shelter" | "ngo" | "police" | "hospital"
    A shelter means an authorized child-intake location only.
    """
    # Calls support_client.search(location, support_type)
    # Returns SupportResult
```

### Tool 5: `get_guidance`

```python
@mcp.tool()
async def get_guidance(
    query: str,
    topic: str | None = None
) -> GuidanceResult:
    """
    Retrieve guidance from the Wayfind knowledge base via RAG.
    Topics: found_child | missing_child | shelter | safety | reporting | emergency
    Falls back to static content if RAG is unavailable.
    Never exposes Qdrant internals.
    """
    # Calls rag_client.query(query, topic)
    # Falls back to static_guidance.yaml on failure
    # Returns GuidanceResult
```

### Tool 6: `get_case_status`

```python
@mcp.tool()
async def get_case_status(
    case_reference: str
) -> CaseStatusResult:
    """
    Return the public-facing status of a submitted report.
    Does NOT expose staff notes, match scores, candidate details,
    or any internal case data. Returns only safe public information.
    """
    # Calls postgres_client.get_public_case_status(case_reference)
    # Returns CaseStatusResult (public-safe subset only)
```

---

## Phase 9 — Service Clients ✅ COMPLETE

Each client is an async httpx stub. They define the interface contract without real backend implementations.

### `services/postgres_client.py`

```python
class PostgresClient:
    async def search_children(
        criteria: ChildSearchCriteria, max_results: int
    ) -> CandidateSearchResult: ...

    async def submit_found_child(
        report: FoundChildReport
    ) -> FoundChildSubmissionResult: ...

    async def get_public_case_status(
        case_reference: str
    ) -> CaseStatusResult: ...
```

### `services/rag_client.py`

```python
class RagClient:
    async def query(query: str, topic: str | None) -> GuidanceResult: ...
```

### `services/image_backend_client.py`

```python
class ImageBackendClient:
    async def compare(
        media_id: str, candidate_case_ids: list[str]
    ) -> ImageMatchResult: ...
```

> [!NOTE]
> In v2, this service receives a `media_id` issued by `ShelterAppUiBackend` — not raw bytes.
> The image was already safety-scanned and stored before it arrives here.

### `services/support_client.py`

```python
class SupportClient:
    async def search(
        location: Location, support_type: str | None
    ) -> SupportResult: ...
```

### `services/media_service.py`

```python
# v2: REMOVED from this repo.
# Image intake, safety scanning, and storage live in ShelterAppUiBackend.
# This service still exists as a stub in case internal re-scan is needed,
# but it is NOT called from agent routes.
class MediaService:
    async def safety_scan(file_bytes: bytes, mime_type: str) -> ScanResult: ...
    async def store(file_bytes: bytes, mime_type: str) -> str: ...
```

### `services/review_service.py`

```python
class ReviewService:
    async def submit(
        candidate_case_ids: list[str],
        evidence: MatchEvidence,
        session_id: str
    ) -> HumanReviewSubmission: ...
```

---

## Phase 10 — Configuration Files ✅ COMPLETE

### `config/evidence_weights.yaml`

```yaml
# Configurable matching thresholds — do NOT hardcode these in Python
# Calibrate against verified historical cases

weights:
  metadata:         0.50
  image_similarity: 0.35
  geographic:       0.10
  temporal:         0.05

tiers:
  high_threshold:      0.75   # above this -> HIGH tier (human review)
  uncertain_threshold: 0.45   # above this -> UNCERTAIN tier (human review)
  # below uncertain_threshold -> LOW (no match response)

candidate_pool:
  max_metadata_results: 50
  max_image_candidates: 20    # only run image matching if pool <= this
```

### `config/static_guidance.yaml`

```yaml
found_child:
  guidance: |
    If you have found a child alone, do not leave them unattended.
    Contact local police immediately at your local emergency number.
    Stay with the child in a safe, public location until authorities arrive.
    Do not share the child's image or details on social media.
  next_steps:
    - Contact local police
    - Visit nearest authorized shelter
    - Submit a report through Wayfind

missing_child:
  no_match_message: |
    We searched our current records and did not find a child matching the
    information provided. This does not mean the child is absent from all
    records — our database covers only registered cases from partner shelters.
  next_steps:
    - File a police report if not already done
    - Contact local child-welfare organizations
    - Submit a report through Wayfind for ongoing monitoring
```

---

## Phase 11 — LangGraph Graph Definition

### `agent/graph.py`

```python
from langgraph.graph import StateGraph, START, END
from agent.state import WayfindState
from agent.nodes import (
    understand_intent, extract_structured_data, check_completeness,
    ask_followup, route_intent, search_metadata, evaluate_candidates,
    image_match, evaluate_evidence, route_by_confidence, human_review,
    no_match, found_child_extract, safety_guidance, submit_found_child,
    search_support_node, get_guidance_node, get_case_status_node,
    generate_response
)

def build_graph() -> StateGraph:
    g = StateGraph(WayfindState)

    # Add all 19 nodes
    g.add_node("understand_intent",        understand_intent)
    g.add_node("extract_structured_data",  extract_structured_data)
    g.add_node("check_completeness",       check_completeness)
    g.add_node("ask_followup",             ask_followup)
    g.add_node("route_intent",             route_intent)
    g.add_node("search_metadata",          search_metadata)
    g.add_node("evaluate_candidates",      evaluate_candidates)
    g.add_node("image_match",              image_match)
    g.add_node("evaluate_evidence",        evaluate_evidence)
    g.add_node("route_by_confidence",      route_by_confidence)
    g.add_node("human_review",             human_review)
    g.add_node("no_match",                 no_match)
    g.add_node("found_child_extract",      found_child_extract)
    g.add_node("safety_guidance",          safety_guidance)
    g.add_node("submit_found_child",       submit_found_child)
    g.add_node("search_support_node",      search_support_node)
    g.add_node("get_guidance_node",        get_guidance_node)
    g.add_node("get_case_status_node",     get_case_status_node)
    g.add_node("generate_response",        generate_response)

    # Entry point
    g.add_edge(START, "understand_intent")
    g.add_edge("understand_intent", "extract_structured_data")
    g.add_edge("extract_structured_data", "check_completeness")

    # Completeness branch
    g.add_conditional_edges("check_completeness", completeness_router, {
        "incomplete": "ask_followup",
        "sufficient": "route_intent",
    })
    g.add_edge("ask_followup", END)

    # Intent branch
    g.add_conditional_edges("route_intent", intent_router, {
        "missing_child":  "search_metadata",
        "found_child":    "found_child_extract",
        "shelter_search": "search_support_node",
        "guidance":       "get_guidance_node",
        "case_status":    "get_case_status_node",
        "unknown":        "ask_followup",
    })

    # Missing child pipeline
    g.add_edge("search_metadata", "evaluate_candidates")
    g.add_conditional_edges("evaluate_candidates", candidate_router, {
        "no_candidates":   "no_match",
        "image_warranted": "image_match",
        "no_image":        "evaluate_evidence",
    })
    g.add_edge("image_match",         "evaluate_evidence")
    g.add_edge("evaluate_evidence",   "route_by_confidence")
    g.add_conditional_edges("route_by_confidence", confidence_router, {
        "low":       "no_match",
        "uncertain": "human_review",
        "high":      "human_review",
    })
    g.add_edge("human_review",     "generate_response")
    g.add_edge("no_match",         "generate_response")
    g.add_edge("generate_response", END)

    # Found child pipeline
    g.add_edge("found_child_extract", "safety_guidance")
    g.add_edge("safety_guidance",     "submit_found_child")
    g.add_edge("submit_found_child",  "generate_response")

    # Other intents
    g.add_edge("search_support_node",  "generate_response")
    g.add_edge("get_guidance_node",    "generate_response")
    g.add_edge("get_case_status_node", "generate_response")

    return g.compile()
```

### `agent/runner.py`

```python
from agent.graph import build_graph
from agent.state import WayfindState

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph

async def run_agent(state: WayfindState) -> WayfindState:
    graph = get_graph()
    result = await graph.ainvoke(state)
    return result
```

---

## Phase 12 — Follow-Up Loop Integration

The follow-up loop is the core multi-turn interaction. State is preserved across turns
by the `AgentSessionStore` (keyed by `session_id` passed from `ShelterAppUiBackend`).

```text
Turn 1:  "My daughter is missing."
  -> intent: MISSING_CHILD
  -> criteria: { gender: "female" }
  -> missing: ["age_or_range", "last_seen_location"]
  -> followup: "How old is she approximately, and where was she last seen?"
  -> agent_events: [
       { "type": "assistant_message", "content": "How old is she..." },
       { "type": "request_information", "fields": ["age", "last_seen_location"] }
     ]
  -> State saved. Graph ends.

Turn 2:  "She's about 7, last seen near Johar Town."
  -> State loaded from session store
  -> Merge: criteria.age.min=6, criteria.age.max=8,
            criteria.last_seen_location="Johar Town"
  -> missing: []
  -> Proceed to search_metadata
  -> agent_events: [
       { "type": "search_started" },
       { "type": "review_pending", "case_reference": "WF-..." }
     ]
```

Key requirements for merge logic in `extract_structured_data`:
1. Receive existing `child_search_criteria` from state
2. Parse new user turn
3. Merge new values into existing fields
4. Do NOT reset existing fields when user provides new info for a different field
5. Explicit "none" / "I don't know" → set field to `None` (not omitted)

---

## Phase 13 — Security (Internal)

In v2, the security surface of this service is drastically reduced because
`ShelterAppUiBackend` handles the public boundary.

### What this service still enforces

| Control | Implementation |
|---------|---------------|
| Internal auth | `X-Internal-Key` middleware — rejects any request without the shared secret |
| No PII in logs | Log `session_id` only; never log user content or agent state |
| No internal data to client | Route handler returns only `list[AgentEvent]` — never raw state |
| Tool result filtering | MCP tools return only safe public fields (case IDs, no staff notes) |
| Media ID only | `media_reference` is always an opaque ID — never a raw storage URL |
| Tool abuse prevention | `image_match_candidates` validates non-empty `candidate_case_ids` |

### What moved to `ShelterAppUiBackend`

- Image upload, safety scanning, and storage
- Rate limiting
- JWT session token issuance
- CORS
- Public request validation and size limits

---

## Phase 14 — Error Handling & Failure States

Each node handles its own failures:

```python
try:
    result = await mcp_client.search_child_records(criteria)
    return {
        "candidate_ids": result.candidate_ids,
        "candidate_count": result.total_candidates,
    }
except McpToolError as e:
    return {
        "tool_failures": state["tool_failures"] + ["search_child_records"],
        "errors": state["errors"] + [str(e)],
        "agent_events": state["agent_events"] + [{
            "type": "error",
            "message": "Our records service is temporarily unavailable. Please try again shortly."
        }]
    }
```

`generate_response` node checks `tool_failures` and `errors` to produce appropriate output.

FastAPI exception handler (internal):
```json
{ "type": "error", "message": "Something went wrong. Please try again." }
```
Never exposes stack traces, internal errors, or infrastructure details.
`ShelterAppUiBackend` can pass this event through to the frontend as-is.

---

## Phase 15 — Tests

### `tests/test_schemas.py`
- Validate all Pydantic models serialize/deserialize correctly
- Test `None` handling for optional fields
- Test `AgeRange` and `HeightRange` partial population
- Test `IncomingEvent` and `AgentEvent` (new v2 types)

### `tests/test_nodes.py`
- Unit test each LangGraph node in isolation
- Mock LLM calls via `WayfindLLM`
- Test completeness check logic
- Test evidence evaluation with configurable weights
- Test `agent_events` accumulation per node

### `tests/test_tools.py`
- Test each FastMCP tool with mocked service clients
- Test error handling paths
- Test `image_match_candidates` rejects empty `candidate_case_ids`

### `tests/test_graph.py`
- Integration test of complete graph execution
- Test missing-child happy path (multi-turn, state preserved)
- Test found-child submission flow
- Test no-match path
- Test guidance / support / case status flows
- Test failure states and `agent_events` error output

### `tests/test_internal_api.py` — NEW in v2
- `POST /internal/sessions/{id}/events` without `X-Internal-Key` → 403
- `POST /internal/sessions/{id}/events` with wrong key → 403
- `POST /internal/sessions/{id}/events` with valid key → 200 + list of AgentEvent
- State is persisted and loaded correctly across two sequential calls (multi-turn)
- `GET /health` → 200

---

## Implementation Order

| Phase | Description | Status | Notes |
|-------|-------------|--------|-------|
| 1 | Project setup | ✅ COMPLETE | Add `SHELTER_BACKEND_API_KEY` to `.env.example` |
| 2 | Pydantic schemas | ✅ COMPLETE | Add `schemas/event.py` (IncomingEvent, AgentEvent) |
| 3 | FastAPI entry point | ✅ COMPLETE | Internal event endpoint live; internal auth middleware; `/health` added |
| 4 | LangGraph state | ✅ COMPLETE | `agent/state.py` — `WayfindState`, `Intent`, `initial_state()`, 4 router helpers |
| 5 | LangGraph nodes | ✅ COMPLETE | 19 nodes in `agent/nodes/`; `agent/dependencies.py` for LLM/MCP injection |
| 6 | MCP Client | ✅ COMPLETE | LLM wrapper + client implemented & tested |
| 7 | FastMCP server | ✅ COMPLETE | Server registration implemented & tested |
| 8 | FastMCP tools | ✅ COMPLETE | 6 tools implemented & tested |
| 9 | Service clients | ✅ COMPLETE | Async httpx stubs implemented & tested |
| 10 | Config files | ✅ COMPLETE | `config/evidence_weights.yaml` and `config/static_guidance.yaml` |
| 11 | LangGraph graph | **NEXT** | `agent/graph.py` + `runner.py` — unchanged |
| 12 | Follow-up loop | — | Multi-turn integration; session store keyed by `session_id` |
| 13 | Security/media | — | Internal auth middleware only; media in ShelterAppUiBackend |
| 14 | Failure handling | — | Per-node; errors go into `agent_events` |
| 15 | Tests | — | Add `test_internal_api.py` for v2 endpoint |

---

## Resolved Decisions

| # | Decision | Value |
|---|----------|-------|
| 1 | LLM Provider | Gemini |
| 2 | MCP Transport | SSE/HTTP |
| 3 | Session Backend | Agent state in memory/Redis, keyed by `session_id` from `ShelterAppUiBackend` |
| 4 | Image Upload | `ShelterAppUiBackend` handles upload, scan, storage — passes only `media_id` here |
| 5 | Downstream Services | Stub interfaces initially; real backends wired later |
| 6 | Auth | Internal `X-Internal-Key` only; user auth is `ShelterAppUiBackend`'s concern |
| 7 | Deployment | Docker Compose — all services in one compose file |
| 8 | Accounts | Not in v1; future: `ShelterAppUiBackend` creates accounts; this layer remains stateless about user identity |

---

## Final Tool List — Wayfind v1

| # | Tool | Backend | Purpose |
|---|------|---------|---------|
| 1 | `search_child_records` | PostgreSQL | Metadata candidate search |
| 2 | `image_match_candidates` | Image/vector | Image similarity (candidate-scoped) |
| 3 | `submit_found_child_report` | PostgreSQL | Submit found-child report |
| 4 | `search_support` | Support/location | Find nearby shelters/NGOs |
| 5 | `get_guidance` | RAG | Knowledge base guidance |
| 6 | `get_case_status` | PostgreSQL | Public status of own report |

**Internal only (not MCP tools)**:
- `submit_for_human_review` — LangGraph → review service
- All PostgreSQL CRUD
- All vector/embedding operations
- Media safety scanning (moved to ShelterAppUiBackend)
- Geocoding
