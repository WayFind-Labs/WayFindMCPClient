---
name: wayfind-architecture
description: >
  Master architecture, responsibility boundaries, LangGraph workflow design,
  FastMCP server/tool specification, Pydantic schemas, matching pipeline, cost
  strategy, security model, and implementation guide for the WayFindMCPClient
  repository. This is the single source of truth for every backend decision
  about LangGraph nodes, MCP tools, data models, and the found-child /
  missing-child workflows. Read this before writing any new agent, node, tool,
  schema, or service inside WayFindMCPClient.
---

# Wayfind — Backend Architecture Reference

## 1. What Is This Repository?

`WayFindMCPClient` is the **agent backend** for the Wayfind public PWA.

It contains:
- The **FastMCP MCP server** (domain-level tools only)
- The **LangGraph** stateful workflow / orchestration layer
- The **MCP Client** (connects LangGraph to FastMCP via MCP protocol)
- All **Pydantic schemas** shared across LangGraph, MCP client, and FastMCP tools
- **FastAPI entry-point** that receives POST /api/agent {prompt} from the Next.js frontend
- Session management, media safety intake, and auth boundary
- No frontend code; no raw DB access; no direct Qdrant/vector calls

---

## 2. Frontend Contract (Read-Only — Do Not Change)

The Next.js PWA (ShelterApp ui) sends only:

```
POST /api/agent
{ "prompt": "string" }
```

Response:
```json
{ "message": "string", "metadata"?: {} }
```

The frontend:
- Does NOT select MCP tools
- Does NOT construct tool arguments
- Does NOT call MCP, Qdrant, PostgreSQL, or object storage directly
- Renders only assistant messages and optional status guidance
- Must never be told an identity match is confirmed

---

## 3. System Architecture Diagram

```
Wayfind PWA (ShelterApp ui)
POST /api/agent { prompt }
        |
        v
Agent Backend  [WayFindMCPClient]
FastAPI routes | Auth | Session | Media safety scan
        |
        v
LangGraph  [WayFindMCPClient]
Stateful workflow | Intent | Extraction | Follow-up loop
MCP orchestration | Matching pipeline | Confidence routing
        |
        v
MCP Client  [WayFindMCPClient]
LLM (Gemini/GPT-4o) | Structured extraction | Tool invocation
        |
        | MCP protocol (stdio or SSE)
        v
FastMCP — MCP Server  [WayFindMCPClient]
Domain-level tools only
        |
   +---------+-----------+--------------+
   |         |           |              |
   v         v           v              v
PostgreSQL  RAG      Image/Vector   Support/
Cases DB   Backend   Backend        Location
```

---

## 4. Responsibility Boundaries

| Layer | Responsibilities |
|-------|-----------------|
| Frontend | Render prompt input, display messages, PWA install — no tool selection |
| Agent Backend | FastAPI routes, auth, session, media safety intake, calls LangGraph |
| LangGraph | Workflow state, intent detection, follow-up loop, tool orchestration, routing |
| MCP Client | LLM calls, structured extraction, MCP tool invocation via protocol |
| LLM | NL understanding, intent ID, structured extraction, follow-up questions |
| FastMCP | Domain-level tool surface only — no direct DB logic |
| RAG Backend | Qdrant retrieval, document chunking, knowledge search |
| PostgreSQL | Case records, child records, shelter records |
| Image/Vector Backend | Image embedding, face/similarity search |
| Support/Location | Shelter search, geocoding |
| Staff PWA | Future — human review queue, case management, audit |

---

## 5. LangGraph State

```python
from enum import Enum
from typing import Annotated, TypedDict
from langgraph.graph import add_messages
from schemas.child import ChildSearchCriteria, FoundChildReport
from schemas.location import Location
from schemas.evidence import MatchEvidence, ConfidenceTier
from schemas.image import ImageMatch

class Intent(str, Enum):
    MISSING_CHILD = "missing_child"
    FOUND_CHILD = "found_child"
    SHELTER_SEARCH = "shelter_search"
    GUIDANCE = "guidance"
    CASE_STATUS = "case_status"
    UNKNOWN = "unknown"

class WayfindState(TypedDict):
    # -- Conversation
    session_id: str
    user_prompt: str
    conversation_history: Annotated[list[dict], add_messages]
    turn_count: int

    # -- Intent
    intent: Intent | None
    intent_confidence: float | None

    # -- Structured data
    child_search_criteria: ChildSearchCriteria | None
    found_child_report: FoundChildReport | None

    # -- Information completeness
    missing_information: list[str]
    followup_question: str | None

    # -- User context
    user_location: Location | None
    media_reference: str | None

    # -- Candidate pipeline
    candidate_ids: list[str]
    candidate_count: int
    image_match_results: list[ImageMatch]

    # -- Evidence & confidence
    match_evidence: MatchEvidence | None
    confidence_tier: ConfidenceTier | None

    # -- Routing flags
    image_search_warranted: bool
    review_required: bool

    # -- Output / resolution
    case_reference: str | None
    final_response: str | None

    # -- Error state
    errors: list[str]
    tool_failures: list[str]
```

---

## 6. LangGraph Workflow — Missing Child

```
START
  |
  v
[understand_intent]        <- LLM detects intent + partial criteria
  |
  v
[extract_structured_data]  <- LLM fills ChildSearchCriteria, nulls where unknown
  |
  v
[check_information_completeness]
  |
  +-- INCOMPLETE --> [ask_followup] --> END  (wait for next user turn)
  |                  (user reply -> new turn -> extract again, merge)
  |
  +-- SUFFICIENT --> [route_intent]
                          |
           +--------------+-----------+-----------+
           v              v           v           v
   [missing_child]  [found_child] [shelter]  [guidance]
           |
           v
   [search_metadata]      <- MCP: search_child_records()
           |
           v
   [evaluate_candidates]
           |
   +-------+----------+
   v                  v
NO CANDIDATES   CANDIDATES FOUND
   |                  |
   v                  v
[no_match]    [image_search_warranted?]
                       |
          +------------+----------+
          v                       v
      NO IMAGE             IMAGE + SMALL POOL
      PROVIDED             PROVIDED
          |                       |
          v                       v
  [evaluate_evidence]   [image_match_candidates] <- MCP
          |                       |
          +----------+------------+
                     v
             [evaluate_evidence]
                     |
             [route_by_confidence]
                     |
          +----------+----------+
          v          v          v
         LOW      UNCERTAIN    HIGH
          |          |          |
          v          v          v
      [no_match] [human_review] [human_review]
                     |
                     v
             [generate_response]
                     |
                     v
                    END
```

---

## 7. LangGraph Workflow — Found Child

```
START
  |
  v
[understand_intent]
  |
  v
[extract_found_child_data]        <- LLM fills FoundChildReport
  |
  v
[check_report_completeness]
  |
  +-- INCOMPLETE --> [ask_followup] --> END
  |
  +-- SUFFICIENT
          |
          v
  [safety_guidance_node]          <- MCP: get_guidance(topic="found_child")
          |
          v
  [handle_media_if_provided]      <- internal media service
          |
          v
  [submit_found_child_report]     <- MCP: submit_found_child_report()
          |
          v
  [generate_response]             <- Returns case reference + next steps
          |
          v
         END
```

---

## 8. Follow-Up Question Strategy

KEY RULE: LangGraph keeps prompting the user across turns until search criteria
reaches sufficient completeness. This is similar to how Claude asks clarifying
questions before answering.

- Each new user prompt restores full WayfindState from session
- LLM merges new answer into existing partial criteria
- Unknown / refused fields -> None (never invented by LLM)
- If user says "I don't know" or "none" -> stored as explicit None/empty list
- Ask ONE compound question per turn targeting the most impactful missing fields
- Stop asking when minimum viable criteria are satisfied

MINIMUM REQUIRED TO PROCEED:
- gender (or explicit "unknown")
- approximate age or age range (or explicit "unknown")
- last seen location

---

## 9. Pydantic Schemas

### child.py

```python
class AgeRange(BaseModel):
    min: int | None = None
    max: int | None = None
    exact: int | None = None

class HeightRange(BaseModel):
    min_cm: float | None = None
    max_cm: float | None = None

class ChildSearchCriteria(BaseModel):
    age: AgeRange = Field(default_factory=AgeRange)
    gender: str | None = None
    height: HeightRange = Field(default_factory=HeightRange)
    hair_color: str | None = None
    eye_color: str | None = None
    skin_tone: str | None = None
    clothing: list[str] = []
    identifying_features: list[str] = []
    last_seen_location: str | None = None
    date_missing: str | None = None
    time_missing: str | None = None
    description: str | None = None

class FoundChildReport(BaseModel):
    approx_age: AgeRange = Field(default_factory=AgeRange)
    gender: str | None = None
    height: HeightRange = Field(default_factory=HeightRange)
    hair_color: str | None = None
    clothing: list[str] = []
    identifying_features: list[str] = []
    found_location: str
    found_at: str | None = None
    current_circumstances: str | None = None
    authorities_contacted: bool | None = None
    reporter_name: str | None = None
    reporter_contact: str | None = None
    description: str | None = None
    media_reference: str | None = None
```

### location.py

```python
class Location(BaseModel):
    label: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    radius_km: float | None = None
```

### evidence.py

```python
class ConfidenceTier(str, Enum):
    LOW = "low"
    UNCERTAIN = "uncertain"
    HIGH = "high"

class MatchEvidence(BaseModel):
    metadata_score: float
    image_similarity: float | None
    geographic_score: float | None
    temporal_score: float | None
    supporting_factors: list[str]
    conflicting_factors: list[str]
    candidate_case_id: str
```

### candidates.py

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

### image.py

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

### support.py

```python
class SupportLocation(BaseModel):
    name: str
    type: str
    address: str | None
    distance_km: float | None
    contact: str | None
    availability: str | None

class SupportResult(BaseModel):
    locations: list[SupportLocation]
    search_location_used: str
    total_found: int
```

### guidance.py

```python
class GuidanceSource(BaseModel):
    title: str
    excerpt: str
    relevance_score: float

class GuidanceResult(BaseModel):
    guidance_text: str
    sources: list[GuidanceSource]
    topic: str | None
```

### case.py

```python
class CaseStatusResult(BaseModel):
    case_reference: str
    status: str
    last_updated: str
    public_message: str
    next_steps: list[str]

class FoundChildSubmissionResult(BaseModel):
    case_reference: str
    status: str
    next_steps: list[str]

class HumanReviewSubmission(BaseModel):
    review_id: str
    status: str
    estimated_review_time: str | None
```

---

## 10. FastMCP Tool Specifications

### search_child_records
- Purpose: Cheap metadata-only candidate filtering
- Caller: LangGraph search_metadata node
- Backend: PostgreSQL
- Returns: CandidateSearchResult (case IDs + coarse metadata, no PII)
- Safety: No PII in return; case IDs only
- Public: Yes

### image_match_candidates
- Purpose: Expensive image similarity against pre-filtered candidate set ONLY
- Caller: LangGraph image_match node
- Backend: Image/vector backend
- Input: media_id (backend-internal ID, never raw URL) + candidate_case_ids
- Returns: ImageMatchResult
- Constraint: candidate_case_ids must be non-empty (enforced)
- Public: Yes (only when media was provided by user)

### submit_found_child_report
- Purpose: Submit complete found-child report, receive case reference
- Caller: LangGraph submit_found_child node
- Backend: PostgreSQL
- Returns: FoundChildSubmissionResult (case ref + next steps)
- Safety: No cross-referencing or matching at submission time
- Public: Yes

### search_support
- Purpose: Find authorized child-intake shelters or support organizations
- Caller: LangGraph search_support node
- Backend: Support/location backend
- Returns: SupportResult
- Note: "shelter" means authorized child-intake, not general homelessness
- Public: Yes

### get_guidance
- Purpose: Retrieve knowledge base guidance via RAG
- Caller: LangGraph guidance node or safety_guidance node
- Backend: RAG backend (Qdrant + synthesis)
- Topics: found_child | missing_child | shelter | safety | reporting | emergency
- Returns: GuidanceResult
- Public: Yes

### get_case_status
- Purpose: Public-safe status of a previously submitted case
- Caller: LangGraph case_status node
- Backend: PostgreSQL (read-only, public-safe view)
- Returns: CaseStatusResult (no staff notes, no candidate IDs, no scores)
- Public: Yes

### submit_for_human_review (INTERNAL — NOT an MCP tool)
- This is an internal LangGraph -> review service call
- No LLM interpretation needed; purely deterministic routing
- Staff review system has separate auth boundary
- Do NOT expose as FastMCP tool

---

## 11. Operations That Are NOT MCP Tools

| Operation | Lives In |
|-----------|----------|
| PostgreSQL CRUD | PostgreSQL service / ORM |
| Qdrant insert/update/delete | RAG backend service |
| Embedding generation | RAG / image backend |
| Image preprocessing | Image/vector backend |
| Media safety scanning | Agent backend (before MCP) |
| Object-storage upload | Agent backend media service |
| Database migrations | Infrastructure / Alembic |
| Authentication internals | Agent backend auth layer |
| Raw geocoding | Support/location backend |
| Metadata scoring calculations | LangGraph evaluate_evidence node |
| Human review routing | LangGraph + internal review service |
| Session management | Agent backend |

---

## 12. Matching Pipeline

Stage 1 — Metadata Search (cheap)
  ChildSearchCriteria -> PostgreSQL filtered query
  (age range, gender, location radius, date window, clothing keywords)
  -> Ranked candidate pool (capped at MAX_CANDIDATE_POOL, configurable)

Scoring signals (configurable weights in evidence_weights.yaml):
  - age_match_score: range overlap
  - gender_match: binary
  - location_proximity_score: geographic distance decay
  - temporal_score: recency decay from intake date
  - physical_description_overlap: clothing/hair/height fuzzy match

Stage 2 — Image Matching (expensive, conditional)
  Only triggered when:
  1. User has provided an image (media_reference in state)
  2. Candidate pool is <= MAX_IMAGE_CANDIDATES (configurable)

  media_id + candidate_case_ids -> image_match_candidates()
  -> similarity scores merged with metadata scores -> MatchEvidence

Stage 3 — Evidence Evaluation (deterministic)
  evaluate_evidence(metadata_score, image_similarity, geo_score, temporal_score, weights)
  -> ConfidenceTier

Stage 4 — Confidence Routing
  LOW      -> no_match response
  UNCERTAIN -> submit_for_human_review (internal)
  HIGH      -> submit_for_human_review (internal)

  HIGH confidence does NOT mean "confirmed match."
  It means "sufficient evidence for human review by shelter staff."

---

## 13. Threshold Calibration Strategy

DO NOT hardcode confidence thresholds.
All thresholds live in config/evidence_weights.yaml.
Initial values: conservative (favour false negatives over false positives).
Calibration approach:
1. Collect verified historical cases (ground truth)
2. Run retrospective scoring against ground truth
3. Plot precision/recall curve
4. Select threshold that minimizes false positives while maintaining recall
5. Monitor false positive and false negative rates in production
6. Adjust weights via config, not code changes

---

## 14. Cost Optimization

Cheap operations (always run):
  - LLM structured extraction (single prompt)
  - PostgreSQL metadata filtering (indexed query)
  - RAG retrieval (fast Qdrant search)

Expensive operations (run only when justified):
  - Image embedding generation (only for user-provided images)
  - Image similarity search (only against candidate pool, never full DB)
  - Multiple LLM calls (minimized via single extraction prompt)

Cost guardrails:
  - MAX_CANDIDATE_POOL: cap metadata search result set
  - MAX_IMAGE_CANDIDATES: only run image matching if pool is small
  - Precomputed embeddings: stored child records have embeddings at intake
  - User image: processed once per session, media_id cached
  - Never scan entire image database

---

## 15. Security and Privacy

```
Public API:  JWT anonymous session | Rate limiting | Media safety scan
Agent Backend: No staff records returned | No raw candidate PII to frontend
FastMCP Tools: Case IDs only in candidate results | media_id = internal ID
               get_case_status = public-safe subset only
Internal Services: PostgreSQL full records (staff auth required)
                   Image backend full access (staff auth required)
                   Staff PWA: separate auth domain
```

Audit trail: All MCP tool invocations logged with session_id, tool_name,
input hash, result shape. No PII in audit log.

Media: safety scanned before any persistence. media_id is internal
backend identifier, never a raw object-storage URL.

---

## 16. Failure Handling

| Failure | User Response |
|---------|--------------|
| PostgreSQL unavailable | "Our records service is temporarily unavailable. Please try again shortly." |
| RAG unavailable | Fall back to static_guidance.yaml content |
| Image backend unavailable | Skip image matching, proceed with metadata evidence only |
| MCP tool error | Log + safe message, never expose stack trace |
| LLM extraction fails | Ask user to rephrase |
| Unsafe image | "We were unable to process the image. Please contact support directly." |
| No candidates found | No-match response with next steps |
| Human review unavailable | Queue async, notify user of delay |
| Invalid case reference | "We could not find a report with that reference number." |

---

## 17. No-Match Response Guidelines

When no candidates found or evidence insufficient:

"We searched our current records and did not find a child matching the
information you provided. This does not mean the child is not present
elsewhere — our records cover only registered cases from partner shelters.
We recommend: [next steps: contact local police, call [number], visit nearest shelter]."

NEVER state:
- "The child is not in any shelter"
- Any claim about the child's current safety

---

## 18. Public vs. Staff Capabilities

Public Wayfind (this repo):
  search_child_records, image_match_candidates, submit_found_child_report,
  search_support, get_guidance, get_case_status

Future Staff PWA (separate repo, separate auth):
  review_candidates, verify_match, resolve_case, manage_shelter_records,
  audit_actions, get_all_cases

---

## 19. Target Directory Structure

```
WayFindMCPClient/
|-- skills/
|   `-- wayfind-architecture/
|       `-- SKILL.md                    <- This file
|-- pyproject.toml
|-- .env.example
|-- README.md
|-- app/
|   |-- __init__.py
|   |-- main.py                         <- FastAPI entry point
|   |-- config.py                       <- Pydantic settings
|   |-- session.py                      <- Session management
|   `-- routes/
|       |-- __init__.py
|       `-- agent.py                    <- POST /api/agent handler
|-- agent/
|   |-- __init__.py
|   |-- graph.py                        <- LangGraph graph definition
|   |-- state.py                        <- WayfindState TypedDict
|   |-- runner.py                       <- Graph compilation + invoke
|   `-- nodes/
|       |-- __init__.py
|       |-- understand_intent.py
|       |-- extract_structured_data.py
|       |-- check_completeness.py
|       |-- ask_followup.py
|       |-- route_intent.py
|       |-- search_metadata.py
|       |-- evaluate_candidates.py
|       |-- image_match.py
|       |-- evaluate_evidence.py
|       |-- route_by_confidence.py
|       |-- human_review.py
|       |-- no_match.py
|       |-- found_child_extract.py
|       |-- safety_guidance.py
|       |-- submit_found_child.py
|       |-- search_support.py
|       |-- get_guidance.py
|       |-- get_case_status.py
|       `-- generate_response.py
|-- mcp_client/
|   |-- __init__.py
|   |-- client.py                       <- MCP client init + connection
|   `-- llm.py                          <- LLM wrapper
|-- mcp_server/
|   |-- __init__.py
|   |-- server.py                       <- FastMCP mcp = FastMCP("wayfind")
|   `-- tools/
|       |-- __init__.py
|       |-- search_child_records.py
|       |-- image_match_candidates.py
|       |-- submit_found_child_report.py
|       |-- search_support.py
|       |-- get_guidance.py
|       `-- get_case_status.py
|-- schemas/
|   |-- __init__.py
|   |-- child.py
|   |-- location.py
|   |-- evidence.py
|   |-- candidates.py
|   |-- image.py
|   |-- review.py
|   |-- support.py
|   |-- guidance.py
|   `-- case.py
|-- services/
|   |-- __init__.py
|   |-- postgres_client.py
|   |-- rag_client.py
|   |-- image_backend_client.py
|   |-- support_client.py
|   |-- media_service.py
|   `-- review_service.py
|-- config/
|   |-- evidence_weights.yaml
|   `-- static_guidance.yaml
`-- tests/
    |-- test_schemas.py
    |-- test_nodes.py
    |-- test_tools.py
    `-- test_graph.py
```

---

## 20. Final Tool List — Wayfind v1

| Tool | Public | Backend | Purpose |
|------|--------|---------|---------|
| search_child_records | Yes | PostgreSQL | Metadata candidate search |
| image_match_candidates | Yes | Image/vector | Image similarity (candidate-scoped) |
| submit_found_child_report | Yes | PostgreSQL | Submit found-child report |
| search_support | Yes | Support/location | Find nearby shelters/NGOs |
| get_guidance | Yes | RAG | Knowledge base guidance |
| get_case_status | Yes | PostgreSQL | Public status of own report |

NOT MCP tools (internal only):
  submit_for_human_review, all PostgreSQL CRUD, vector/embedding ops,
  media safety scanning, geocoding
