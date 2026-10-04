---
name: wayfind-architecture
description: >
  Master architecture, temporal window search, progressive notifications,
  communication gateway, empathetic crisis AI, and cascaded vision pipeline
  for the Wayfind platform.
---

# Wayfind — Master Architecture Reference

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
   - *Phase 2:* Dispatches verified shelter directions or opens masked VoIP/SMS proxy bridge between finder and guardian.
7. **Cascaded Vision AI:** Biometric face matching runs only on top 3–5 candidate records filtered by the deterministic engine.

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
                   ▼ (Top 3-5 Shortlisted Candidates Only)
┌─────────────────────────────────────────────────────────────────────────┐
│              Biometric Vision AI Service (WayFindMCPClient)             │
│   • InsightFace 512-D Biometric Embedding Comparison                    │
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
