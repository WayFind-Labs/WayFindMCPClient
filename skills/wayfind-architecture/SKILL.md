---
name: wayfind-architecture
description: >
  Master architecture, temporal window search, progressive notifications,
  communication gateway, empathetic crisis AI, and cascaded vision pipeline
  for the Wayfind platform.
---

# Wayfind — Master Architecture Reference

## Single-container prototype package

`render-single.yaml` selects `Dockerfile.single` for one free Render web
service. Pinned Git submodules bring in the frontend and gateway at known
commits. A supervisor starts MCP, agent, gateway, and Next.js in that order;
only Next.js binds to the public port. The other services use loopback URLs.
External Neon and Layerbase continue to hold report and session data. This
temporary arrangement keeps the existing four-service Blueprint separate.

## Temporary Render deployment

`render.yaml` deploys the public Next.js web app plus private gateway, agent,
and MCP Docker services across the three GitHub repositories. Render injects
private `hostport` values; startup commands assemble internal HTTP URLs. Neon
is the durable PostgreSQL store and Layerbase is the shared Redis service.
Only the web app has a public Render URL; it proxies `/api/*` to the gateway.

## Implemented runtime knowledge wiring — 17 November 2026

User reference: `docs/reference/found_child_user_guidance.txt` (unchanged).
Runtime adaptation: `mcp_client/knowledge/found_child_guidance.md`.
`mcp_client/conversation_context.py` loads it as a packaged UTF-8 resource,
caches it until process restart, and assembles bounded user/assistant history
without accepting history-provided system/tool roles. The LLM wrapper uses it
for follow-ups, contextual guidance and final model-response fallbacks.
`safety_guidance` and `get_guidance_node` now use the contextual model method,
with explicit static safety help when unavailable, instead of the MCP guidance
path. MCP guidance tools remain available separately for existing callers.

Recording/transcription and biometric prompts remain outside the MVP. This
change does not change extraction/classification, graph routing/submission,
durable persistence, notification delivery or the frontend. Those audit gaps
remain open. The larger architecture below includes roadmap capabilities and
must not be treated as proof they are already deployed.

## 1. Core Operating Foundations & Entry Scenarios

1. **Single Landing Page with 3 Scenario Cards:**
   - **Scenario 1: Register Child on Wayfind (`REGISTERED_SAFE`):** Child pre-registration flow collecting baseline physical/biometric data. Excluded from general missing scans until SOS is triggered.
   - **Scenario 2: Looking for Lost Child (`MISSING_CHILD` / `MISSING_REGISTRATION`):** If registered children exist, shows them by name + option to add new (e.g. searching for someone else's child); else goes straight to progressive intake/search. Triggers temporal window matching from $T_{\text{lost}} \to \text{Now}$ and crisis companion de-escalation.
   - **Scenario 3: Found a Lost Child (`FOUND_CHILD` / `FOUND_INTAKE`):** Immediate safety guidance (safe public area, shelter/police contact, child helpline) + progressive found-child report intake.
2. **Pre-Seeded Conversational Intake (Light Progressive UX):**
   - The conversational AI flow starts immediately upon scenario card selection with pre-seeded intent.
   - Avoids dumping massive forms at once; gathers fields progressively with explicit "Unknown" toggles serializing to `null`.
3. **Deterministic-First Core:** Mathematical multi-attribute scoring and database queries execute deterministically with zero LLM dependency.
4. **Temporal Window Matching:** Bounds search space from $[T_{\text{lost}} - \Delta t] \to [\text{Now}]$, handling both recent emergencies and long-tail cold cases without database-wide scans.
5. **Empathetic Crisis AI Companion (MCP Client):** Conversational AI layer providing trauma-informed de-escalation, physical search protocols, and safe custodian guidance.
6. **Two-Phase Progressive Alerts & Masked Communication Gateway:**
   - *Phase 1:* Immediate acknowledgment of candidate verification.
7. **Decoupled Cascaded Vision AI (Separate Service — To Be Added Later):**
   - Biometric face matching runs only on top 3–5 candidate records filtered by the deterministic engine.
   - **Significance Gating:** Triggered ONLY when metadata `significance_score >= 0.60`.
   - **Standalone Microservice Contract:** (1) `POST /api/biometrics/embed` and (2) `POST /api/biometrics/match`. Decoupled via `ImageBackendClient`.
   - **Deterministic Scoring:** Composite evidence evaluation is pure mathematical scoring with zero LLM dependency.

---

## 2. System Architecture & Component Mapping

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                       Next.js PWA Client (ShelterApp ui)                │
│                                                                         │
│   [Single Landing Page (3 Scenario Cards)] ──► [Pre-Seeded Crisis Bot]  │
│   [Guardian Registered Profiles & SOS]     ──► [Progressive Mini-Forms] │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     │ REST / WebSockets
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   Core Backend (ShelterAppUiBackend)                    │
│                                                                         │
│   • Guardian Registry & Safe-State Isolation                            │
│   • Temporal Window Engine (Time Bounding & Buffer)                     │
│   • Dynamic Composable Query Builder (Null-Pruned SQL)                  │
│   • Normalized Multi-Attribute Scoring Engine                           │
│   • Masked Communication Gateway (Twilio Voice/SMS Bridge)              │
│   • Two-Phase Notification Dispatcher (SMS/Push/Email)                  │
│   • Staff Review Queue & HITL Approvals                                 │
└──────────────────┬─────────────────────────────────┬────────────────────┘
                   │                                 │
                   ▼                                 ▼
    ┌─────────────────────────────┐   ┌───────────────────────────────────┐
    │   PostgreSQL 16 + PostGIS   │   │  Encrypted Blob Storage (S3)      │
    │   • Guardians & Children    │   │  • Baseline Child Photos          │
    │   • Active SOS Beacons      │   │  • Found Child Intake Photos      │
    │   • Found Child Cases       │   └───────────────────────────────────┘
    └─────────────────────────────┘
                   │
                   ▼ (Top 3-5 Shortlisted Candidates Only; If Significance >= 0.60)
┌─────────────────────────────────────────────────────────────────────────┐
│        Standalone Biometric Vision Microservice (Port 8003 — Later)     │
│   • POST /api/biometrics/embed (Image -> 512-D ArcFace Vector)          │
│   • POST /api/biometrics/match (Cosine Similarity vs Candidate Vectors) │
└─────────────────────────────────────────────────────────────────────────┘
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Temporal Window Matching Mathematics

When an SOS or search is triggered with a reported last-seen time $T_{\text{lost}}$:

$$\text{Search Time Range } = [T_{\text{lost}} - \Delta t_{\text{buffer}}, \quad T_{\text{current}} + \Delta t_{\text{buffer}}]$$

* Default $\Delta t_{\text{buffer}} = 2\text{ hours}$ for reports from today; dynamically expands for multi-day searches.
* Prevents searching through irrelevant historical archives or safe registered profiles.

---

## 4. Progressive Notification & Communication Flow

```text
[Found Child Reported] ──► [Match Found (S >= 0.80)]
                                  │
                                  ├──► (1) Phase 1 SMS to Guardian:
                                  │    "Potential match detected. Verifying now."
                                  │
                                  ▼
                    [Staff Verification in /admin/review]
                                  │
                   ┌──────────────┴──────────────┐
                   ▼                             ▼
       [Child at Shelter]              [Child with Citizen Finder]
               │                                     │
   Phase 2 SMS: Shelter Address,       Phase 2 SMS: Masked Call Link
   Desk Contact, Case Passkey          + Finder Guided to Safe Location
```
# Found-child write path

Agent node → MCP tool → PostgresClient → gateway internal report endpoint →
PostgreSQL. `POSTGRES_SERVICE_URL` and a shared internal API key are required.
The submit node derives a stable per-draft submission ID for retried writes.
Opaque draft IDs bind confirmation and cancellation; stale confirmations are
rejected and explicit new reports clear the prior draft/reference state.
The internal snapshot route derives a minimal review or receipt event from
Redis state so the gateway can restore a browser view after refresh.
The found-report success response reflects irregular sole-admin review and
does not imply active monitoring or automatic authority notification.
The found draft stores field status separately from report values. Form choices
and the model's structured latest-turn extraction set explicit unknown or
declined states; known corrections replace those states.
The versioned runtime prompt currently targets English-only user-facing turns;
Urdu and Roman Urdu are deferred roadmap languages.
The completeness branch offers age, clothing, immediate condition and visible
features progressively after a coarse location, using an asked-once list.
Explicitly unavailable location routes to safety and direct-authority help
without submission.
Layerbase managed Redis over TLS is the local MVP shared state provider;
agent state uses `wayfind:agent-state:` to avoid gateway hash collisions.
The graph pauses on `request_confirmation` until a form response with
`confirm_found_report=true` arrives.
The LLM wrapper uses heuristics only when no API key is configured; configured
provider errors propagate to the agent.
Runtime guidance is packaged and location neutral for found-child intake.
The gateway receipt timestamp is passed through the agent event to the UI.
Age/height bounds and the receipt version match the gateway intake contract.
The submit node first emits a summary of known details for explicit review.
The committed-report message states only the Wayfind record and asks the
finder to contact local authorities; generic tool failures claim no staff alert.
The agent's public status branch explains the deferred lookup; internal status
adapters fail closed on missing or failed downstream responses.
With `ENABLE_DEFERRED_FEATURES=false`, the agent routes typed missing-child,
registration and shelter-search requests to an unavailable-feature response
before extraction or synthetic candidate search. Roadmap graph branches remain
behind the flag for later activation.
The internal agent exposes `/health` for liveness and authenticated `/ready`
for nondefault credentials, initialized model, Redis ping and MCP SSE endpoint.
The gateway uses `/ready` with the shared internal key.
The LLM's structured found-child extraction merges corrections into a
validated `FoundChildReport`, including age ranges.
The same extractor accepts a finder-supplied full name and phone from natural
chat or form data. Completeness asks optional child observations once, then
requires finder name and phone. The submit node enforces that gate even if a
confirmed draft reaches it directly. Found intake emits chat questions without
`request_information` cards. Runtime policy v5 and structured Groq guidance
keep user-facing replies short and action-first; invalid guidance falls back
to static safety help.
The follow-up schema has an optional short acknowledgment ahead of one question.
Formatting mismatch uses a field-specific question; genuine provider failure
continues through the recoverable error path. Acknowledgments may repeat
finder-supplied numeric facts such as age.
The agent snapshot route maps an unfinished found intake to `assistant_message`
and preserves review/receipt events for completed stages.
Found-child follow-up events and snapshots include `optional_field` for Skip
and `draft_id` for clearing an open draft. Clear resets only the draft; the
existing new-report action replaces the visible receipt while retaining the
durable saved report. Finder contact wording refers to a possible verified
parent or guardian handover without exposing the private phone.
Clear and new-report resets preserve found-child intent and a small assistant
context turn; the next location-only reply advances the same intake workflow.
The intent guard also accepts a pre-fix open draft ID to recover existing
sessions from the generic unknown-intent response.
The recovery question is derived from `missing_information` so Redis snapshots
do not depend on conversational history being present.
Fresh text turns are reclassified so guidance questions can interrupt intake;
form answers retain the active draft intent. Groq structured extraction uses
JSON Schema mode rather than function calling.
An open found-child draft retains found-child intent when a classifier mistakes
a short detail answer for a deferred journey; guidance can still interrupt.
The Karachi-scoped role prompt directs the finder to call before finishing the
Wayfind report. The UI owns verified dial links; the agent never initiates calls.
The MCP get_guidance tool falls through to reviewed static YAML when RAG has
only a fallback answer, preserving Karachi numbers and truthful report claims.
The first found-child turn emits reviewed immediate-danger guidance before a
missing-location question; `found_safety_delivered` persists across turns so
the initial safety message is not repeated.
The initial safety event is four short paragraphs that the chat renders with
visible spacing.
