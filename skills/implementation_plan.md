# Wayfind — WayFindMCPClient Implementation Plan

**Repository**: `e:\React\Shelter\WayFindMCPClient`  
**Date**: 2026-09-23  
**Scope**: Agent backend — LangGraph + MCP Client + FastMCP Server

> [!IMPORTANT]
> This plan covers the complete backend only. The Next.js frontend (`ShelterApp ui`) is not modified. The frontend already sends `POST /api/agent { "prompt": string }` and renders `{ "message": string }`.

---

## Background & Goals

Wayfind is a prompt-first public PWA for missing children, found children, and shelter access. The user types one natural-language message. The backend owns everything else.

The `WayFindMCPClient` repository will contain:

- **FastAPI** — API entry point (`POST /api/agent`)
- **LangGraph** — Stateful workflow engine with follow-up question loop
- **MCP Client** — LLM wrapper + MCP protocol connection
- **FastMCP Server** — 6 domain-level tools
- **Pydantic schemas** — Shared across all layers
- **Service clients** — HTTP clients to downstream backends
- **Session management** — In-process or Redis session state
- **Security/media intake** — Safety scan before any persistence

---

## Architecture Overview

```text
Wayfind PWA
POST /api/agent { "prompt" }
        ↓
FastAPI (app/)
        ↓
LangGraph graph (agent/)
        ↓
MCP Client + LLM (mcp_client/)
        ↓
FastMCP Server (mcp_server/)
        ↓
[PostgreSQL] [RAG] [Image/Vector] [Support/Location]
```

---

## Target Directory Structure

```text
WayFindMCPClient/
├── skills/
│   └── wayfind-architecture/
│       └── SKILL.md                        ✅ DONE
├── pyproject.toml                           ✅ DONE
├── .env.example                             ✅ DONE
├── .gitignore                               ✅ DONE
├── README.md                                ✅ DONE
│
├── app/                                     Phase 3
│   ├── __init__.py
│   ├── main.py                              ← FastAPI app factory
│   ├── config.py                            ← Pydantic Settings
│   ├── session.py                           ← Session store (dict / Redis)
│   └── routes/
│       ├── __init__.py
│       └── agent.py                         ← POST /api/agent
│
├── agent/                                   Phases 4–5
│   ├── __init__.py
│   ├── state.py                             ← WayfindState TypedDict
│   ├── graph.py                             ← LangGraph graph definition
│   ├── runner.py                            ← Compile + invoke graph
│   └── nodes/
│       ├── __init__.py
│       ├── understand_intent.py             Phase 5
│       ├── extract_structured_data.py       Phase 5
│       ├── check_completeness.py            Phase 5
│       ├── ask_followup.py                  Phase 5
│       ├── route_intent.py                  Phase 5
│       ├── search_metadata.py               Phase 5
│       ├── evaluate_candidates.py           Phase 5
│       ├── image_match.py                   Phase 5
│       ├── evaluate_evidence.py             Phase 5
│       ├── route_by_confidence.py           Phase 5
│       ├── human_review.py                  Phase 5
│       ├── no_match.py                      Phase 5
│       ├── found_child_extract.py           Phase 5
│       ├── safety_guidance.py               Phase 5
│       ├── submit_found_child.py            Phase 5
│       ├── search_support.py                Phase 5
│       ├── get_guidance.py                  Phase 5
│       ├── get_case_status.py               Phase 5
│       └── generate_response.py             Phase 5
│
├── mcp_client/                              Phase 6
│   ├── __init__.py
│   ├── client.py                            ← MCP client init + session
│   └── llm.py                              ← LLM wrapper (Gemini / GPT-4o)
│
├── mcp_server/                              Phases 7–8
│   ├── __init__.py
│   ├── server.py                            ← FastMCP("wayfind") + tool registration
│   └── tools/
│       ├── __init__.py
│       ├── search_child_records.py
│       ├── image_match_candidates.py
│       ├── submit_found_child_report.py
│       ├── search_support.py
│       ├── get_guidance.py
│       └── get_case_status.py
│
├── schemas/                                 Phase 2
│   ├── __init__.py
│   ├── child.py                             ← ChildSearchCriteria, FoundChildReport
│   ├── location.py                          ← Location
│   ├── evidence.py                          ← MatchEvidence, ConfidenceTier
│   ├── candidates.py                        ← Candidate, CandidateSearchResult
│   ├── image.py                             ← ImageMatch, ImageMatchResult
│   ├── review.py                            ← HumanReviewSubmission
│   ├── support.py                           ← SupportLocation, SupportResult
│   ├── guidance.py                          ← GuidanceResult, GuidanceSource
│   └── case.py                              ← CaseStatusResult, FoundChildSubmissionResult
│
├── services/                                Phase 9
│   ├── __init__.py
│   ├── postgres_client.py                   ← Async PostgreSQL HTTP client stub
│   ├── rag_client.py                        ← RAG backend HTTP client stub
│   ├── image_backend_client.py              ← Image/vector backend HTTP client stub
│   ├── support_client.py                    ← Support/location backend HTTP client stub
│   ├── media_service.py                     ← Media intake + safety scan
│   └── review_service.py                   ← Internal human-review queue submission
│
├── config/                                  Phase 10
│   ├── evidence_weights.yaml                ← Configurable matching thresholds
│   └── static_guidance.yaml                ← Fallback guidance when RAG unavailable
│
└── tests/                                   Phase 15
    ├── __init__.py
    ├── test_schemas.py
    ├── test_nodes.py
    ├── test_tools.py
    └── test_graph.py
```

---

## Phase 1 — Project Setup & Tooling ✅ COMPLETE

### Tasks

- [x] Initialize Python project with `pyproject.toml` (Python 3.12+)
- [x] Choose and configure package manager: **uv** (preferred) or pip
- [x] Define dependencies:
  - `fastapi` + `uvicorn[standard]`
  - `langgraph` + `langchain-core`
  - `fastmcp`
  - `langchain-google-genai` (Gemini — confirmed LLM provider)
  - `pydantic` v2
  - `python-dotenv`
  - `httpx` (async HTTP for service clients)
  - `pytest` + `pytest-asyncio` (testing)
  - `redis` (session store — Redis from day 1)
  - `pyyaml` (config file loading)
  - `python-multipart` (media/image upload)
- [x] Create `.env.example` with all required env vars:
  - `LLM_PROVIDER` (gemini | openai)
  - `GEMINI_API_KEY` / `OPENAI_API_KEY`
  - `POSTGRES_SERVICE_URL`
  - `RAG_SERVICE_URL`
  - `IMAGE_BACKEND_URL`
  - `SUPPORT_SERVICE_URL`
  - `REVIEW_SERVICE_URL`
  - `SESSION_BACKEND` (memory | redis)
  - `REDIS_URL`
  - `MAX_CANDIDATE_POOL` (default: 50)
  - `MAX_IMAGE_CANDIDATES` (default: 20)
  - `MEDIA_SAFETY_SCAN_URL`
  - `SECRET_KEY`
  - `CORS_ORIGINS`
  - `MCP_TRANSPORT` + `MCP_SERVER_URL` (SSE — confirmed transport)
- [x] Create `.gitignore` (Python defaults + `.env`)
- [x] Create `README.md` with architecture overview and dev setup

---

## Phase 2 — Pydantic Schemas

> **All schemas are established first.** Every layer (LangGraph, MCP Client, FastMCP tools, service clients) imports from `schemas/`.

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
    gender: str | None = None  # "male" | "female" | "unknown"
    height: HeightRange = Field(default_factory=HeightRange)
    hair_color: str | None = None
    eye_color: str | None = None
    skin_tone: str | None = None
    clothing: list[str] = []
    identifying_features: list[str] = []
    last_seen_location: str | None = None
    date_missing: str | None = None   # ISO 8601 date
    time_missing: str | None = None   # ISO 8601 time
    description: str | None = None    # free-text remainder

class FoundChildReport(BaseModel):
    approx_age: AgeRange = Field(default_factory=AgeRange)
    gender: str | None = None
    height: HeightRange = Field(default_factory=HeightRange)
    hair_color: str | None = None
    clothing: list[str] = []
    identifying_features: list[str] = []
    found_location: str                # required
    found_at: str | None = None
    current_circumstances: str | None = None
    authorities_contacted: bool | None = None
    reporter_name: str | None = None
    reporter_contact: str | None = None
    description: str | None = None
    media_reference: str | None = None  # internal media ID only
```

### `schemas/location.py`

```python
class Location(BaseModel):
    label: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float | None = None
```

### `schemas/evidence.py`

```python
from enum import Enum

class ConfidenceTier(str, Enum):
    LOW = "low"
    UNCERTAIN = "uncertain"
    HIGH = "high"

class MatchEvidence(BaseModel):
    metadata_score: float          # 0.0–1.0
    image_similarity: float | None
    geographic_score: float | None
    temporal_score: float | None
    supporting_factors: list[str]
    conflicting_factors: list[str]
    candidate_case_id: str
```

### `schemas/candidates.py`

```python
class Candidate(BaseModel):
    case_id: str
    age_at_intake: int | None
    gender: str | None
    height_cm: float | None
    hair_color: str | None
    intake_location: str | None
    intake_date: str | None
    metadata_match_score: float
    thumbnail_available: bool

class CandidateSearchResult(BaseModel):
    candidates: list[Candidate]
    total_candidates: int
    search_summary: str
    truncated: bool
```

### `schemas/image.py`

```python
class ImageMatch(BaseModel):
    candidate_case_id: str
    similarity_score: float
    model_version: str
    match_regions: list[str]

class ImageMatchResult(BaseModel):
    matches: list[ImageMatch]
    query_media_id: str
    candidates_searched: int
```

### `schemas/support.py`, `schemas/guidance.py`, `schemas/case.py`, `schemas/review.py`

_(As specified in SKILL.md — all structured return types for MCP tools)_

---

## Phase 3 — FastAPI Entry Point

### `app/config.py`

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""
    postgres_service_url: str
    rag_service_url: str
    image_backend_url: str
    support_service_url: str
    review_service_url: str
    session_backend: str = "memory"
    redis_url: str = ""
    max_candidate_pool: int = 50
    max_image_candidates: int = 20
    media_safety_scan_url: str = ""
    secret_key: str
    cors_origins: list[str] = ["http://localhost:3000"]
    
    class Config:
        env_file = ".env"
```

### `app/session.py`

- In-memory `dict[session_id, WayfindState]` for dev
- Redis-backed for production
- Session ID generated as UUID on first request
- Returned in response header `X-Session-ID`
- State persisted between turns (the follow-up loop requires this)

### `app/routes/agent.py`

```python
@router.post("/api/agent")
async def agent_endpoint(body: AgentRequest, session_id: str = Header(None)):
    # 1. Resolve or create session
    # 2. Load existing WayfindState from session
    # 3. Merge new prompt into state
    # 4. Run LangGraph graph
    # 5. Save updated state to session
    # 6. Return { message, metadata }
```

Key requirements:
- Accept `{ "prompt": string }`
- Return `{ "message": string, "metadata"?: {} }`
- Session ID in `X-Session-ID` header (create if missing)
- CORS configured for frontend origin
- Rate limiting per session
- Never expose internal state to frontend

### `app/main.py`

- FastAPI app factory
- Mount `/api` router
- CORS middleware
- Exception handlers (no stack traces to client)
- Startup/shutdown hooks (MCP client init, service client warmup)

---

## Phase 4 — LangGraph State

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
    MISSING_CHILD = "missing_child"
    FOUND_CHILD = "found_child"
    SHELTER_SEARCH = "shelter_search"
    GUIDANCE = "guidance"
    CASE_STATUS = "case_status"
    UNKNOWN = "unknown"

class WayfindState(TypedDict):
    session_id: str
    user_prompt: str
    conversation_history: Annotated[list[dict], add_messages]
    turn_count: int
    intent: Intent | None
    intent_confidence: float | None
    child_search_criteria: ChildSearchCriteria | None
    found_child_report: FoundChildReport | None
    missing_information: list[str]
    followup_question: str | None
    user_location: Location | None
    media_reference: str | None
    candidate_ids: list[str]
    candidate_count: int
    image_match_results: list[ImageMatch]
    match_evidence: MatchEvidence | None
    confidence_tier: ConfidenceTier | None
    image_search_warranted: bool
    review_required: bool
    case_reference: str | None
    final_response: str | None
    errors: list[str]
    tool_failures: list[str]
```

---

## Phase 5 — LangGraph Nodes

Each node is a pure function `(state: WayfindState) -> dict` (partial state update).

### Node: `understand_intent`

- Sends `conversation_history` + `user_prompt` to LLM
- LLM returns: `{ intent, intent_confidence, partial_criteria }`
- Uses structured output (Pydantic model) — not free text
- Updates: `intent`, `intent_confidence`
- If `CASE_STATUS` intent: extract `case_reference` from prompt

### Node: `extract_structured_data`

**For MISSING_CHILD intent:**
- LLM receives: existing `child_search_criteria` + new user prompt
- LLM **merges** new information into existing criteria
- LLM must:
  - Fill fields where user provided information
  - Leave fields `None` where user said nothing or "I don't know"
  - Set `[]` where user said "none" for clothing/features
  - Never infer or hallucinate values
- Returns updated `ChildSearchCriteria`
- Critical: `age.exact` only if user said an exact number; use `age.min/max` for "around 9"

**For FOUND_CHILD intent:**
- Same discipline for `FoundChildReport`

### Node: `check_completeness`

- Checks `child_search_criteria` against `MINIMUM_REQUIRED = {gender, age_or_range, last_seen_location}`
- Builds `missing_information: list[str]`
- If `missing_information` is non-empty: sets `followup_question`
- Follow-up question:
  - Targets only the most impactful missing fields
  - Max ONE compound question per turn
  - Natural language (LLM generated, not template)
  - Example: "Could you tell me approximately how old the child is and where they were last seen?"

### Node: `ask_followup`

- Sets `final_response = followup_question`
- Appends question to `conversation_history`
- **Does not call any MCP tool**
- Graph terminates → frontend renders question → user replies → next turn

### Node: `route_intent`

- Conditional edge based on `intent`:
  - `MISSING_CHILD` → `search_metadata`
  - `FOUND_CHILD` → `found_child_extract`
  - `SHELTER_SEARCH` → `search_support`
  - `GUIDANCE` → `get_guidance`
  - `CASE_STATUS` → `get_case_status`
  - `UNKNOWN` → ask_followup (request clarification)

### Node: `search_metadata`

- Calls MCP tool: `search_child_records(criteria=child_search_criteria)`
- Stores: `candidate_ids`, `candidate_count`
- On tool failure: adds to `tool_failures`, sets fallback response

### Node: `evaluate_candidates`

- If `candidate_count == 0`: route to `no_match`
- If `candidate_count > 0`: check `image_search_warranted`
  - `image_search_warranted = media_reference is not None and candidate_count <= MAX_IMAGE_CANDIDATES`
- Routing decision: to `image_match` or `evaluate_evidence`

### Node: `image_match`

- Calls MCP tool: `image_match_candidates(media_id=media_reference, candidate_case_ids=candidate_ids)`
- Stores: `image_match_results`
- On failure: sets flag, skips to `evaluate_evidence` with image_similarity=None

### Node: `evaluate_evidence`

- **Deterministic** — no LLM involved
- Reads `child_search_criteria`, `candidate_ids`, `image_match_results`
- Computes `MatchEvidence` for top candidate(s)
- Loads weights from `config/evidence_weights.yaml`
- Computes `confidence_tier`
- Never hardcodes thresholds

### Node: `route_by_confidence`

- `LOW` → `no_match`
- `UNCERTAIN` or `HIGH` → `human_review`

### Node: `human_review`

- Calls **internal** `review_service.submit_for_human_review(...)` (NOT an MCP tool)
- Sets `review_required = True`
- Sets `case_reference` from review submission
- Response to user: "We found a potential match and submitted it for verification. Reference: {case_reference}."

### Node: `no_match`

- Sets `final_response` to safe no-match message with next steps
- Next steps sourced from `static_guidance.yaml` for consistency

### Node: `found_child_extract`

- Handles FOUND_CHILD flow extraction + follow-up

### Node: `safety_guidance`

- Calls MCP: `get_guidance(query=..., topic="found_child")`
- Adds guidance to conversation before submitting report

### Node: `submit_found_child`

- Calls MCP: `submit_found_child_report(report=found_child_report)`
- Returns `case_reference` + next steps

### Node: `search_support`

- Calls MCP: `search_support(location=user_location, support_type=...)`

### Node: `get_guidance`

- Calls MCP: `get_guidance(query=user_prompt, topic=...)`

### Node: `get_case_status`

- Calls MCP: `get_case_status(case_reference=case_reference)`

### Node: `generate_response`

- LLM or template generates final natural-language response from structured state
- Never states confirmed identity
- Always uses safe language ("potential match", "submitted for verification")

---

## Phase 6 — MCP Client

### `mcp_client/llm.py`

- Wraps LLM (Gemini / GPT-4o)
- Methods:
  - `extract_intent(conversation_history, prompt) -> IntentResult`
  - `extract_child_criteria(existing_criteria, prompt) -> ChildSearchCriteria`
  - `extract_found_child_report(existing_report, prompt) -> FoundChildReport`
  - `generate_followup_question(missing_fields, context) -> str`
  - `generate_final_response(state) -> str`
- All outputs are Pydantic models via structured output / function calling
- LLM **never invents** values for fields the user did not provide

### `mcp_client/client.py`

- Initializes FastMCP client connection (stdio or SSE transport)
- Provides async method wrappers for each tool
- Handles connection lifecycle (startup, shutdown, reconnect)

---

## Phase 7 — FastMCP Server

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

## Phase 8 — FastMCP Tools

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

## Phase 9 — Service Clients

Each service client is an async HTTP client (httpx) that calls downstream backends. These are **stubs** at this stage — they define the interface contract without real backend implementations.

### `services/postgres_client.py`

```python
class PostgresClient:
    async def search_children(criteria: ChildSearchCriteria, max_results: int) -> CandidateSearchResult: ...
    async def submit_found_child(report: FoundChildReport) -> FoundChildSubmissionResult: ...
    async def get_public_case_status(case_reference: str) -> CaseStatusResult: ...
```

### `services/rag_client.py`

```python
class RagClient:
    async def query(query: str, topic: str | None) -> GuidanceResult: ...
```

### `services/image_backend_client.py`

```python
class ImageBackendClient:
    async def compare(media_id: str, candidate_case_ids: list[str]) -> ImageMatchResult: ...
```

### `services/support_client.py`

```python
class SupportClient:
    async def search(location: Location, support_type: str | None) -> SupportResult: ...
```

### `services/media_service.py`

```python
class MediaService:
    async def safety_scan(file_bytes: bytes, mime_type: str) -> ScanResult: ...
    async def store(file_bytes: bytes, mime_type: str) -> str:  # returns media_id
        ...
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

## Phase 10 — Configuration Files

### `config/evidence_weights.yaml`

```yaml
# Configurable matching thresholds — do NOT hardcode these in Python
# Calibrate against verified historical cases

weights:
  metadata: 0.50
  image_similarity: 0.35
  geographic: 0.10
  temporal: 0.05

tiers:
  high_threshold: 0.75      # above this -> HIGH tier (human review)
  uncertain_threshold: 0.45 # above this -> UNCERTAIN tier (human review)
  # below uncertain_threshold -> LOW (no match response)

candidate_pool:
  max_metadata_results: 50
  max_image_candidates: 20   # only run image matching if pool <= this
```

### `config/static_guidance.yaml`

```yaml
found_child:
  guidance: |
    If you have found a child alone, do not leave them unattended.
    Contact local police immediately at [emergency number].
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
    
    # Add all nodes
    g.add_node("understand_intent", understand_intent)
    g.add_node("extract_structured_data", extract_structured_data)
    g.add_node("check_completeness", check_completeness)
    g.add_node("ask_followup", ask_followup)
    g.add_node("route_intent", route_intent)
    # ... (all 19 nodes)
    
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
        "missing_child": "search_metadata",
        "found_child": "found_child_extract",
        "shelter_search": "search_support_node",
        "guidance": "get_guidance_node",
        "case_status": "get_case_status_node",
        "unknown": "ask_followup",
    })
    
    # Missing child pipeline
    g.add_edge("search_metadata", "evaluate_candidates")
    g.add_conditional_edges("evaluate_candidates", candidate_router, {
        "no_candidates": "no_match",
        "image_warranted": "image_match",
        "no_image": "evaluate_evidence",
    })
    g.add_edge("image_match", "evaluate_evidence")
    g.add_edge("evaluate_evidence", "route_by_confidence")
    g.add_conditional_edges("route_by_confidence", confidence_router, {
        "low": "no_match",
        "uncertain": "human_review",
        "high": "human_review",
    })
    g.add_edge("human_review", "generate_response")
    g.add_edge("no_match", "generate_response")
    g.add_edge("generate_response", END)
    
    # Found child pipeline
    g.add_edge("found_child_extract", "safety_guidance")
    g.add_edge("safety_guidance", "submit_found_child")
    g.add_edge("submit_found_child", "generate_response")
    
    # Other intents
    g.add_edge("search_support_node", "generate_response")
    g.add_edge("get_guidance_node", "generate_response")
    g.add_edge("get_case_status_node", "generate_response")
    
    return g.compile()
```

### `agent/runner.py`

```python
async def run_agent(state: WayfindState) -> WayfindState:
    graph = build_graph()
    result = await graph.ainvoke(state)
    return result
```

---

## Phase 12 — Follow-Up Loop Integration

The follow-up loop is the core multi-turn interaction:

```
Turn 1: "My daughter is missing."
  -> intent: MISSING_CHILD
  -> criteria: { gender: "female" }
  -> missing: ["age_or_range", "last_seen_location"]
  -> followup: "How old is she approximately, and where was she last seen?"
  -> Response: followup question
  -> END (state saved to session)

Turn 2: "She's about 7, last seen near Johar Town."
  -> State loaded from session
  -> Merge: criteria.age.min=6, criteria.age.max=8, criteria.last_seen_location="Johar Town"
  -> missing: []
  -> Proceed to search_metadata
```

Key requirements for merge logic in `extract_structured_data`:
1. Receive existing `child_search_criteria` from state
2. Parse new user turn
3. Merge new values into existing fields
4. Do NOT reset existing fields when user provides new info for a different field
5. Explicit "none" / "I don't know" → set field to `None` (not omitted)

---

## Phase 13 — Security & Media Intake

### Media Intake Flow (before any MCP tool is called)

```
User uploads image
      ↓
app/routes/agent.py receives multipart OR base64
      ↓
media_service.safety_scan(file_bytes, mime_type)
      ↓
UNSAFE: Return safe error message, do not persist
SAFE:
      ↓
media_service.store(file_bytes, mime_type)
      ↓
Returns media_id (internal backend ID)
      ↓
Stored in WayfindState.media_reference = media_id
      ↓
image_match_candidates(media_id=media_id, ...)
```

### Authorization Rules

- Public API: anonymous session (JWT session token)
- No staff records ever returned to public route
- `get_case_status` returns only public-safe fields
- All candidate results: case IDs + coarse metadata, no PII
- `media_id` is an internal identifier, never a raw object-storage URL
- Rate limiting: per session, per IP

---

## Phase 14 — Error Handling & Failure States

Each node handles its own failures:

```python
try:
    result = await mcp_client.search_child_records(criteria)
    return {"candidate_ids": result.candidate_ids, ...}
except McpToolError as e:
    return {
        "tool_failures": state["tool_failures"] + ["search_child_records"],
        "errors": state["errors"] + [str(e)],
        "final_response": "Our records service is temporarily unavailable. Please try again shortly."
    }
```

`generate_response` node checks `tool_failures` and `errors` to produce appropriate final responses.

Exception handler in FastAPI returns:
```json
{ "message": "Something went wrong. Please try again." }
```
Never exposes stack traces, internal errors, or infrastructure details.

---

## Phase 15 — Tests

### `tests/test_schemas.py`
- Validate all Pydantic models serialize/deserialize correctly
- Test `None` handling for optional fields
- Test `AgeRange` and `HeightRange` partial population

### `tests/test_nodes.py`
- Unit test each LangGraph node in isolation
- Mock LLM calls
- Test completeness check logic
- Test evidence evaluation with configurable weights

### `tests/test_tools.py`
- Test each FastMCP tool with mocked service clients
- Test error handling paths
- Test `image_match_candidates` rejects empty `candidate_case_ids`

### `tests/test_graph.py`
- Integration test of complete graph execution
- Test missing-child happy path (multi-turn)
- Test found-child submission flow
- Test no-match path
- Test guidance / support / case status flows
- Test failure states

---

## Open Questions / Decisions Needed

> [!IMPORTANT]
> The following decisions need your input before implementation begins:

1. **LLM Provider**: For Now gemini
2. **MCP Transport**: SSE/HTTP
3. **Session Backend**:  Redis from day 1
4. **Image Upload**: The front end should support image upload right now  mcp client will not process it but we will use it for the image search only if other details are matched then we will call image search and we will be passing the image as tool which will convert the image to vector and search it.
5. **Downstream Services**: Build interfaces/stubs initially
6. **Authentication**: Anonymous sessions initially. but in the context update that we are not creating acconts right now in future we will be creating accounts by asking the user doing the prompt their name, email and password within the prompt and create a WayFind account which will keep them posted and notify them if a child similar to their child has been found.
7. **Deployment**: Docker Compose (all services together)

---

## Implementation Order

| Phase | Description | Deliverable |
|-------|-------------|-------------|
| 1 | Project setup ✅ | pyproject.toml, .env.example, .gitignore, README.md |
| 2 | Pydantic schemas | schemas/ directory (9 files) |
| 3 | FastAPI entry point | app/ directory |
| 4 | LangGraph state | agent/state.py |
| 5 | LangGraph nodes | agent/nodes/ (19 nodes) |
| 6 | MCP Client | mcp_client/ (LLM + client) |
| 7 | FastMCP server | mcp_server/server.py |
| 8 | FastMCP tools | mcp_server/tools/ (6 tools) |
| 9 | Service clients | services/ (6 stub clients) |
| 10 | Config files | config/ (2 YAML files) |
| 11 | LangGraph graph | agent/graph.py + runner.py |
| 12 | Follow-up loop | Integration across nodes |
| 13 | Security/media | Media intake + session auth |
| 14 | Failure handling | Per-node error handling |
| 15 | Tests | tests/ directory |

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
- Media safety scanning
- Geocoding
