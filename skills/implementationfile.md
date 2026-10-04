# Wayfind — Master Implementation Plan

**Date:** 2026-10-04  
**Author:** Antigravity  
**Workspaces:** `ShelterApp ui` (Next.js 14), `ShelterAppUiBackend` (FastAPI), `WayFindMCPClient` (FastAPI + LangGraph + FastMCP)

---

## 🧭 Architecture & Design Philosophy

1. **Single Landing Page with 3 Scenario Cards:**
   - **🟢 I want to register my child on Wayfind** → Child pre-registration flow (`REGISTERED_SAFE`).
   - **🔴 I am looking for my lost child** → If registered children exist, lists them by name with option to select or add new; if none exist, flows straight to search/reporting.
   - **🔵 I just found a lost child** → Immediate safety guidance + report intake.
2. **Pre-Seeded Conversational AI Intake:**
   - Selecting a scenario transitions to the chat assistant with the user's intent pre-seeded.
3. **Light, Progressive UX:**
   - No overwhelming long static forms dumped at once.
   - Information gathered progressively through guided conversational turns and inline mini-forms (`request_information`) with explicit **"Unknown / Don't Know"** toggles that serialize to `null`.
4. **Deterministic Multi-Attribute Scoring & Temporal Window:**
   - Mathematical composite scoring (metadata, temporal, geographic, and cascaded biometric vision).
   - Bounds search space $[T_{\text{lost}} - \Delta t \to \text{Now}]$ without scanning full databases or safe registered profiles.
5. **Human-in-the-Loop Staff Review & Progressive Alerts:**
   - High confidence candidate matches are held in a staff review queue before disclosing identity or location.
   - Phase 1 immediate acknowledgment; Phase 2 verified rescue or masked Twilio proxy bridge.

---

## 📅 Phased Implementation Roadmap

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ Phase 1: End-to-End Browser Flow (Zero External Dependencies — Mock-Backed)           │
│   • Inline dynamic form prompts (`request_information`) with "Unknown" toggles         │
│   • Inline photo capture (`request_image`) & Case Reference Card (`review_pending`)    │
│   • Backend `user_form_response` event bridge & audit bug fixes                        │
│   • Pre-seeded flow verification from the Single Landing Page                          │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Phase 2: PostgreSQL Persistence & Child Registration                                   │
│   • PostgreSQL 16 + PostGIS schema (Guardians, Children, SOS Beacons, Found Cases)    │
│   • Live `PostgresClient` queries replacing mock records                               │
│   • Child Pre-Registration REST API (`REGISTERED_SAFE`)                               │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Phase 3: Biometric AI & Knowledge Vector Base                                          │
│   • InsightFace 512-D ArcFace embedding service (Top 3-5 candidate matching only)     │
│   • Qdrant Vector Store + RAG for local laws, helpline 1098 & shelter directories      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Phase 4: Shelter Staff Portal & Progressive Alerts                                     │
│   • Human-in-the-Loop staff review queue UI (`/shelter/cases`)                         │
│   • Phase 1 (Immediate notification) & Phase 2 (Verified rescue / Masked call)         │
│   • Twilio Voice/SMS proxy bridge                                                      │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ Phase 5: Production Hardening, Encryption & Docker Deploy                             │
│   • AES-256 field encryption for child PII                                             │
│   • Redis Pub/Sub durable SSE event broker                                             │
│   • Docker Compose orchestration for all microservices                                 │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Phase 1: Interactive Browser Flow & Agent Handshake (Current Focus)

- [ ] **Agent Core Bug Fixes:**
  - Fix [`agent/nodes/safety_guidance.py`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/safety_guidance.py): change `result.guidance_text` to `result.guidance`.
  - Fix [`app/main.py`](file:///e:/React/Shelter/WayFindMCPClient/app/main.py): remove duplicate `_add_health_route(app)` call at module level.
- [ ] **Backend Event Bridge (`ShelterAppUiBackend`):**
  - Update `MessageRequest` schema to support optional `form_data: dict | None`.
  - Route `user_form_response` event to `agent_client.send_event()`.
- [ ] **Frontend Handshake (`ShelterApp ui`):**
  - Add `sendFormResponse(sessionId, formData)` in `src/lib/api/client.ts`.
  - Update `ChatInterface` to render:
    - Dynamic inline form on `request_information` event with per-field "Unknown" toggles.
    - Inline photo upload prompt on `request_image` event.
    - Styled reference card on `review_pending` event.
  - Verify seamless transition from the 3 landing page scenario cards.

---

### Phase 2: PostgreSQL Persistence & Child Registration

- [ ] **PostgreSQL 16 + PostGIS Setup:**
  - Create Alembic migrations for `guardians`, `children`, `physical_attributes`, `baseline_photos`, `sos_beacons`, `found_child_cases`, `intake_photos`, `review_queue`, `audit_log`.
- [ ] **Live Service Endpoints in Backend:**
  - `POST /api/children/search` (temporal window + dynamic null-pruning query).
  - `POST /api/children/found` (intake record registration).
  - `GET /api/cases/{reference}` (public case status query).
- [ ] **Child Pre-Registration API:**
  - `POST /api/guardians/register-child` to register safe baseline profiles (`REGISTERED_SAFE`).

---

### Phase 3: Biometric Vision AI & RAG Knowledge Base

- [ ] **InsightFace Vision Service (Port 8003):**
  - Fast FastAPI service executing ArcFace 512-D embeddings.
  - Compares query image strictly against top 3–5 shortlisted candidate IDs (no full table scans).
- [ ] **Qdrant Vector Database (Port 8002):**
  - Ingestion pipeline for child protection SOPs, helpline numbers (1098), and shelter directories.
  - Vector similarity query endpoint for `RagClient`.

---

### Phase 4: Shelter Staff Portal & Progressive Alerts

- [ ] **Shelter Staff Dashboard (`/shelter/cases`):**
  - Review queue for candidate matches with score breakdowns.
  - Staff actions: **Approve Match** (triggers Phase 2 alerts) or **Reject** (routes to no match).
- [ ] **Two-Phase Notification Engine:**
  - Phase 1 immediate acknowledgment SMS.
  - Phase 2 verified shelter address + passkey dispatch.
- [ ] **Twilio Masked Proxy Bridge:**
  - Anonymized voice and SMS bridge between finder and guardian.

---

### Phase 5: Production Hardening & DevOps

- [ ] **Security & Cryptography:**
  - AES-256 GCM field-level encryption for guardian phone numbers, national IDs, and exact coordinates.
- [ ] **Infrastructure & Durability:**
  - Redis Pub/Sub for cross-worker durable SSE streams.
  - Docker Compose file connecting Next.js, FastAPI Gateway, LangGraph Agent, PostgreSQL, Redis, Qdrant, and InsightFace.

---

## 🔑 Configuration & Environment Matrix

| Secret / Config Key | Destination | Default / Fallback | Production Requirement |
|---|---|---|---|
| `GEMINI_API_KEY` | `WayFindMCPClient/.env` | None (required for LLM) | Live Gemini API key |
| `DATABASE_URL` | `ShelterAppUiBackend/.env` | Mock memory in `PostgresClient` | `postgresql+asyncpg://user:pass@host:5432/wayfind` |
| `REDIS_URL` | Backend & Agent `.env` | In-memory session fallback | `redis://localhost:6379/0` |
| `S3_BUCKET` / `R2_BUCKET` | `ShelterAppUiBackend/.env` | Local temporary directory | S3 / Cloudflare R2 bucket credentials |
| `TWILIO_ACCOUNT_SID` & `TOKEN` | `ShelterAppUiBackend/.env` | Mock logger | Live Twilio credentials for SMS/Voice |
| `QDRANT_URL` & `API_KEY` | `WayFindMCPClient/.env` | Static YAML fallback | Live Qdrant cluster |
