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

### Phase 1: Interactive Browser Flow & Agent Handshake (✅ COMPLETED)

- [x] **Agent Core Bug Fixes:** Fixed `result.guidance` attribute and removed duplicate health route.
- [x] **Backend Event Bridge (`ShelterAppUiBackend`):** Handled `user_form_response` & `user_image` events.
- [x] **Frontend Handshake (`ShelterApp ui`):** Built `InlineFormCard`, `InlineImageUploadCard`, `InlineCaseReviewCard`, and wired `sendFormResponse()`.
- [x] **Zero Build Errors:** Verified Next.js 22 static pages build cleanly.

---

### Phase 2: PostgreSQL Persistence & Child Registration (✅ COMPLETED)

- [x] **PostgreSQL 16 + PostGIS Setup:** Created complete DDL schema script in [`db/schema.sql`](file:///e:/React/Shelter/ShelterAppUiBackend/db/schema.sql).
- [x] **Live Service Endpoints in Backend:** Implemented `POST /api/children/search`, `POST /api/children/found`, `GET /api/cases/{reference}`.
- [x] **Child Pre-Registration API:** Implemented `POST /api/guardians/register-child` and `GET /api/guardians/{id}/children`.
- [x] **Landing Page Drawer Sync:** Dynamic fetching and selection of registered children.

---

### Phase 3: Biometric Vision AI (Separate Service — To Be Done Later) & RAG Vector Base

> [!NOTE]
> **Biometric Vision Microservice Design & Future Integration:**
> The Biometric Face Embedding & Matching service will be built as a separate standalone microservice with two primary functions:
> 1. **Image to Vector (`POST /api/biometrics/embed`):** Computes 512-D ArcFace/InsightFace feature embedding vectors for baseline and intake photos.
> 2. **Candidate Matching (`POST /api/biometrics/match`):** Computes cosine similarity between query embedding and pre-filtered candidate vectors.
>
> **Decoupled Architecture & Guardrails:**
> - **Significance Gating:** Biometric scanning is **never called blindly or on full database scans**. It is triggered in [`evaluate_candidates`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/evaluate_candidates.py) **only if** `significance_score >= 0.60` (strong demographic/metadata match).
> - **Pure Deterministic Scoring (Zero LLM):** [`evaluate_evidence`](file:///e:/React/Shelter/WayFindMCPClient/agent/nodes/evaluate_evidence.py) evaluates evidence deterministically using normalized weights without LLM dependency.
> - **Loose Coupling:** The application uses [`ImageBackendClient`](file:///e:/React/Shelter/WayFindMCPClient/services/image_backend_client.py) with graceful mock fallback when `IMAGE_BACKEND_URL` is unconfigured.
>
> **How to wire the future Biometric service:**
> 1. Launch biometric service on `IMAGE_BACKEND_URL` (e.g. `http://localhost:8003`).
> 2. Set `IMAGE_BACKEND_URL=http://localhost:8003` in `WayFindMCPClient/.env`.
> 3. Zero changes needed to LangGraph core logic or UI.

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
| `LLM_PROVIDER` | `WayFindMCPClient/.env` | `groq` | `groq` \| `gemini` \| `openai` |
| `GROQ_API_KEY` | `WayFindMCPClient/.env` | None (required) | Live Groq API key (`gsk_...`) — **active provider** |
| `GEMINI_API_KEY` | `WayFindMCPClient/.env` | None (optional alt) | Google AI API key |
| `DATABASE_URL` | `ShelterAppUiBackend/.env` | Mock memory in `PostgresClient` | `postgresql+asyncpg://user:pass@host:5432/wayfind` |
| `REDIS_URL` | Backend & Agent `.env` | In-memory session fallback | `redis://localhost:6379/0` |
| `S3_BUCKET` / `R2_BUCKET` | `ShelterAppUiBackend/.env` | Local temporary directory | S3 / Cloudflare R2 bucket credentials |
| `TWILIO_ACCOUNT_SID` & `TOKEN` | `ShelterAppUiBackend/.env` | Mock logger | Live Twilio credentials for SMS/Voice |
| `QDRANT_URL` & `API_KEY` | `WayFindMCPClient/.env` | Static YAML fallback | Live Qdrant cluster |
