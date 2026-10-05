# Guardrails & Workflow Standards for WayFind MCP Client

## 1. Git Commit & Push Guardrail (Mandatory)
- **Automatic Push After Meaningful Work:** After completing any meaningful writing, coding, LangGraph node creation, prompt engineering, tool integration, or bug fix, you must stage, commit, and run `git push` to the remote repository (`origin`).
- **Descriptive & Understandable Commit Messages:** Commit messages must strictly follow Conventional Commits (e.g., `feat:`, `fix:`, `refactor:`, `docs:`, `test:`, `chore:`) with clear, understandable descriptions explaining *what* was changed and *why*.
  - Example: `feat(agent): add child registration node with schema validation`
  - Example: `fix(prompt): refine crisis companion de-escalation tone and safety checks`

## 2. Project Context Synchronization Guardrail (Mandatory)
- **Keep Project Context in Sync:** If the work requested or performed alters, introduces, or extends the agent state machine, MCP tools, schemas, intent classification, prompt structures, or guardrails, you **must immediately update** the project context documentation (`skills/wayfind-guardrails/SKILL.md`, `skills/wayfind-architecture/SKILL.md`, `skills/implementationfile.md`, `README.md`).
- Never leave project context files outdated or inconsistent with the active code implementation.
