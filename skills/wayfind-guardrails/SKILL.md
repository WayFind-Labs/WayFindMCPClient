---
name: wayfind-guardrails
description: >
  Safety guardrails, privacy policies, communication gateway constraints, and
  crisis response guardrails for the Wayfind platform.
---

# Wayfind — Safety, Privacy & Operational Guardrails

## Current MVP runtime policy — 17 November 2026

`mcp_client/knowledge/found_child_guidance.md` is the runtime conversation policy,
adapted from the preserved user reference in `docs/reference/`. It is explicitly
loaded into model calls; developer skill files are not automatically runtime
context. This current MVP policy takes precedence over aspirational wording below.

- Recording/transcription, biometric capture, automatic authority notification
  and verified reunification are not enabled by the reference document.
- Never assert that parents/authorities were alerted, staff are reviewing, data
  is encrypted or a report is durably committed without verified evidence.
- Committed-report copy states only the Wayfind record and direct-authority
  action; generic tool failures do not claim staff notification.
- Public case-status lookup is deferred; internal status adapters fail closed
  rather than inventing a review state or timestamps.
- The agent blocks missing-child search, registration and shelter-search graph
  paths by default before extraction or candidate search; re-enable only after
  their separate public-use gates are verified.
- The internal agent's authenticated `/ready` reports missing provider/model,
  Redis and MCP dependencies as not ready. `/health` is liveness only.
- Use sourced regional contacts; do not present 1098 as a universal Pakistan
  child helpline or 1099 as emergency medical dispatch.
- Stay visible and seek official help; do not advise private transport or handing
  a child to an unverified claimant. Avoid unsupported guarantees such as “you
  are safe,” coercive questioning, recording prompts and hidden-body inspection.
- Guidance-node model failure uses explicit unavailable safety help; no new
  regex/keyword conversation fallback is introduced by this integration.
- Fresh text turns are reclassified so a safety question can interrupt intake;
  Groq structured extraction uses JSON Schema mode. Form responses stay with
  the active draft. No-key development still contains legacy heuristics.
- The first found-child assistant turn states immediate-danger actions before
  requesting location; a session flag prevents repeating this initial notice.
- Wider audit fixes remain pending, including legacy heuristic routing, static
  success messages and report persistence. Prompt instructions alone do not
  enforce database/authentication/notification guarantees.

## 1. Core Operating Principle
The core system must be deterministic, transparent, and safe by design. Child safety data and direct guardian-finder interactions must be strictly controlled and protected.

---

## 2. Guardrail Group 1: Child Privacy & Masked Communication

1. **No Direct Phone Number Leaks:** When connecting a citizen finder with a guardian, raw phone numbers **must never** be displayed. All calls/SMS must pass through a masked proxy bridge (Twilio Voice/SMS Proxy).
2. **Finder Safety Instructions:** The finder must be explicitly instructed: *"The parents have been alerted and are connecting now. Please remain in a well-lit, public location or near an authorized shelter."*
3. **No Public Search Catalog:** Public search endpoints return only status confirmation; never full names, guardian numbers, or residential addresses.
4. **Encryption at Rest:** Sensitive medical notes, guardian ID proofs, and contact details are encrypted at rest using AES-256 (GCM).

---

## 3. Guardrail Group 2: Temporal & Safe-State Isolation

1. **Safe-State Exclusion:** Pre-registered children in `REGISTERED_SAFE` status **must never** be scanned or exposed in general missing-child queries.
2. **Temporal Window Enforced:** Missing/found queries must enforce a bounded time window ($[T_{\text{lost}} - \text{buffer}] \to [\text{Now}]$) to prevent accidental historical false matches.

---

## 4. Guardrail Group 3: Empathetic Crisis AI Safety & Role Guidance

1. **No Medical or Legal Guarantees:** The Crisis Companion LLM must never promise or guarantee that the child is safe or already found until verified by staff.
2. **Immediate Physical Safety First for Parents:** The Crisis Companion must prioritize immediate physical steps (checking nearby hazards/pools, exits, notifying security/police) while the matching engine executes in the background.
3. **Finder Safe Custody Instructions:** Finders must be guided immediately to:
   - Stay in a well-lit, public location.
   - Contact or escort the child to the nearest verified shelter home or police station.
   - Dial the national child helpline (e.g., 1098 / emergency services).
   - Never interrogate or separate a child unassisted.
4. **Trauma-Informed Wording:** Response tone must be steady, calming, and concise—avoiding alarming language or technical jargon.
5. **Historical / Cold-Case Awareness:** For children lost long ago (e.g., 10 years), acknowledge the emotional weight, handle age progression gracefully, and enforce search window starting from original $T_{\text{lost}}$.

---

## 5. Guardrail Group 4: Human-in-the-Loop (HITL) Verification

1. **Staff Approval Gate:** Matches in the `UNCERTAIN` ($0.50 \le S < 0.80$) and `HIGH` ($S \ge 0.80$) tiers require staff verification before releasing shelter desk directions or activating the masked communication bridge.
2. **Tamper-Evident Audit Logs:** Every match calculation, profile lookup, and staff decision is logged with immutable timestamps and user IDs.

---

## 6. Guardrail Group 5: Development, Git Push & Context Synchronization

1. **Mandatory Git Push Discipline:**
   - After completing meaningful writing, coding, LangGraph node work, prompt refinement, or bug fixes, immediately stage, commit, and `git push` to `origin`.
   - Commit messages must follow Conventional Commits formatting (`feat:`, `fix:`, `refactor:`, `docs:`, etc.) with clear descriptions of what was implemented.
2. **Mandatory Context Synchronization:**
   - Whenever work modifies, expands, or introduces changes to state schemas, intent nodes, tools, prompts, or workflows, immediately update project context files ([`skills/wayfind-guardrails/SKILL.md`](file:///e:/React/Shelter/WayFindMCPClient/skills/wayfind-guardrails/SKILL.md), [`skills/wayfind-architecture/SKILL.md`](file:///e:/React/Shelter/WayFindMCPClient/skills/wayfind-architecture/SKILL.md), [`skills/implementationfile.md`](file:///e:/React/Shelter/WayFindMCPClient/skills/implementationfile.md), and [`README.md`](file:///e:/React/Shelter/WayFindMCPClient/README.md)) to maintain complete context accuracy.
# Submission receipt rule

Found-child submission may emit `submission_complete` only after the gateway
returns a validated backend receipt. Tool outages and missing configuration
must remain errors, never local reference fallbacks.
Retries within one session use the same submission ID. A distinct new report
requires a distinct draft ID before recording.
The current draft ID is carried in review/confirmation events. Stale
confirmation is rejected, and cancellation clears an unrecorded draft.
The internal session snapshot exposes only a found-child review or committed
receipt behind the shared service key; raw state and dialogue stay internal.
Success wording must state irregular sole-admin review with no guaranteed
monitoring or response time, and must direct the finder to local authorities.
Keep `known`, `unknown`, `declined` and unasked field states distinct in the
active found draft. A correction may replace an unavailable value; never infer
unknown or declined merely from silence.
Offer useful optional found-child observations one at a time and at most once.
The runtime policy speaks clear English in the MVP. Urdu and Roman Urdu
conversation support requires later implementation and evaluation.
An explicitly unavailable location needs an assistance outcome and no saved
report; do not repeatedly ask for a place the finder cannot provide.
Layerbase managed Redis over TLS is the shared local MVP state provider;
agent and gateway key namespaces are distinct.
The found-report node requires an explicit confirmation event before a write.
Configured model failures must not fall back to keyword extraction.
The prototype is scoped to Karachi, Sindh. Give Karachi call options before
intake and direct a finder outside Karachi to their own local emergency help.
If RAG returns fallback content, use the reviewed Karachi static guidance YAML
for found-child tool guidance instead of generic missing-child or 1098 advice.
Carry the backend receipt timestamp into `submission_complete`.
Use the `FoundChildIntakeV1` schema version in the report and receipt event.
Show known report details in the confirmation summary before any write.
Structured corrections replace prior report facts and are validated.
Found-child reports require the finder's full name and a reachable phone
number before confirmation or submission. Extract contact only when the finder
supplies their own details; keep it out of the receipt and public responses.
Ask one short chat question per intake turn. The `found-child-intake-v5`
runtime policy gives action-first, plain-English guidance with no long list or
unverified emergency number. Groq follow-ups and guidance use structured
output contracts; invalid output fails to reviewed static safety text.
A follow-up may briefly acknowledge the finder, but cannot assert unobserved
safety or authority action.
Allow grounded numbers such as a stated age in acknowledgments. If the model
misses the short follow-up format, ask about the current field in one brief
question; disclose a real provider failure instead of presenting it as a
successful model answer.
While a found-child draft is open, a model misclassification cannot route an
answer about the child into a deferred missing-child journey. Safety questions
may interrupt intake. The runtime role is to help the finder stay safe, call
for help promptly, and review and record a report without implying dispatch.
Session snapshot recovery must return a chat question for unfinished found
intake; it must not reintroduce a mandatory form card.
Optional intake questions and restored snapshots expose the current optional
field and draft ID so the frontend can offer Skip and Clear draft. Skip records
an explicit unknown status; Clear draft cannot delete a recorded report.
Reset actions retain the found-child scenario so a location-only answer after
starting over cannot fall into a generic unknown-intent question.
Recognize an existing draft ID from older sessions as found-child intake too.
Ask for finder contact in terms of a possible handover to a verified parent or
guardian, without implying automatic matching or direct access to the phone.
Derive a field-specific recovery question from the current missing field if
the prior assistant wording is unavailable.
