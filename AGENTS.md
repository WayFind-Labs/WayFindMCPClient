# Agent Instructions & Operating Guardrails

## Core Guardrails

### 1. Mandatory Git Commit & Push Discipline
- **After Meaningful Coding / Writing Work:** Always stage, commit, and `git push` all changes to the remote repository (`origin`).
- **Clear Commit Messages:** Write descriptive, understandable commit messages using Conventional Commits format (e.g., `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`). Never use vague messages like "update files" or "fix agent".

### 2. Mandatory Project Context Maintenance
- **Keep Context Synced:** Whenever new LangGraph nodes, state definitions, MCP tools, prompts, or workflows are created or modified, immediately update the project context files:
  - [`skills/wayfind-guardrails/SKILL.md`](file:///e:/React/Shelter/WayFindMCPClient/skills/wayfind-guardrails/SKILL.md)
  - [`skills/wayfind-architecture/SKILL.md`](file:///e:/React/Shelter/WayFindMCPClient/skills/wayfind-architecture/SKILL.md)
  - [`skills/implementationfile.md`](file:///e:/React/Shelter/WayFindMCPClient/skills/implementationfile.md)
  - [`README.md`](file:///e:/React/Shelter/WayFindMCPClient/README.md)
- Context documentation must remain an accurate reflection of the current codebase state.
