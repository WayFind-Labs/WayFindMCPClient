# WayFindMCPClient

## Temporary Render deployment

[`render.yaml`](render.yaml) creates four Docker services from the three Wayfind
repositories. The Next.js web service is public. The gateway, agent, and MCP
server are private services on Render's network. The web app forwards `/api/*`
to the gateway, so the browser uses one origin. The gateway applies the
idempotent found-report migration at startup. Neon PostgreSQL and Layerbase
Redis remain external managed services.

Create a Render Blueprint from this repository's `feat/groq-llm-provider`
branch. Connect all three GitHub repositories to the same Render workspace.
Render prompts for `DATABASE_URL` (Neon), `REDIS_URL` (Layerbase `rediss://`),
and `GROQ_API_KEY`. Enter these as Render secrets, never in Git. The Blueprint
generates the gateway JWT secret, private admin API key, and shared gateway/
agent key. Render private services use paid compute; review the four service
charges before creating the Blueprint. The frontend branch is
`feat/found-child-pitch-flow`; the gateway branch is `main`.

After all services are live, open the web service URL and run a synthetic
found-child conversation. If intake returns 503, inspect gateway, agent, and
MCP logs and the external Neon/Layerbase/Groq connections. This is the
English-only Karachi prototype, without guaranteed emergency monitoring.

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
The key also includes the draft ID, so an explicitly new report can have its
own receipt. Confirmation and cancellation carry the opaque draft ID from the
review event; stale confirmations are rejected, and cancellation clears only
an unrecorded draft.
The authenticated internal snapshot endpoint returns only the current
found-child review event or committed receipt for gateway-mediated refresh;
it never exposes raw agent state or the conversation log.
The recorded-report message states that sole-admin review is irregular with no
guaranteed monitoring or response time; users are directed to local authorities
for immediate action rather than promised an automatic alert.
The found-child draft now carries per-field `known`, `unknown`, `declined` or
unasked state. Explicit form choices and typed model extraction update those
statuses; later corrections replace earlier unknown/declined values.
The versioned runtime conversation policy is English-only for the MVP. Urdu
and Roman Urdu conversational support are future work; no translation service
or multilingual quality claim is active.
After a coarse found location is known, the graph offers age, clothing,
immediate condition and visible features one question at a time, each only
once. They are optional; an unknown or declined value does not block a partial
report. If the location itself is explicitly unavailable, the graph gives
assistance and direct-authority guidance without claiming a report was saved.
The graph emits `request_confirmation` with a review summary before recording.
The committed-report message does not claim staff review, matching or authority
notification; tool-failure copy does not claim staff were notified.
Public case-status lookup is deferred. The agent explains that limitation;
internal status adapters reject missing or failed downstream results instead
of inventing an active review state.
`ENABLE_DEFERRED_FEATURES=false` closes typed missing-child search, child
registration and shelter-search turns before extraction or search. The graph
retains those branches for later work, but both agent and gateway gates must
be enabled before any roadmap feature can be activated.
`/health` is process liveness. Authenticated `/ready` returns 503 unless the
nondefault internal key, provider key/model, gateway URL, Redis session store
and MCP SSE endpoint are configured and the initialized model, Redis ping and
MCP endpoint respond. The gateway calls this route with `X-Internal-Key`.
Only the explicit `confirm_found_report` form action enables the write; a text
correction or failed submission resets confirmation.
When an LLM API key is configured, intent and structured extraction failures
surface as errors. Keyword heuristics remain only in no-key development mode.
Fresh text turns are reclassified, allowing guidance questions to interrupt an
active intake; structured form answers remain attached to their active draft.
For the first found-child turn, reviewed immediate-danger guidance precedes
the intake question even when the location is missing. A session flag prevents
repeating that initial safety message; model guidance failures retain static
safety help.
Groq extraction uses JSON Schema output for the configured GPT OSS model rather
than function calling. The interruption and extraction paths have a synthetic
live Groq rehearsal.
The packaged found-child guidance is location neutral. It records the
finder's reported location without requiring a Pakistan province or running
candidate matching; regional contacts are used only where verified.
`submission_complete` carries the committed backend timestamp and Wayfind
reference for the dedicated receipt UI.
The `FoundChildIntakeV1` report and receipt event share an explicit schema
version; age and height bounds match the gateway contract.
The pre-submit review includes known age, appearance, location, time,
circumstances, authority-contact status and the finder's required full name and phone.
Structured extraction applies new facts as corrections to prior report fields
and validates the merged canonical report; approximate ages retain bounds.
`tests/test_live_groq.py` is an opt-in synthetic rehearsal for configured
Groq intent, structured fields and photo-sharing safety guidance.
The finder now gives a full name and phone number before report review or
submission; the agent extracts these from ordinary chat and the submit node
checks them again. Found-child follow-ups use one chat question at a time,
without an inline form card. Reporter contact appears in the private review
summary, never in the receipt. A versioned runtime guidance asset controls
short, action-first English responses; structured Groq follow-ups and guidance
are checked for length, formatting and unverified emergency number examples.
The follow-up model may add one brief, grounded acknowledgment before its
single question to keep the exchange calm without adding a second request.
If a Groq follow-up breaks that short response format, the agent asks a brief
question for the current field. A provider failure remains visible as an error.
Grounded numbers, such as a child's stated age, are allowed in acknowledgments.
The Karachi prototype uses runtime policy `found-child-intake-v5` in
`mcp_client/knowledge/found_child_guidance.md`. It tells the agent to help the
finder stay safe, call police or rescue before finishing intake, and calmly
review and record a found-child report. The classifier is separately prompted
with intent definitions and follow-up context; active found drafts keep that
intent for short detail answers while safety questions can interrupt. The
frontend provides verified Karachi dial links; Wayfind never places the call.
The reviewed first-turn safety message uses four short paragraphs with blank
lines: urgent action, public place, privacy boundary, and Wayfind's call limit.
When the optional RAG client returns its own static fallback, the MCP guidance
tool uses the reviewed Karachi YAML instead of older generic fallback copy.
The authenticated snapshot restores an unfinished found-child intake as a
chat question, not a form card; review and committed receipt snapshots retain
their existing event types.
Optional found-child questions carry `optional_field` and the draft ID in the
agent event. The UI uses that field to show a Skip button, which sends an
explicit unknown status. A finder can clear an open draft; a recorded receipt
can be dismissed to start another report without deleting the saved record.
Both Clear draft and Start another report leave the session in the found-child
scenario, so a location-only reply receives the next specific intake question.
The intent guard also recognizes a draft created before this correction, so
the finder can retry the location in the same session.
Finder contact questions mention a possible handover to a verified parent or
guardian and do not suggest direct contact with an unverified claimant.
When dialogue history is unavailable, recovery derives the question from the
current missing field instead of showing a generic placeholder.
The MVP shared Redis provider is Layerbase managed Redis over TLS (`rediss://`),
configured only in ignored local environment files. Agent conversation state
uses `wayfind:agent-state:` keys, separate from gateway session hashes under
`wayfind:session:`. A synthetic shared Redis contract test lives in the gateway
test suite.
