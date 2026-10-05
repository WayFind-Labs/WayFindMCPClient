---
name: wayfind-guardrails
description: >
  Safety guardrails, privacy policies, communication gateway constraints, and
  crisis response guardrails for the Wayfind platform.
---

# Wayfind — Safety, Privacy & Operational Guardrails

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
