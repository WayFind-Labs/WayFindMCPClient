---
name: wayfind-architecture
description: >
  Master architecture, temporal window search, progressive notifications,
  communication gateway, empathetic crisis AI, and cascaded vision pipeline
  for the Wayfind platform.
---

# Wayfind — Master Architecture Reference

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
The submit node derives a stable per-session submission ID for retried writes.
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
The LLM's structured found-child extraction merges corrections into a
validated `FoundChildReport`, including age ranges.
Fresh text turns are reclassified so guidance questions can interrupt intake;
form answers retain the active draft intent. Groq structured extraction uses
JSON Schema mode rather than function calling.
