# WayFindMCPClient

> Agent backend for the **Wayfind** platform — a prompt-first PWA for missing children, found children, and shelter access.

## Runtime conversation knowledge (17 November 2026)

The user-supplied found-child guidance is preserved unchanged in
[`docs/reference/found_child_user_guidance.txt`](docs/reference/found_child_user_guidance.txt).
The MVP adaptation in
[`mcp_client/knowledge/found_child_guidance.md`](mcp_client/knowledge/found_child_guidance.md)
is actual runtime context, loaded by `mcp_client/conversation_context.py` and sent
as a system message to Groq for follow-ups, safety/general guidance, and final
LLM responses. Recent user/assistant dialogue accompanies it. Guidance nodes now
call this grounded model path; a missing model returns explicitly unavailable
safety help. Restart the agent after editing the cached knowledge file.

The original includes future feature proposals and unverified legal assertions;
it is preserved for provenance and is not injected verbatim. The runtime version
keeps practical safety/communication/reporting/handover guidance, regional contact
sources, and truthful capability limits. Recording/transcription and biometric
capture remain post-MVP. It does not claim notifications, dispatch, encryption,
or a durable save merely because those are proposed in the source.

This is a targeted knowledge-injection change, not completion of the wider MVP
audit: intent/extraction heuristics, auto-submission behavior, static submission
messages, persistence and frontend issues still need their tracked fixes.
The extraction/classification model prompts are not changed by this knowledge
asset. Existing event responses may still bypass the final LLM fallback.

Verification: `python -m pytest tests/test_conversation_context.py -q` checks
actual outgoing prompt context, dialogue role boundaries, guidance-node wiring
and model-failure behavior using synthetic data and mocked model responses.

---

## Architecture

```
Wayfind PWA
POST /api/agent { "prompt" }
        ↓
FastAPI  (app/)
        ↓
LangGraph graph  (agent/)
        ↓
MCP Client + LLM  (mcp_client/)
        ↓
FastMCP Server  (mcp_server/)
        ↓
[PostgreSQL] [RAG] [Image/Vector] [Support/Location]
```

The frontend sends a single natural-language message. The backend:

1. **Understands intent** — `missing_child`, `found_child`, `shelter_search`, `guidance`, `case_status`
2. **Extracts structured data** — fills `ChildSearchCriteria` or `FoundChildReport` incrementally across turns
3. **Checks completeness** — asks one compound follow-up question per turn if required fields are missing
4. **Routes** — invokes the appropriate MCP tool pipeline
5. **Evaluates evidence** — scores candidates by metadata + image similarity + geography + time
6. **Submits for human review** — UNCERTAIN and HIGH confidence matches go to a staff queue
7. **Returns a safe natural-language response** — never leaks PII, internal IDs, or match scores

---

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| Agent | LangGraph |
| LLM | Groq (`openai/gpt-oss-120b` by default, via `langchain-groq`); model remains configurable |
| MCP Server | FastMCP |
| Session | Redis |
| Async HTTP | httpx |
| Config | Pydantic v2 + pydantic-settings |
| Package manager | uv |

---

## Project Structure

```
WayFindMCPClient/
├── app/                  # FastAPI entry point
│   ├── main.py           # App factory + CORS + exception handlers
│   ├── config.py         # Pydantic Settings (loads .env)
│   ├── session.py        # Session store (memory / Redis)
│   └── routes/
│       └── agent.py      # POST /api/agent
├── agent/                # LangGraph graph
│   ├── state.py          # WayfindState TypedDict
│   ├── graph.py          # Graph definition + conditional edges
│   ├── runner.py         # Compile + invoke graph
│   └── nodes/            # 19 pure-function nodes
├── mcp_client/           # MCP client + LLM wrapper
│   ├── client.py         # FastMCP client session
│   └── llm.py            # Structured LLM calls (Gemini)
├── mcp_server/           # FastMCP server
│   ├── server.py         # Tool registration
│   └── tools/            # 6 domain tools
├── schemas/              # Shared Pydantic models
├── services/             # Async HTTP clients (stubs → real)
├── config/               # evidence_weights.yaml, static_guidance.yaml
└── tests/                # pytest test suite
```

---

## Quick Start

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) installed globally
- Redis running locally (or update `SESSION_BACKEND=memory` for dev)

### Setup

```bash
# 1. Clone / enter the repo
cd WayFindMCPClient

# 2. Install dependencies
uv sync --all-extras

# 3. Configure environment
cp .env.example .env
# Edit .env — at minimum set GEMINI_API_KEY and SECRET_KEY

# 4. Start the FastAPI server
uv run uvicorn app.main:app --reload --port 8000

# 5. Start the FastMCP server (separate terminal)
uv run python -m mcp_server.server
```

### Running Tests

```bash
uv run pytest --cov=. --cov-report=term-missing
```

---

## Environment Variables

See [.env.example](.env.example) for a full reference with comments.

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `LLM_PROVIDER` | `groq` | No | `groq`, `gemini`, or `openai` |
| `GROQ_API_KEY` | — | Yes (if groq) | Groq API key — **default provider** |
| `GEMINI_API_KEY` | — | Yes (if gemini) | Google AI API key |
| `POSTGRES_SERVICE_URL` | — | Yes | Downstream PostgreSQL service |
| `RAG_SERVICE_URL` | — | Yes | RAG knowledge-base service |
| `IMAGE_BACKEND_URL` | — | Yes | Image/vector similarity service |
| `SUPPORT_SERVICE_URL` | — | Yes | Shelter/support location service |
| `REVIEW_SERVICE_URL` | — | Yes | Human review queue service |
| `SESSION_BACKEND` | `redis` | No | `memory` or `redis` |
| `REDIS_URL` | — | If redis | Redis connection URL |
| `SECRET_KEY` | — | Yes | JWT session signing key |
| `CORS_ORIGINS` | `http://localhost:3000` | No | Allowed frontend origins |
| `MAX_CANDIDATE_POOL` | `50` | No | Metadata search cap |
| `MAX_IMAGE_CANDIDATES` | `20` | No | Max candidates for image match |
| `MCP_TRANSPORT` | `sse` | No | `sse` or `stdio` |
| `MCP_SERVER_URL` | — | If sse | URL of FastMCP SSE server |

---

## API

### `POST /api/agent`

**Request**
```json
{ "prompt": "My daughter is missing." }
```
Optionally include `X-Session-ID` header to continue an existing conversation.

**Response**
```json
{
  "message": "Could you tell me approximately how old she is and where she was last seen?",
  "metadata": {}
}
```
Response includes `X-Session-ID` header for the next turn.

---

## Security Notes

- All API routes are public (anonymous sessions via JWT session tokens)
- No PII is ever returned to the client — only safe subsets of records
- Images are safety-scanned before storage; only an internal `media_id` flows through the system
- `get_case_status` returns only public-safe fields — no staff notes, match scores, or candidate details
- Rate limiting applied per session and per IP

---

## Future Work (Post v1)

- Account creation via prompt (name, email, password) for case-update notifications
- Full Docker Compose deployment (all services together)
- Production image safety scan integration
- Real PostgreSQL / RAG / image backend integration
# Found-child submission dependency

Recording a found-child report requires `POSTGRES_SERVICE_URL` pointing to the
gateway and matching `SHELTER_BACKEND_API_KEY`. The tool and agent surface a
failure if a committed backend receipt is unavailable; they never generate a
local success reference.
The agent attaches a stable submission key derived from the session so retrying
the same report after a lost response reuses the database reference.
The graph emits `request_confirmation` with a review summary before recording.
Only the explicit `confirm_found_report` form action enables the write; a text
correction or failed submission resets confirmation.
When an LLM API key is configured, intent and structured extraction failures
surface as errors. Keyword heuristics remain only in no-key development mode.
The packaged found-child guidance is location neutral. It records the
finder's reported location without requiring a Pakistan province or running
candidate matching; regional contacts are used only where verified.
`submission_complete` carries the committed backend timestamp and Wayfind
reference for the dedicated receipt UI.
The `FoundChildIntakeV1` report and receipt event share an explicit schema
version; age and height bounds match the gateway contract.
The pre-submit review includes known age, appearance, location, time,
circumstances, authority-contact status and optional reporter details.
Structured extraction applies new facts as corrections to prior report fields
and validates the merged canonical report; approximate ages retain bounds.
