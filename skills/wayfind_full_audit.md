# Wayfind — Full Project Audit & Implementation Plan
**Audit Date:** 2026-10-04 | **Auditor:** Antigravity
**Scope:** All three workspaces — ShelterApp ui, ShelterAppUiBackend, WayFindMCPClient

---

## Project Overview — Three-Workspace Architecture

```
Browser (PWA)
    │  HTTPS
    ▼
┌─────────────────────────────────────────────────────┐
│  ShelterApp ui  (Next.js 14 PWA, port 3000)         │
│  Public facing. ChatInterface, PublicShell, 3 forms │
└───────────────┬─────────────────────────────────────┘
                │ REST (fetch) — Bearer token per session
                ▼
┌─────────────────────────────────────────────────────┐
│  ShelterAppUiBackend  (FastAPI, port 8001)           │
│  Public-facing gateway. Sessions, auth, images, SSE │
└───────────────┬─────────────────────────────────────┘
                │ Internal REST — X-Internal-Key
                ▼
┌─────────────────────────────────────────────────────┐
│  WayFindMCPClient  (FastAPI + LangGraph, port 8000) │
│  AI agent. 19 graph nodes. 6 MCP tools. Gemini LLM. │
└─────┬──────────────┬────────────────┬───────────────┘
      │ FastMCP SSE  │ httpx          │ httpx
      ▼              ▼                ▼
  MCP Server     PostgreSQL      RAG / Image /
  (port 9000)    Backend         Review Services
```

---

## ✅ WHAT IS ALREADY DONE

### Workspace 1 — ShelterApp ui (Next.js)

| Area | Status | Key File |
|------|--------|----------|
| Project bootstrapped (Next.js 14, TypeScript) | ✅ Done | [`package.json`](file:///e:/React/Shelter/ShelterApp%20ui/package.json) |
| PWA manifest and service worker registration | ✅ Done | [`manifest.ts`](file:///e:/React/Shelter/ShelterApp%20ui/src/app/manifest.ts) |
| PublicShell layout (topbar, back nav, help menu, install button) | ✅ Done | [`PublicShell/index.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/components/public/PublicShell/index.tsx) |
| ChatInterface (conversation turns, send message, SSE events) | ✅ Done | [`ChatInterface/index.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/components/public/ChatInterface/index.tsx) |
| MessageInput component | ✅ Done | [`MessageInput.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/components/public/ChatInterface/MessageInput.tsx) |
| MessageList component | ✅ Done | [`MessageList.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/components/public/ChatInterface/MessageList.tsx) |
| Frontend API client (session, send message, upload image) | ✅ Done | [`client.ts`](file:///e:/React/Shelter/ShelterApp%20ui/src/lib/api/client.ts) |
| use-pwa hook | ✅ Done | [`use-pwa.ts`](file:///e:/React/Shelter/ShelterApp%20ui/src/hooks/use-pwa.ts) |
| Global CSS (design tokens, dark theme, agent workspace layout) | ✅ Done | [`globals.css`](file:///e:/React/Shelter/ShelterApp%20ui/src/app/globals.css) |
| Home page renders Single Landing Page (3 scenario cards) | ✅ Done | [`(public)/page.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/app/%28public%29/page.tsx) |
| LandingPage component (scenario selection, registered child list, add new) | ✅ Done | [`LandingPage/index.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/components/public/LandingPage/index.tsx) |
| Skeleton routes for: chat, report, help, faq, contact, privacy, terms, settings | ✅ Done (stubs) | `(public)/*` |
| Shelter admin routes (dashboard, cases, search, ai, people, shelters, activity) | ✅ Done (stubs) | `shelter/*` |
| PwaRegister.tsx shared component | ✅ Done | [`PwaRegister.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/components/shared/PwaRegister.tsx) |

**Currently missing from UI:**
- No `request_information` event handler → no inline form rendering
- No `request_image` event handler → no image upload in chat flow
- No `review_pending` event rendered as a styled card
- `shelter/` admin dashboard has zero real content
- `src/components/ui/` folder is **completely empty** (only `.gitkeep`)
- No `sendFormResponse()` in the API client

---

### Workspace 2 — ShelterAppUiBackend (FastAPI)

| Area | Status | Key File |
|------|--------|----------|
| FastAPI app factory with CORS, lifespan | ✅ Done | [`app/main.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/main.py) |
| `POST /api/sessions` — create session + JWT token | ✅ Done | [`routes/sessions.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/routes/sessions.py) |
| `POST /api/sessions/{id}/messages` — send message + proxy to agent | ✅ Done | [`routes/messages.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/routes/messages.py) |
| `GET /api/sessions/{id}/events` — SSE event stream | ✅ Done | [`routes/events.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/routes/events.py) |
| `POST /api/sessions/{id}/images` — image upload with safety scan + storage | ✅ Done | [`routes/images.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/routes/images.py) |
| AgentClient (HTTP proxy to WayFindMCPClient) | ✅ Done | [`services/agent_client.py`](file:///e:/React/Shelter/ShelterAppUiBackend/services/agent_client.py) |
| EventBroker (in-memory SSE publisher) | ✅ Done | [`services/event_broker.py`](file:///e:/React/Shelter/ShelterAppUiBackend/services/event_broker.py) |
| ImageService (validate, safety scan, store) | ✅ Done | [`services/image_service.py`](file:///e:/React/Shelter/ShelterAppUiBackend/services/image_service.py) |
| Session auth (verify JWT Bearer token) | ✅ Done | [`app/auth.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/auth.py) |
| Rate limiter (message + image rate limits per session) | ✅ Done | [`app/rate_limit.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/rate_limit.py) |
| SessionStore (Redis-backed) | ✅ Done | [`app/session.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/session.py) |
| Pydantic schemas (message, image) | ✅ Done | `schemas/` |

**Currently missing from ShelterAppUiBackend:**
- No `/api/sessions/{id}/form-response` route for `user_form_response` event
- No `/api/admin/*` routes for shelter staff (review queue, case management)
- No masked communication bridge (Twilio) endpoints
- No two-phase notification dispatcher
- EventBroker is in-memory — not durable across restarts or multiple workers

---

### Workspace 3 — WayFindMCPClient (FastAPI + LangGraph + FastMCP)

| Area | Status | Key File |
|------|--------|----------|
| FastAPI app factory (internal-only, X-Internal-Key auth middleware) | ✅ Done | [`app/main.py`](file:///e:/React/Shelter/WayFindMCPClient/app/main.py) |
| `POST /internal/sessions/{id}/events` route | ✅ Done | [`app/routes/agent.py`](file:///e:/React/Shelter/WayFindMCPClient/app/routes/agent.py) |
| Session merge logic (`user_message`, `user_image`, `user_form_response`) | ✅ Done | [`_merge_event()`](file:///e:/React/Shelter/WayFindMCPClient/app/routes/agent.py#L152-L196) |
| Session store (memory + Redis backends) | ✅ Done | [`app/session.py`](file:///e:/React/Shelter/WayFindMCPClient/app/session.py) |
| `WayfindState` — full 19-field TypedDict with all reducers | ✅ Done | [`agent/state.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/state.py) |
| Intent enum (6 values: MISSING_CHILD, FOUND_CHILD, SHELTER_SEARCH, GUIDANCE, CASE_STATUS, UNKNOWN) | ✅ Done | [`state.py L34`](file:///e:/React/Shelter/WayFindMCPClient/agent/state.py#L34-L50) |
| 4 router functions (completeness, intent, candidate, confidence) | ✅ Done | [`state.py L267`](file:///e:/React/Shelter/WayFindMCPClient/agent/state.py#L267-L321) |
| Full 19-node LangGraph compiled graph with all edges | ✅ Done | [`agent/graph.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/graph.py) |
| **understand_intent** — LLM classifies intent + fallback keyword matching | ✅ Done | [`nodes/understand_intent.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/understand_intent.py) |
| **extract_structured_data** — LLM extracts ChildSearchCriteria / FoundChildReport | ✅ Done | [`nodes/extract_structured_data.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/extract_structured_data.py) |
| **check_completeness** — deterministic field checker (FULL IMPLEMENTATION) | ✅ Done | [`nodes/check_completeness.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/check_completeness.py) |
| **ask_followup** node | ✅ Done | [`nodes/ask_followup.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/ask_followup.py) |
| **route_intent** node | ✅ Done | [`nodes/route_intent.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/route_intent.py) |
| **search_metadata** node | ✅ Done | [`nodes/search_metadata.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/search_metadata.py) |
| **evaluate_candidates** node | ✅ Done | [`nodes/evaluate_candidates.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/evaluate_candidates.py) |
| **image_match** node | ✅ Done | [`nodes/image_match.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/image_match.py) |
| **evaluate_evidence** — FULL deterministic composite scoring with YAML weights | ✅ Done | [`nodes/evaluate_evidence.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/evaluate_evidence.py) |
| **route_by_confidence** node | ✅ Done | [`nodes/route_by_confidence.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/route_by_confidence.py) |
| **human_review** — builds evidence package, calls ReviewService, trauma-safe messages | ✅ Done | [`nodes/human_review.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/human_review.py) |
| **no_match** node | ✅ Done | [`nodes/no_match.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/no_match.py) |
| **found_child_extract** node | ✅ Done | [`nodes/found_child_extract.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/found_child_extract.py) |
| **safety_guidance** — fetches finder guidance via MCP / static YAML | ✅ Done | [`nodes/safety_guidance.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/safety_guidance.py) |
| **submit_found_child** node | ✅ Done | [`nodes/submit_found_child.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/submit_found_child.py) |
| **search_support_node** node | ✅ Done | [`nodes/search_support.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/search_support.py) |
| **get_guidance_node** node | ✅ Done | [`nodes/get_guidance.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/get_guidance.py) |
| **get_case_status_node** node | ✅ Done | [`nodes/get_case_status.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/get_case_status.py) |
| **generate_response** node | ✅ Done | [`nodes/generate_response.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/generate_response.py) |
| WayfindLLM — Gemini wrapper (IntentResult, ChildCriteria, FoundChildReport, followup) | ✅ Done | [`mcp_client/llm.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_client/llm.py) |
| WayfindMCPClient — typed client for 6 MCP tools, SSE + in-process | ✅ Done | [`mcp_client/client.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_client/client.py) |
| FastMCP server registered with 6 tools | ✅ Done | [`mcp_server/server.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/server.py) |
| MCP Tool 1: `search_child_records` — metadata search + mock fallback | ✅ Done | [`tools/search_child_records.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/search_child_records.py) |
| MCP Tool 2: `image_match_candidates` | ✅ Done | [`tools/image_match_candidates.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/image_match_candidates.py) |
| MCP Tool 3: `submit_found_child_report` | ✅ Done | [`tools/submit_found_child_report.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/submit_found_child_report.py) |
| MCP Tool 4: `search_support` | ✅ Done | [`tools/search_support.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/search_support.py) |
| MCP Tool 5: `get_guidance` — RAG + static YAML fallback | ✅ Done | [`tools/get_guidance.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/get_guidance.py) |
| MCP Tool 6: `get_case_status` | ✅ Done | [`tools/get_case_status.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/get_case_status.py) |
| Service clients — PostgresClient, RagClient, ImageBackendClient, ReviewService, SupportClient | ✅ Done | `services/*.py` |
| All Pydantic schemas (child, event, evidence, candidates, case, guidance, image, review, support, location) | ✅ Done | `schemas/*.py` |
| Evidence weights YAML | ✅ Done | [`config/evidence_weights.yaml`](file:///e:/React/Shelter/WayFindMCPClient/config/evidence_weights.yaml) |
| Static guidance YAML | ✅ Done | [`config/static_guidance.yaml`](file:///e:/React/Shelter/WayFindMCPClient/config/static_guidance.yaml) |
| Internal API integration tests | ✅ Done | [`tests/test_internal_api.py`](file:///e:/React/Shelter/WayFindMCPClient/tests/test_internal_api.py) |

---

## ❌ WHAT NEEDS TO BE DONE — By Priority

---

### PRIORITY 1 (RED) — Three Form Flows & Bot Intake

This is the biggest missing piece from your new idea. The agent already handles all 3 intents conversationally through the graph, but the **frontend form handshake and dedicated entry pages** are not built.

#### 1A. `request_information` Event Renderer in ChatInterface

**Problem:** The agent emits `request_information` with a `fields` array (e.g. `["age", "last_seen_location", "gender"]`) but [`ChatInterface/index.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/components/public/ChatInterface/index.tsx) completely ignores this event type. It only handles `assistant_message`, `error`, and `submission_complete`.

**What to build:**
- Detect `request_information` in the event loop
- Render a structured mini-form inline in the chat with appropriate input types per field
- Each field must have an **"Unknown / Don't Know"** toggle that serializes that field as `null`
- On submit → call `sendFormResponse()` which posts a `user_form_response` event with `form_data: {...}`
- This is already handled end-to-end on the backend: `_merge_event()` in [`app/routes/agent.py`](file:///e:/React/Shelter/WayFindMCPClient/app/routes/agent.py#L177-L187) unpacks `form_data` into `last_form_data` state, and [`extract_structured_data.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/extract_structured_data.py) merges it into `ChildSearchCriteria` / `FoundChildReport`

**Field → Input type mapping needed:**
```
gender        → radio (male / female / unknown + "Don't know" toggle)
age           → number input (+ "Don't know" toggle)
last_seen_location / found_location → text input
hair_color, eye_color, skin_tone → text or select
clothing      → multi-tag text input
```

**Files to modify:**
- [`ChatInterface/index.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/components/public/ChatInterface/index.tsx) — add `request_information` case
- [`lib/api/client.ts`](file:///e:/React/Shelter/ShelterApp%20ui/src/lib/api/client.ts) — add `sendFormResponse(formData)` function

#### 1B. `request_image` Event Handler

**Problem:** Agent emits `request_image` when it needs a photo (post metadata search), but there is no camera/file input anywhere in the chat UI.

**What to build:**
- Inline photo upload prompt triggered when `request_image` is received
- `<input type="file" accept="image/*" capture="environment">` for mobile camera
- On file select → call `uploadImage()` (already in [`client.ts`](file:///e:/React/Shelter/ShelterApp%20ui/src/lib/api/client.ts#L160)) → get `mediaId`
- Send `user_image` event with `media_id` (already handled by `_merge_event` → sets `media_reference` in state)

#### 1C. `review_pending` Styled Card

**Problem:** Agent emits `review_pending` with `case_reference` but front-end renders nothing.

**What to build:**
- Styled notification card displaying the case reference number
- Copy-to-clipboard button
- Clear message: "Your case is under human review. Keep this reference number."
- Link to `/report` for updates

#### 1D. Single Landing Page & Scenario Card Architecture

A **single landing page** replaces the previous chat-first home page. When users land on Wayfind, they see three distinct scenario cards:

```
┌─────────────────────────────────────────────────────────────┐
│                      WAYFIND HOME ( / )                     │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ 🟢 I want to register my child on Wayfind           │   │
│   │    Child pre-registration flow (REGISTERED_SAFE)    │   │
│   └─────────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ 🔴 I am looking for my lost child                   │   │
│   │    • If registered children exist: list by name     │   │
│   │    • Option: "+ Add / Search for another child"     │   │
│   │    • Else: straight to emergency/cold-case search   │   │
│   └─────────────────────────────────────────────────────┘   │
│   ┌─────────────────────────────────────────────────────┐   │
│   │ 🔵 I just found a lost child                        │   │
│   │    Immediate safety guidance + report intake flow   │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Scenario Card Details & Pre-Seeded AI Flow:**

1. **"I want to register my child on Wayfind"**
   - **Intent:** `REGISTERED_SAFE`
   - **Pre-seed:** "I want to pre-register my child on Wayfind as a proactive safety measure."
   - **Flow:** Light, progressive intake collecting baseline physical attributes, emergency contacts, and optional baseline photo.

2. **"I am looking for my lost child"**
   - **Intent:** `MISSING_CHILD`
   - **Child Selection / Multi-Child Support:** If the guardian already has registered children in their account, a selector lists them by name. Tapping a child launches the search with that child's profile already pre-populated.
   - **Looking for someone else's child / New Child:** Users can tap "+ Register / Search for another child" to enter details directly.
   - **Pre-seed:** "My child is missing. I need immediate help finding them." (Or child-specific: "My registered child [Name] is missing. Last seen at...")
   - **Flow:** De-escalation guidance, last-seen location/time capture, immediate temporal window search across found reports and shelters.

3. **"I just found a lost child"**
   - **Intent:** `FOUND_CHILD`
   - **Pre-seed:** "I just found an unaccompanied lost child. What should I do right now?"
   - **Flow:** Immediate trauma-informed safety protocol (stay in well-lit public area, alert security, call 1098/police) followed by progressive intake of child's visible attributes and intake photo.

**Light, Progressive UX Philosophy:**
- **No long forms dumped on user:** In high-stress or emergency moments, long rigid forms cause panic or abandonment.
- All information is gathered via structured mini-prompts (`request_information`) with explicit **"Unknown"** toggles that serialize to `null`.
- The user is guided step-by-step with real-time feedback.

> [!IMPORTANT]
> Cold case searches (child lost 10 years ago) are already architecturally supported. `ChildSearchCriteria.date_missing` accepts any past ISO date. The temporal window expands automatically based on how old the missing report is. No special code path is needed.

#### 1E. Backend: Form Response Route

**Problem:** [`routes/messages.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/routes/messages.py) only supports `user_message` type. Form submissions need `user_form_response` with `form_data: dict`.

**Simplest fix:** Extend the `MessageRequest` body schema to accept optional `form_data: dict | None`. When `form_data` is present, set event type to `user_form_response` before proxying to agent.

---

### PRIORITY 2 (RED) — Real PostgreSQL Database Integration

All MCP tools and service clients operate on **mock data**. The actual persistence layer does not exist.

#### 2A. Database Schema and Migrations

**Tables needed (PostgreSQL 16 + PostGIS):**

```sql
-- Core entities
guardians           (id UUID PK, name, phone_masked, national_id_hash, created_at)
children            (id UUID PK, guardian_id FK, name, dob, gender,
                     status ENUM[REGISTERED_SAFE, MISSING, FOUND], created_at)
physical_attributes (child_id FK, height_cm, hair_color, eye_color, skin_tone,
                     identifying_features TEXT[])
baseline_photos     (child_id FK, s3_key, embedding_vector VECTOR(512), uploaded_at)

-- Active case operations
sos_beacons         (id UUID PK, child_id FK, activated_at, date_missing,
                     last_seen_location GEOGRAPHY(POINT), status)
found_child_cases   (id UUID PK, case_reference TEXT UNIQUE,
                     found_location GEOGRAPHY(POINT), found_at TIMESTAMPTZ,
                     status, reporter_name, reporter_contact_masked)
intake_photos       (case_id FK, s3_key, embedding_vector VECTOR(512), uploaded_at)

-- Matching and Review
match_candidates    (search_session_id, case_id FK, metadata_score FLOAT, composite_score FLOAT, tier)
review_queue        (id UUID PK, case_reference TEXT, tier, evidence_json JSONB,
                     agent_session_id, staff_id, decision, created_at)

-- Audit (immutable)
audit_log           (id BIGSERIAL PK, action, entity_type, entity_id, user_id,
                     metadata_json JSONB, created_at TIMESTAMPTZ DEFAULT NOW())
```

**What to build:**
- Alembic migration files for all tables above
- SQLAlchemy async ORM models or raw asyncpg queries
- Backend service exposing the 3 endpoints already expected by `PostgresClient`:
  - `POST /api/children/search` → called by [`PostgresClient.search_children()`](file:///e:/React/Shelter/WayFindMCPClient/services/postgres_client.py#L51)
  - `POST /api/children/found` → called by [`PostgresClient.submit_found_child()`](file:///e:/React/Shelter/WayFindMCPClient/services/postgres_client.py#L97)
  - `GET /api/cases/{reference}` → called by [`PostgresClient.get_public_case_status()`](file:///e:/React/Shelter/WayFindMCPClient/services/postgres_client.py#L131)

#### 2B. Child Registration API (Form 1 — REGISTERED_SAFE)

No endpoint currently exists to handle Form 1 (pre-registration of safe children by guardians). This is a **direct REST flow**, not through the AI agent.

**What to build:**
- `POST /api/guardians/register-child` — accepts guardian details + child physical data + baseline photo
- Sets child status to `REGISTERED_SAFE`
- Triggers async InsightFace embedding computation for baseline photo
- Stores embedding in `baseline_photos.embedding_vector`
- Returns a guardian dashboard reference

---

### PRIORITY 3 (RED) — InsightFace Biometric Vision Service

The [`image_match_candidates`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/image_match_candidates.py) MCP tool calls [`ImageBackendClient.compare()`](file:///e:/React/Shelter/WayFindMCPClient/services/image_backend_client.py#L45) which calls `POST /api/images/compare`. **This endpoint does not exist.**

**What to build:**
- A Python FastAPI service running InsightFace ArcFace
- Input: `{"media_id": "...", "candidate_case_ids": ["WF-CASE-XXX", ...]}`
- Process:
  1. Load query image bytes from S3 by `media_id`
  2. Compute 512-D ArcFace embedding for query image
  3. Fetch pre-stored embeddings for each `candidate_case_id` from DB
  4. Compute cosine similarity for each pair
- Output: `{"matches": [{"candidate_case_id": "...", "similarity_score": 0.88, "model_version": "arcface-r100", ...}]}`
- **Critical guardrail:** ONLY compare against the passed-in candidate IDs — no full database scan ever

---

### PRIORITY 4 (YELLOW) — RAG Knowledge Base (Qdrant)

[`get_guidance()`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/get_guidance.py) calls `RagClient.query()` which calls `POST /api/guidance/query`. **This endpoint does not exist.** The static fallback already works well for MVP.

**What to build:**
- Qdrant collection with embedded guidance documents (child protection law, shelter directories, helplines, cold-case procedures, finder protocols, 1098 child helpline, emergency procedures)
- Embedding pipeline using `text-embedding-004` (Gemini) or `all-MiniLM-L6-v2`
- Query API service: `POST /api/guidance/query` → semantic search → top-k chunks → return `GuidanceResult`

---

### PRIORITY 5 (YELLOW) — Shelter Staff Admin Panel

All `shelter/` routes exist as stubs. Zero functional content.

**What to build per page:**

**`/shelter/dashboard`:**
- Summary stat cards: active SOS beacons, pending review count, found cases today, resolved cases this week
- Real-time activity feed using SSE

**`/shelter/cases` (Review Queue):**
- Paginated list of review queue items fetched from `ReviewService`
- Each item: confidence tier badge (UNCERTAIN / HIGH), key matching factors summary, candidate case preview
- Actions: **Approve Match** → triggers Phase 2 notification | **Reject** → routes to no-match response

**`/shelter/search`:**
- Manual child record search form for staff
- Direct DB query (bypasses agent)

**`/shelter/ai` (Session Monitor):**
- Live view of active agent sessions (read-only for safety oversight)

**Backend admin routes needed in ShelterAppUiBackend:**
```
GET  /api/admin/review-queue       — list pending review cases
POST /api/admin/review/{id}/approve — approve match, trigger Phase 2 notifications
POST /api/admin/review/{id}/reject  — reject, send no-match response
GET  /api/admin/cases              — paginated case list
GET  /api/admin/stats              — dashboard summary stats
```

---

### PRIORITY 6 (YELLOW) — Two-Phase Notification System

Described in architecture and guardrails but **not implemented anywhere** in code.

**Phase 1 — Immediate (triggered by `human_review` node submitting to queue):**
- SMS to guardian: "Potential match detected. Verifying now. Reference: WF-XXXXX"
- Twilio SMS API call

**Phase 2 — After staff approval:**
- **Path A (Child at shelter):** SMS to guardian with shelter address + desk contact + case passkey
- **Path B (Child with finder):** Masked call link to both parties via Twilio Voice/SMS Proxy

**Where to build:**
- New `services/notification_service.py` in ShelterAppUiBackend
- Called from `/api/admin/review/{id}/approve` endpoint

---

### PRIORITY 7 (YELLOW) — Masked Communication Bridge

Privacy guardrail: raw phone numbers must NEVER be exposed. All calls/SMS must go through Twilio Proxy.

**What to build:**
- Twilio Proxy session creation when a match is approved
- Unique masked proxy numbers generated per guardian-finder pair
- Proxy session ID stored in case record
- Masked call link sent to both parties

---

### PRIORITY 8 (YELLOW) — Redis Pub/Sub EventBroker

**Current limitation:** `EventBroker` in ShelterAppUiBackend is an in-memory `asyncio.Queue`. Multiple uvicorn workers cannot share queues; events are lost on restart.

**What to build:**
- Replace with Redis Pub/Sub
- `push()` → `redis.publish(f"events:{session_id}", json.dumps(event))`
- `consume()` → async generator over `redis.subscribe(f"events:{session_id}")`

---

### PRIORITY 9 (GREEN) — Testing Suite

| Test | Status | Notes |
|------|--------|-------|
| Internal API auth tests | ✅ Done | [`test_internal_api.py`](file:///e:/React/Shelter/WayFindMCPClient/tests/test_internal_api.py) |
| LangGraph node unit tests | ❌ Missing | Test each of the 19 nodes in isolation |
| End-to-end graph run tests (missing_child, found_child flows) | ❌ Missing | |
| Frontend component tests | ❌ Missing | Test ChatInterface event rendering |
| Evidence scoring unit tests | ❌ Missing | Test composite score + tier routing |
| Load/concurrency tests | ❌ Missing | Multiple concurrent sessions |

---

### PRIORITY 10 (GREEN) — DevOps & Deployment

| Item | Status |
|------|--------|
| Docker Compose (all services + Redis + PostgreSQL + Qdrant) | ❌ Missing |
| `.env.example` files documented | ✅ Done |
| GitHub Actions CI pipeline | ❌ Missing |
| NGINX reverse proxy config | ❌ Missing |
| AES-256 GCM encryption at rest for PII fields | ❌ Missing |
| Immutable tamper-evident audit logging | ❌ Partial (logging calls exist, no immutable store) |

---

## Recommended Build Order

```
Phase A — MVP Visible in Browser (Start Here)
  1. ChatInterface: handle request_information → render inline null-tolerant form → send user_form_response
  2. ChatInterface: handle request_image → file upload → send user_image
  3. ChatInterface: handle review_pending → styled case reference card
  4. ShelterAppUiBackend: extend /messages to support user_form_response event type
  5. Single Landing Page with 3 scenario cards & pre-seeded conversational intake

Phase B — Core Data Layer
  6. PostgreSQL schema + PostGIS + Alembic migrations
  7. Child registration API (Form 1 — REGISTERED_SAFE)
  8. Connect PostgresClient to real DB (all 3 endpoints)
  9. S3 photo storage for baseline and found-child photos

Phase C — AI Enhancement
  10. InsightFace image comparison service (port 8003)
  11. Qdrant RAG service + document ingest pipeline (port 8002)
  12. Wire image_backend_client and rag_client to live endpoints

Phase D — Operations & Communications
  13. Twilio SMS Phase 1 notifications
  14. Twilio Voice Proxy for masked communication bridge
  15. Redis Pub/Sub EventBroker for multi-worker durability

Phase E — Admin & Oversight
  16. Shelter staff admin panel (review queue, case management, dashboard)
  17. Backend admin API routes

Phase F — Hardening & Production
  18. AES-256 field-level encryption for PII
  19. Immutable audit log
  20. Full test suite + Docker Compose + CI/CD
```

---

## Critical Key Files Reference

| File | What It Does |
|------|-------------|
| [`agent/graph.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/graph.py) | `build_graph()` — wires all 19 LangGraph nodes; the central pipeline definition |
| [`agent/state.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/state.py) | `WayfindState` TypedDict + 4 router functions; the full data contract |
| [`nodes/understand_intent.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/understand_intent.py) | LLM classifies user message into one of 6 intents |
| [`nodes/extract_structured_data.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/extract_structured_data.py) | LLM builds/merges ChildSearchCriteria or FoundChildReport across turns |
| [`nodes/check_completeness.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/check_completeness.py) | Deterministic check of required fields; emits request_information events |
| [`nodes/evaluate_evidence.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/evaluate_evidence.py) | Deterministic composite scoring: metadata + image + geo + temporal weights |
| [`nodes/human_review.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/human_review.py) | Builds evidence package, calls ReviewService, sends trauma-safe message |
| [`nodes/safety_guidance.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/safety_guidance.py) | Fetches finder guidance (MCP or static YAML) before submitting found-child report |
| [`mcp_client/llm.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_client/llm.py) | WayfindLLM — Gemini structured output for intent, criteria, and followup generation |
| [`mcp_client/client.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_client/client.py) | WayfindMCPClient — typed wrapper for all 6 MCP tools with fallbacks |
| [`mcp_server/server.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/server.py) | FastMCP server — registers all 6 tools |
| [`mcp_server/tools/search_child_records.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/search_child_records.py) | Metadata query → PostgresClient.search_children() → mock fallback |
| [`mcp_server/tools/get_guidance.py`](file:///e:/React/Shelter/WayFindMCPClient/mcp_server/tools/get_guidance.py) | RAG query → RagClient.query() → static YAML fallback |
| [`services/postgres_client.py`](file:///e:/React/Shelter/WayFindMCPClient/services/postgres_client.py) | HTTP client for child records DB; mock fallback until DB is built |
| [`services/image_backend_client.py`](file:///e:/React/Shelter/WayFindMCPClient/services/image_backend_client.py) | HTTP client for InsightFace service; mock fallback |
| [`services/review_service.py`](file:///e:/React/Shelter/WayFindMCPClient/services/review_service.py) | HTTP client for human review queue submission; mock fallback |
| [`services/rag_client.py`](file:///e:/React/Shelter/WayFindMCPClient/services/rag_client.py) | HTTP client for Qdrant vector search; mock fallback |
| [`app/routes/agent.py`](file:///e:/React/Shelter/WayFindMCPClient/app/routes/agent.py) | `handle_event()` — load state → merge event → run graph → save → return events |
| [`app/routes/agent.py L152`](file:///e:/React/Shelter/WayFindMCPClient/app/routes/agent.py#L152-L196) | `_merge_event()` — maps event types to state fields |
| [`ShelterAppUiBackend/services/agent_client.py`](file:///e:/React/Shelter/ShelterAppUiBackend/services/agent_client.py) | `send_event()` — proxies all events to internal WayFindMCPClient |
| [`ShelterAppUiBackend/app/routes/events.py`](file:///e:/React/Shelter/ShelterAppUiBackend/app/routes/events.py) | `stream_events()` — SSE stream draining EventBroker |
| [`src/lib/api/client.ts`](file:///e:/React/Shelter/ShelterApp%20ui/src/lib/api/client.ts) | All frontend→backend HTTP calls (session, message, image) |
| [`ChatInterface/index.tsx`](file:///e:/React/Shelter/ShelterApp%20ui/src/components/public/ChatInterface/index.tsx) | Main conversational UI — handles only 3 of 8 event types currently |
| [`schemas/child.py`](file:///e:/React/Shelter/WayFindMCPClient/schemas/child.py) | ChildSearchCriteria + FoundChildReport + AgeRange + HeightRange |
| [`config/evidence_weights.yaml`](file:///e:/React/Shelter/WayFindMCPClient/config/evidence_weights.yaml) | Composite scoring weights — tune here without touching code |

---

## Known Bugs Found During Audit

> [!WARNING]
> **Bug in `safety_guidance.py` L69:** Code accesses `result.guidance_text` but `GuidanceResult` schema has the field named `guidance`, not `guidance_text`. This will raise `AttributeError` when the MCP client is live. **Fix:** change `result.guidance_text` → `result.guidance` in [`nodes/safety_guidance.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/safety_guidance.py#L69).

> [!WARNING]
> **Placeholder score in `evaluate_evidence.py` L113:** `metadata_score = 0.60` is hardcoded. When PostgresClient returns real `Candidate.metadata_match_score`, this line must read that value from the top candidate. The comment in the file already flags this.

> [!WARNING]
> **Duplicate route registration in `WayFindMCPClient/app/main.py`:** `_add_health_route(app)` is called at line 139 (inside `create_app()`) AND again at line 226 (module level). This double-registers the `/health` endpoint. Remove the call at line 226.

> [!NOTE]
> **Cold-case searches are architecturally supported with no extra work.** `ChildSearchCriteria.date_missing` is nullable, and `check_completeness` only requires `gender + age + last_seen_location`. A guardian who lost a child 10 years ago can search with just those three fields — the temporal window in the scoring engine expands accordingly.

> [!NOTE]
> **MCP transport defaults to SSE** (`MCP_TRANSPORT=sse`, port 9000). For local development, set `MCP_TRANSPORT=inprocess` or inject the `mcp_server` FastMCP instance directly into `WayfindMCPClient(mcp_server=mcp)` to avoid needing a running MCP server process.
