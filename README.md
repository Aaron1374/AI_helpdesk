# AI L1 IT Helpdesk

An AI-powered internal IT support platform. Employees describe an issue in a chat portal; a LangGraph agent triages it, retrieves evidence from a vector Knowledge Base (RAG), runs mock diagnostic tools through an authorization gateway, and either resolves the issue with a grounded answer or escalates to a human L1 engineer with full context.

**Everything in this document is derived from the source code in this repository.**

---

## Table of Contents

1. [Architecture](#architecture)
2. [Technology Stack](#technology-stack)
3. [Quick Start](#quick-start)
4. [Configuration Reference (env vars)](#configuration-reference-env-vars)
5. [Default Accounts](#default-accounts)
6. [The AI Workflow (LangGraph)](#the-ai-workflow-langgraph)
7. [RAG Pipeline: Thresholds, Retry Values & Tuning](#rag-pipeline-thresholds-retry-values--tuning)
8. [Escalation Policy](#escalation-policy)
9. [Security Model](#security-model)
10. [API Reference](#api-reference)
11. [Ticket State Machine](#ticket-state-machine)
12. [Database Schema](#database-schema)
13. [Observability](#observability)
14. [Frontend](#frontend)
15. [Testing](#testing)
16. [Project Structure](#project-structure)
17. [Code-Accuracy Notes](#code-accuracy-notes)

---

## Architecture

Defined in `docker-compose.yml` — four services:

```
┌────────────────────────── Docker Compose ──────────────────────────┐
│                                                                    │
│  frontend (5173)          backend (8001→8000)       db (5432)      │
│  React 18 + TS + Vite ──► FastAPI + LangGraph ────► PostgreSQL     │
│  dev server, hot reload    uvicorn --reload         + pgvector     │
│  Vite proxy /api ─────────► (source mounted)       (pgdata vol.)   │
│                                                                    │
│  adminer (8080) ── web UI into the database                        │
└────────────────────────────────────────────────────────────────────┘
```

- `db`: image `ankane/pgvector:v0.5.1`, defaults `helpdesk_user` / `helpdesk_password` / `helpdesk_db`, data in the `pgdata` volume.
- `backend`: built from `./backend`, host port **8001** → container **8000**, runs `uvicorn src.main:app --reload` with `./backend` bind-mounted.
- `frontend`: built from `./frontend`, host port **5173**, runs `npm run dev -- --host 0.0.0.0`; `node_modules` is an isolated named volume. In-container API calls go through the Vite proxy (`/api` → `http://backend:8000`, prefix stripped).
- `adminer`: image `adminer`, host port **8080**.

---

## Technology Stack

| Layer | Technology | Where in code |
|---|---|---|
| Backend framework | FastAPI (async), Uvicorn | `backend/src/main.py` |
| ORM / DB | SQLAlchemy 2.0 async (`asyncpg`), Alembic migrations | `backend/src/core/db.py`, `backend/alembic/` |
| Vector search | pgvector (`Vector(3072)` columns, cosine distance) | `backend/src/models/knowledge.py`, `ticket.py`, `services/retrieval_service.py` |
| AI orchestration | LangGraph `StateGraph` | `backend/src/workflow/graph.py` |
| LLM access | LangChain (OpenAI / Google Gemini / xAI Grok / OpenAI-compatible) | `backend/src/core/llm.py` |
| Auth | JWT HS256 via `python-jose`, bcrypt via `passlib` (`bcrypt<4.0.0` pinned) | `backend/src/auth/security.py` |
| LLM tracing | Langfuse (optional, lazy-init callback handler) | `backend/src/core/observability.py` |
| Frontend | React 18 + TypeScript + Vite 5, `react-markdown` + `remark-gfm` | `frontend/src/` |
| E2E tests | Playwright | `frontend/e2e/workflow.spec.ts` |
| Load tests | Locust | `backend/tests/performance/locustfile.py` |
| Security scan | Bandit | `.github/workflows/ci.yml` |

---

## Quick Start

```bash
# 1. Create .env in the repo root (see Configuration Reference).
#    Minimum: DATABASE_URL is hardcoded in compose, but you need an LLM/embedding key:
#    LLM_PROVIDER, LLM_MODEL, OPENAI_API_KEY (or GOOGLE_API_KEY / XAI_API_KEY)

# 2. Start everything
docker compose up --build -d

# 3. Create the schema
docker compose exec backend alembic upgrade head

# 4. Seed the Knowledge Base (100 articles from kb_articles.json)
docker compose exec backend python seed_kb.py

# 5. Open the app
#    Frontend:  http://localhost:5173
#    API docs:  http://localhost:8001/docs   (Swagger)  and  /redoc
#    Adminer:   http://localhost:8080
```

`seed_kb.py` flags: `--dry-run` (preview chunks, no embedding/DB writes), `--reset` (delete all `knowledge_documents` first), `--file <path>` (default `kb_articles.json`).

---

## Configuration Reference (env vars)

All values below are read directly in code (`core/db.py`, `core/llm.py`, `core/observability.py`, `workflow/constants.py`, `auth/security.py`, `docker-compose.yml`).

### Core

| Variable | Default | Used by |
|---|---|---|
| `DATABASE_URL` | **required** — `RuntimeError` if missing | async engine (`postgresql+asyncpg://…`) |
| `SECRET_KEY` | `change-this-development-secret` | JWT signing (HS256) |

### LLM provider

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `openai` | Also accepts `google`/`gemini`, `xai`/`grok`, `openai_compatible`, `ollama`, `custom` |
| `LLM_MODEL` | `gpt-4o-mini` | e.g. `gemini-2.5-flash`, `grok-3-mini` |
| `LLM_TEMPERATURE` | `0` | Deterministic outputs (also `workflow/constants.py` default `0.0`) |
| `LLM_SEED` | `42` | Fixed sampling seed (passed where supported) |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_ORG_ID` | empty | OpenAI-compatible clients |
| `GOOGLE_API_KEY` | empty | Gemini chat + embeddings |
| `XAI_API_KEY` / `XAI_BASE_URL` | empty / `https://api.x.ai/v1` | Grok chat (embeddings fall back to OpenAI) |

`get_chat_model()` and `get_embedding_model()` return **`None`** when the provider's key is missing — every consumer degrades gracefully instead of crashing.

### Embeddings

| Variable | Default |
|---|---|
| `EMBEDDING_PROVIDER` | falls back to `LLM_PROVIDER`, else `openai` |
| `EMBEDDING_MODEL` | `text-embedding-3-small` (OpenAI path) / `gemini-embedding-2` (Gemini path) |

Embedding vectors are stored as **`vector(3072)`** in both `knowledge_documents` and `tickets` (migration `5a6381fc5d41` widened tickets from 1536 → 3072).

### Dev accounts

| Variable | Default |
|---|---|
| `DEV_USER_EMAIL` | `employee@example.com` |
| `DEV_USER_PASSWORD` | `dev-password` |
| `DEV_USER_ROLE` | `employee` |

### Observability

| Variable | Default |
|---|---|
| `LANGFUSE_ENABLED` | `false` |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | empty (tracing disabled if missing) |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` |

### Workflow tuning (all env-overridable) — see [RAG section](#rag-pipeline-thresholds-retry-values--tuning)

| Variable | Default |
|---|---|
| `SIMILARITY_THRESHOLD` | `0.62` |
| `MIN_DOC_SCORE` | `0.55` |
| `MAX_CLARIFICATION_ROUNDS` | `5` |
| `RECENT_HISTORY_KEEP` | `10` |

---

## Default Accounts

`POST /auth/login` auto-provisions dev accounts on first matching login (`src/api/auth.py`):

| Email | Password (from code) | Role |
|---|---|---|
| `employee@example.com` (or `DEV_USER_EMAIL`) | `dev-password` (or `DEV_USER_PASSWORD`) | employee |
| `engineer@example.com` | `dev-password11` | l1 |
| `l1@example.com` | `dev-password` | l1 |
| `admin@example.com` | `dev-password` | admin |

If a dev account exists in the DB with a different (unverifiable) hash, login re-hashes the known dev password and succeeds.

> ⚠️ Note: the login page's "L1 Engineer" quick-fill button (`App.tsx`) fills `engineer@example.com` / `dev-password`, but the backend expects `dev-password11` for that address. Use `l1@example.com` / `dev-password` for a guaranteed match.

`POST /auth/signup` accepts role `employee` | `engineer` | `admin` (mapped to `employee` / `l1` / `admin`) and a department (`hr`, `sales`, `ui_ux`, `ta` in the frontend dropdown; free-text server-side). Password min 8 chars, name 2–100 chars. Duplicate email → `409`.

---

## The AI Workflow (LangGraph)

`backend/src/workflow/graph.py` compiles a `StateGraph(AgentState)`. `AgentState` (`state.py`) carries: `messages` (LangGraph `add_messages` reducer), `input`, `sanitized_query`, `search_query`, `needs_clarification`, `escalate`, `needs_handoff`, `out_of_scope`, `retrieval_score`, `category`, `priority`, `priority_rationale`, `evidence`, `tool_history`, `status`, `user_context`, `confirmation_decision`, `awaiting_confirmation_reply`.

```
intake ─┬─ status == "human_takeover" ──► human ──► END
        └─► injection_pre_check ─┬─ EscalationPolicy hit ──► escalate
                                 ├─ awaiting_confirmation_reply ──► handle_confirmation ─┬─ "retry"    ──► retrieve (loop back)
                                 │                                                       ├─ "escalate" ──► escalate
                                 │                                                       └─ else       ──► END
                                 └─► preprocess ─┬─ needs_clarification / out_of_scope ──► END
                                                 └─► classify ──► retrieve ──► diagnose ─┬─ policy hit ──► escalate
                                                                                         └─► resolve ─┬─ policy hit / needs_handoff ──► escalate
                                                                                                      └─► verify ─┬─ leak detected ──► escalate
                                                                                                                  └─► present_confirmation ──► END

escalate ──► human ──► END      (fixed edges)
```

### Nodes

| Node | File | Behavior |
|---|---|---|
| `intake` | `nodes/intake.py` | Passes `input` through; the conditional edge exits to `human` when an engineer owns the conversation. |
| `injection_pre_check` | `nodes/intake.py` | 3 layers: (1) deterministic pattern list — *"ignore all previous instructions"*, *"system prompt"*, *"dan mode"*, *"jailbreak"*, *"grant me admin"*, etc. → instant block with `category=security_incident`, `priority=CRITICAL`; (2) benign bypasses — messages containing escalation keywords (`escalate`, `engineer`, `human`, `l1`, …) and short replies (`yes`, `1`, `thanks`, ≤2 words) skip the LLM; (3) LLM classifier returning exactly `INJECTION` or `SAFE`. On LLM failure, falls back to a second deterministic pattern list. |
| `preprocess` | `nodes/triage.py` | The triage brain. Handles gibberish (first offense → ask for clarity; **2 consecutive** gibberish turns → session cleanly closed, signature `out_of_scope=True, escalate=False, sanitized_query=""`); cold-open greeting check (`GREETING_ONLY` = {hi, hello, hey, help, test, ok}, or <4 chars); `sanitize_input()`; IT-scope check (`is_it_support_query`); mid-conversation topic-pivot detection (hard regex: pizza/uber/jokes/weather… + LLM `CONTINUE`/`ABANDONED` transcript check that defaults to CONTINUE on failure); new-issue detection (`_NEW_ISSUE_RE` — "another issue", "different problem", …) which clears the old `search_query`; search-query extraction that anchors on the first real problem statement and ignores short boilerplate replies; and a JSON LLM clarification loop (`sufficient` / one `question` / `category` / `priority` / `rationale`) capped at `MAX_CLARIFICATION_ROUNDS` (**5**). |
| `classify` | `nodes/triage.py` | Fast path: if preprocess already set a valid category ≠ `general_support`, returns it unchanged (no LLM call). Otherwise LLM JSON classification into `access / network / hardware / software / email / security / application` + priority `CRITICAL/HIGH/MEDIUM/LOW` with rationale. On LLM failure: keyword fallback (`malware/phishing/breach/outage` → critical; `locked out/won't boot/bsod` → high; `how do i/request` → low; default `general_support`/medium). |
| `retrieve` | `nodes/retrieval.py` | The only async node. Calls `RetrievalService.get_similar_documents(session, query, user_department)`; replaces prior `knowledge_and_incidents` evidence (dedupe across retries); stores `retrieval_score`. Logs when no docs clear the relevance floor. |
| `diagnose` | `nodes/resolution.py` | Deterministic path: `select_mock_tool()` keyword match (`vpn`/`network connection` → `vpn_check`; `device`/`laptop`/`compliance` → `device_check`), executed once per tool via `tool_history`, through `ToolGateway` with `target_id="mock123"`. LLM path: `bind_tools([vpn_check, device_check])`; every tool call the model makes is routed through the gateway; results (or errors) are appended to `evidence` and as `ToolMessage`s. |
| `resolve` | `nodes/resolution.py` | **Gate 1:** `retrieval_score < SIMILARITY_THRESHOLD` (default **0.62**) → escalate. The code comment explains why: scope was already decided in preprocess; a low score is a KB gap, not proof the topic is out of scope. **Gate 2:** no LLM available → escalate. **Gate 3:** generates the answer with evidence in the prompt, then `is_response_from_knowledge_base()` grounding check must pass, else escalate. Any exception → escalate. Success → `status="resolved"`. |
| `verify` | `nodes/resolution.py` | Output guardrail. Regex-scans the last AI message for leaks: `system prompt`, `developer instructions`, `ignore all previous instructions`, AWS keys (`AKIA…`), PEM private-key blocks, `password=…`, bearer JWTs, GitHub tokens (`ghp_…`). Hit → replaces the message with a generic escalation notice and sets `escalate/needs_handoff/status=escalated`. |
| `present_confirmation` | `nodes/confirmation.py` | After a resolved turn: asks *"Did that resolve the issue?"* with options **1** yes / **2** no / **3** not sure. Embeds invisible zero-width markers (`CONFIRM_MARKER`, `CONFIRM_FINAL_MARKER` — see constants) so the next turn can be routed as a confirmation reply. Second-pass variant says "updated my answer… otherwise I'll bring in an engineer". Sets `status="awaiting_confirmation"`. |
| `handle_confirmation` | `nodes/confirmation.py` | Classifies the reply (tiered): explicit-escalation regex **first** (a direct ask for a human is honored unconditionally); then deterministic phrase lists (`no` → "2/nope/still broken/didn't work…"; `yes` → "1/yes/fixed/it works…"; `ack` → "ok got it/will try/thanks…"; `unsure` → "3/not sure"); LLM `YES/NO/ACK/ESCALATE/UNSURE` classifier as fallback. Outcomes: **yes** → `confirmation_decision="resolved"`; **no** → `"retry"` with an enriched `search_query` (original problem + new detail if >3 words) → graph loops back to `retrieve` (**one automatic retry** — a second "no" after the final confirmation marker escalates); **ack** → stays in the loop; **follow-up question** ("how do I…", "what does step 3 mean") → answered directly by the LLM grounded in the last resolution message, stays in the loop; **unsure** or anything after the final marker → escalate. |
| `escalate` (= `handoff_node`) | `nodes/handoff.py` | Appends a `handoff_summary` evidence payload (`query`, `summary`, `evidence_count`, `retrieval_score`) for the engineer, and adds a user-facing "ticket created" AI message unless a recent escalation message already exists. |
| `human` | `nodes/handoff.py` | Terminal: sets `status="human_takeover"`. From then on `intake` routes around the AI entirely. |

### Escalation Policy

`workflow/escalation.py` — `EscalationPolicy.should_escalate(state)` returns `True` when **any** of:

1. `state.escalate is True` or `state.needs_handoff is True`
2. `state.category` ∈ `{"security_incident", "hardware_failure", "datacenter_outage"}`
3. **≥ 2** items in `evidence` contain an `"error"` key (i.e., two or more diagnostic tool failures)

The graph re-checks this after `injection_pre_check`, `diagnose`, `resolve`, and `verify`.

---

## RAG Pipeline: Thresholds, Retry Values & Tuning

All numbers below are read from source. Every one is env-overridable unless marked *hardcoded*.

### Master tuning table (`workflow/constants.py` + related)

| Constant | Default (env var) | Where enforced | Effect |
|---|---|---|---|
| `SIMILARITY_THRESHOLD` | **0.62** (`SIMILARITY_THRESHOLD`) | `resolve_node` | Minimum retrieval similarity to *attempt* an AI answer. Below → escalate to human. |
| `MIN_DOC_SCORE` | **0.55** (`MIN_DOC_SCORE`) | `RetrievalService` | Relevance floor. A KB doc or ticket scoring below this never enters `evidence`, so it can never ground an answer. |
| Keyword-fallback score floor | **0.55** (uses `MIN_DOC_SCORE`) | `_keyword_fallback` | Keyword results below the floor are discarded. |
| Keyword-fallback score cap | **0.70** *hardcoded* | `_keyword_fallback` | Score formula: `min(0.70, 0.45 + 0.04 × weighted_matches)`, where title matches weigh ×3 and content matches ×1. |
| Keyword-fallback trigger | **max score < 0.5** *hardcoded* | `get_similar_documents` | If vector retrieval's best score is under 0.5 (or nothing survived the floor), the keyword pass runs; its results win only if strictly better. |
| `MAX_CLARIFICATION_ROUNDS` | **5** (`MAX_CLARIFICATION_ROUNDS`) | `preprocess_node` | Hard cap on clarification/turn count before preprocess stops asking and pushes the query through. |
| `RECENT_HISTORY_KEEP` | **10** (`RECENT_HISTORY_KEEP`) | `history_utils.build_bounded_history` | Last 10 messages kept verbatim; older ones are LLM-summarized into one `SystemMessage` (2–3 sentences), with a naive 500-char truncation fallback if no LLM. |
| Gibberish session limit | **2 consecutive turns** *hardcoded* | `preprocess_node` | Two gibberish messages in a row close the session (no retrieval, no escalation). One → single clarification request. |
| Confirmation retry budget | **1 automatic retry** *hardcoded* | `handle_confirmation` + graph edge | First "no" loops back to `retrieve` with an enriched query. After the final-confirmation marker has been sent, any non-yes reply escalates. |
| Tool-call dedupe | **once per tool per conversation** *hardcoded* | `diagnose_node` `tool_history` | `vpn_check` / `device_check` never re-run for the same conversation. |
| Tool-error escalation budget | **≥ 2 errors** *hardcoded* | `EscalationPolicy` | Two failed tool executions in evidence force escalation. |
| Retrieval top-K | **5 + 5** *hardcoded* | `get_similar_documents(limit=5)` | Top 5 KB chunks + top 5 historical tickets per query. |
| `LLM_TEMPERATURE` / `LLM_SEED` | **0.0 / 42** (`LLM_TEMPERATURE` / `LLM_SEED`) | `resolve`, `diagnose` (and defaults for all LLM calls) | Deterministic generation. |
| `MAX_INPUT_WORDS` / `MAX_INPUT_CHARS` | **512 / 2048** *hardcoded* | `guardrails.sanitize_input` | Input truncation limits. |

### Retrieval flow (`services/retrieval_service.py`)

1. Embed the (bounded) search query with the configured embedding model. **No embedding model or failed embed → deterministic keyword fallback** (`_keyword_fallback`), so RAG degrades but never crashes.
2. **KB search:** `KnowledgeDocument.embedding.cosine_distance(query)` ordered ascending, `limit=5`, scoped `department == user_department OR department IS NULL` (global docs are visible to everyone).
3. **Ticket search:** same, against `tickets`, scoped `department == user_department` strictly.
4. Similarity score = `max(0.0, 1.0 − cosine_distance)` per row (cosine distance → cosine similarity).
5. Filter both result sets: keep only rows with `score ≥ MIN_DOC_SCORE` (**0.55**).
6. If nothing survived **or** best raw score `< 0.5` → run `_keyword_fallback` (stopword-filtered keyword overlap; title hit = 3 points, content hit = 1; score = `min(0.70, 0.45 + 0.04 × points)`); return keyword results only if their best score beats the vector best.
7. Return `(documents, max_score)` — `max_score` is what `resolve_node` compares against `SIMILARITY_THRESHOLD` (**0.62**).

> Code comment vs. code: `_keyword_fallback` says keyword matches are "capped below SIMILARITY_THRESHOLD", but the cap is 0.70 and the default threshold is now 0.62 — so a keyword-only result with ≥5 weighted matches (0.45 + 0.04×5 = 0.65) *can* clear the resolve gate. Harmless, but worth knowing when tuning.

### Answer generation & grounding

- Prompt contains the conversation (Human/AI turns only), the sanitized query, and the full JSON evidence blob.
- **Grounding check** (`guardrails.is_response_from_knowledge_base`) — the answer passes only if it matches evidence:
  - exact KB **title** found in the answer, **or**
  - ≥ **2** title words (>4 chars) found, **or**
  - ≥ **3** content words (>5 chars) found, **or**
  - ≥ **2** word matches against a diagnostic tool result.
  - Refusal phrases ("cannot answer", "don't know", "insufficient evidence", …) and empty evidence always fail. Length alone never passes.
- Fail → escalate. There is **no retry** at resolve level; the "retry" budget belongs to the confirmation loop.

### KB ingestion & embedding retry values (`seed_kb.py` + `rag/chunker.py`)

- `kb_articles.json` contains **100 valid articles** (verified by loading it; entries missing title/content are skipped with a warning).
- **Chunking** (`chunk_article`): target max **1800 chars** per chunk, **150 chars** sliding overlap, title prefixed to every chunk (`Article Title: …`). Articles are split on section headers (`Problem:`, `Symptoms:`, `Resolution Steps:`, `Edge Case:`, `Affected Systems:`, `Category:`, `IMPORTANT:`, `NOTE:`, or markdown `#` headings); a `Resolution Steps` section longer than **600 chars** is split into numbered steps before grouping.
- **Embedding generation** (`generate_embeddings`):
  - Batch size **25** chunks per embedding call.
  - Rate-limit retries: **max 5 attempts** per batch on `RESOURCE_EXHAUSTED` / HTTP 429.
  - Backoff: starts at **16.0 s**, multiplied by **1.5×** per retry (16 → 24 → 36 → 54 → 81 s).
  - Non-rate-limit errors fail immediately.
  - **1.0 s** pause between successful batches.
- Rows are written to `knowledge_documents` with `document_id` (one UUID per article), `chunk_index`, `department`, and `metadata` JSONB.

### History bounding (`workflow/utils/history_utils.py`)

- `build_bounded_history`: if the loaded conversation exceeds `RECENT_HISTORY_KEEP` (**10**) messages, the older tail is summarized by the LLM ("2–3 sentences, facts only") into a single `SystemMessage` prepended to the recent 10.
- Fallbacks: no LLM or summarization failure → naive 500-char truncation of the transcript. Context is bounded, never silently dropped.
- `SYSTEM` messages (engineer notes, closure notices) are excluded from LLM context entirely (`api/conversations.py::_load_history`).

---

## Security Model

| Layer | Implementation |
|---|---|
| Authentication | JWT HS256, `SECRET_KEY` env, **30-minute** expiry (`ACCESS_TOKEN_EXPIRE_MINUTES = 30`). Passwords hashed with bcrypt (`bcrypt<4.0.0` pinned for passlib compatibility). |
| Authorization | `RoleChecker(allowed_roles)` dependency, enforced server-side. Roles: `employee`, `l1`, `l2`, `support_lead`, `admin`. |
| Input sanitization | `sanitize_input()`: strips zero-width/bidi-override Unicode (`U+200B–200F`, `U+202A–202E`, `U+2060–2064`, `U+FEFF`) and control chars, `{{ }}`/`{% %}` template expressions, HTML tags; collapses whitespace; caps at 512 words / 2048 chars. Internal confirmation markers are masked and restored so routing keeps working. |
| Prompt-injection defense | Deterministic pattern filter → LLM classifier → deterministic fallback (see workflow). Injected messages become `security_incident` / `CRITICAL` escalations. |
| Output leak guard | `verify_node` regexes: system-prompt disclosure, credential patterns (AWS `AKIA`, PEM keys, `password=`, bearer tokens, `ghp_` tokens). |
| Tool authorization | `ToolGateway` allowlist `{"vpn_check", "device_check"}`. Unauthorized tool name → HTTP **403** + warning log with the acting user. The LLM never executes code directly. |
| Data isolation | Retrieval is department-scoped; conversation reads require ownership or a support role; `confirm-resolution` requires ticket ownership. |
| Scope control | `is_it_support_query`: LLM `IN_SCOPE`/`OUT_OF_SCOPE` gatekeeper with a fast trivia-regex rejection list and a ~150-term IT keyword fallback. Non-IT queries are refused, never answered. |
| Audit trail | `audit_events` records `TICKET_ESCALATED`, `TICKET_AUTO_RESOLVED`, `TICKET_STATUS_CHANGED`, `TICKET_TAKEOVER`, `CONVERSATION_CLOSED` with trace_id, actor, and JSONB details. |
| Grounding | Answers must cite retrieved evidence (see above) or the turn escalates instead of answering. |

---

## API Reference

Interactive docs: `/docs` (Swagger) and `/redoc` on the backend origin. Root `GET /` returns `{"message": "AI Helpdesk API is running"}`.

### Observability (`src/api/health.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | none | `{"status": "ok"}` |
| GET | `/ready` | none | Pings the DB (`SELECT 1`); reports `db: ok/error` |

### Auth (`src/api/auth.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/login` | none | OAuth2 form (`username`/`password`). Returns `access_token`, `token_type: bearer`, `user {email, role}`. Auto-provisions dev accounts. |
| POST | `/auth/signup` | none | JSON `{name, email, password, role, department}`. Returns the same token shape. `409` on duplicate email. |

### Conversations (`src/api/conversations.py`)

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/conversations` | any logged-in user | The caller's conversations with auto-titles (first user message line, 45 chars), preview (60 chars), `owner_type`, `status`, linked `ticket_status`, `message_count`. |
| POST | `/conversations` | any logged-in user | Creates a conversation owned by AI. |
| GET | `/conversations/{id}/messages` | owner or support role | Full message history (USER / AI / SYSTEM). `400` bad UUID, `404` missing, `403` otherwise. |
| POST | `/conversations/{id}/messages` | logged-in user | **The main AI endpoint.** Support-role senders are persisted as `SYSTEM` messages prefixed `[Engineer]` and bypass the graph. Employee messages: load bounded history → detect confirmation markers on the last persisted AI message → persist the user message → invoke the LangGraph graph → persist new AI messages → side effects (see below). Closed conversations reject new messages (`400`). |
| POST | `/conversations/{id}/takeover` | `engineer, l1, l2, support_lead, admin` | Sets `owner_type=HUMAN`; transitions an `ESCALATED` linked ticket to `IN_PROGRESS` (with history + audit rows). |
| POST | `/conversations/{id}/close` | owner or support role | Closes the conversation; linked ticket → `RESOLVED` (support) or `CLOSED` (owner), with history + audit; appends a `SYSTEM` closure message. |

**Side effects inside `POST …/messages`:**

- Ticket classification (category / priority / rationale) is **preserved across turns** from the conversation's existing ticket.
- `confirmation_decision == "resolved"` → conversation CLOSED; existing ticket → CLOSED (with history row), or a new ticket is created as `RESOLVED` titled `[{category}] {first 50 chars of original issue}` with a generated embedding, plus a `TICKET_AUTO_RESOLVED` audit event.
- Escalated final state → `owner_type=HUMAN`; new ticket `ESCALATED` (or existing re-escalated) with embedding + `TICKET_ESCALATED` audit; the last AI response gets a `**Ticket Reference:**` `#XXXXXXXX` suffix (first 8 UUID chars) appended, or a fallback escalation message is added.
- Non-escalated, non-confirmed turns with a valid category → a `NEW` ticket is created if none exists yet.
- Gibberish termination signature (`out_of_scope=True`, no escalation, empty `sanitized_query`, `resolved`) → conversation CLOSED so the loop can't repeat.

### Tickets (`src/api/tickets.py`)

All require one of `engineer, l1, l2, support_lead, admin` except `confirm-resolution`.

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/tickets` | support roles | All tickets with id, title, status, priority, rationale, category, conversation_id. |
| POST | `/tickets/{id}/resolve` | support roles | `TicketService.update_status` → `RESOLVED` (state machine validated); linked conversation CLOSED + system message. |
| POST | `/tickets/{id}/confirm-resolution` | ticket owner | Only from `RESOLVED` → `CLOSED`. |
| GET | `/tickets/{id}/similar` | support roles | pgvector similarity search for the ticket description; returns other **tickets** (current one excluded) — the duplicate/incident detector. |

### Diagnostics (`src/api/diagnostics.py`)

Router-level `RoleChecker(["employee", "l1", "l2"])` — note `support_lead`/`admin` are *not* in this list.

| Method | Path | Response |
|---|---|---|
| POST | `/diagnostics/vpn` | `{"status": "online", "mocked": true}` |
| POST | `/diagnostics/account` | `{"status": "active", "mocked": true}` |
| POST | `/diagnostics/device` | `{"status": "compliant", "mocked": true}` |

---

## Ticket State Machine

`TicketService.VALID_TRANSITIONS` (`services/ticket_service.py`) — invalid transitions raise `400`:

```
NEW ──► TRIAGED, ESCALATED
TRIAGED ──► IN_PROGRESS, ESCALATED
IN_PROGRESS ──► RESOLVED, ESCALATED
RESOLVED ──► CLOSED, ESCALATED
CLOSED ──► (terminal)
ESCALATED ──► IN_PROGRESS, RESOLVED, CLOSED
```

Every transition writes a `ticket_history` row (`old_status`, `new_status`, `changed_by`) and a `TICKET_STATUS_CHANGED` audit event.

Priorities: `CRITICAL`, `HIGH`, `MEDIUM` (default), `LOW`. Invalid/absent priority values fall back to `MEDIUM` (`_resolve_ticket_priority`).

---

## Database Schema

Seven tables (SQLAlchemy models in `src/models/`, migrations in `alembic/versions/`):

| Table | Key columns |
|---|---|
| `users` | id UUID, name, email (unique, indexed), hashed_password, role enum (`employee`/`l1`/`l2`/`support_lead`/`admin`), department |
| `conversations` | id, user_id FK, `owner_type` (`AI`/`HUMAN`), `status` (`ACTIVE`/`CLOSED`), timestamps |
| `messages` | id, conversation_id FK, `sender_type` (`USER`/`AI`/`SYSTEM`), content, trace_id, created_at |
| `tickets` | id, user_id FK, conversation_id FK, status enum, priority enum, category, title, description, **embedding `vector(3072)`**, department, priority_rationale, timestamps |
| `ticket_history` | id, ticket_id FK, old_status, new_status, changed_by (NULL = system/AI), changed_at |
| `audit_events` | id, trace_id (indexed), action, entity_type, entity_id, actor, details JSONB, created_at |
| `knowledge_documents` | id, **document_id** (per-article UUID, indexed), **chunk_index**, title, content (Text), **embedding `vector(3072)`**, metadata JSONB, department, timestamps |

**Migration chain** (in order): `baseline_0001` (users/chat) → `1234abcd5678` (tickets/history/audit) → `pgvector_abcd1234` (knowledge + `CREATE EXTENSION vector`) → `pgvector_tickets` (embeddings + department columns) → `14374703e4f9` (priority) → `6d2f8363dfc9` (priority_rationale) → `5a6381fc5d41` (ticket embedding → 3072) → `de3b484134cf` (document_id/chunk_index backfilled NOT NULL, content → Text, index).

Alembic runs async via `DATABASE_URL` from the environment (`alembic/env.py` ignores the URL in `alembic.ini`).

---

## Observability

- **Trace IDs** (`core/logging.py`): `TraceIdMiddleware` accepts an incoming `X-Trace-Id` or generates a UUID4, stores it in a context var, echoes it on the response, and every `ai_helpdesk` log line carries `[trace_id=…]`. Audit events and the Langfuse config reuse it.
- **Langfuse tracing** (`core/observability.py`): opt-in via `LANGFUSE_ENABLED=true` + keys. The callback handler tags runs `["langgraph", "helpdesk"]`, groups by `langfuse_session_id = conversation_id`, sets `langfuse_user_id` to the user email, and attaches department/role metadata. Buffer is flushed on app shutdown.

---

## Frontend

Plain React state (no client router in use despite `react-router-dom` being a dependency) — `App.tsx` switches views from the logged-in role: `employee` → Employee Portal, `l1`/`l2`/`support_lead` → Engineer Dashboard, `admin` → Admin Dashboard.

- **Session** (`auth/session.ts`): token + user in **sessionStorage** (`helpdesk_access_token`, `helpdesk_user`); active conversation id in `employee_active_conv`. Closing the tab logs out.
- **API client** (`api/client.ts`): `fetch` wrapper injecting `Authorization: Bearer`, JSON errors surfaced as `ApiError {message, status}`. Base URL: `VITE_API_BASE_URL` (default `/api`; `fe.env` sets `http://127.0.0.1:8000` for non-Docker dev; Vite dev proxy forwards `/api` → `http://backend:8000` stripping the prefix).
- **Login screen**: sign-in/sign-up toggle, role + department selects, password confirmation, and one-click dev-account fill buttons.

### Portals

| Portal | Features |
|---|---|
| `EmployeePortal.tsx` | Chat with markdown-rendered AI messages, typing indicator, optimistic send with rollback on failure, "Agent activity" panel decoded from the returned workflow state (category, retrieval similarity %, tools executed, referenced KB chunks with scores, escalation), human-takeover banner, End Conversation, conversation history tabs (All / Active / History). |
| `EngineerDashboard.tsx` | Ticket queue tabs (Active / History), real-time **new-escalation pop-up banner** (diffs escalated IDs between polls), full transcript with `[Engineer]` messages rendered as support turns, similar-incidents strip (pgvector duplicate detection), **Take Over Chat**, **Mark Resolved**, live reply box (enabled once `IN_PROGRESS`), AI priority rationale shown in the console header. |
| `AdminDashboard.tsx` | Operational analytics: status breakdown bars, category donut (CSS conic-gradient) with a deep-dive modal + full category table, AI-vs-human handoff percentages ("AI Efficiency Index" = resolved/total), collapsible panel; incident queue table with a conversation **audit modal** that replays any transcript. |

### Polling intervals (all pause when `document.hidden`)

| Screen | What | Interval |
|---|---|---|
| Employee Portal | conversation list | **8 s** |
| Employee Portal | active conversation messages | **4 s** |
| Engineer Dashboard | ticket list (also drives the escalation pop-up) | **5 s** |
| Engineer Dashboard | selected conversation messages | **5 s** |
| Admin Dashboard | ticket/analytics data | **7 s** |

---

## Testing

### Backend (pytest) — `backend/tests/`

| Suite | Covers |
|---|---|
| `workflow/test_injection.py` | Deterministic + LLM injection blocking, injection blocked even mid-confirmation (full graph invoke), ticket-priority resolution helper |
| `workflow/test_rag_pipeline.py` | Sanitizer behavior (template stripping, technical punctuation preserved, 512-word cap), tool selection, grounding check, resolve below/above threshold, out-of-scope rejection, leak detection in `verify` |
| `workflow/test_confirmation.py` | Escalation-intent regex, deterministic reply classification, yes→resolved, no→retry (enriched query), second no→escalate, and a full graph test asserting category/priority survive a retry |
| `workflow/test_escalation.py` | `EscalationPolicy` rules |
| `workflow/test_hallucination.py` | Ungrounded answers must not resolve |
| `workflow/test_retrieval.py` | Retrieval service behavior |
| `workflow/test_robustness_guardrails.py` | Sanitizer/gibberish edge cases |
| `workflow/test_triage_optimization.py` | Preprocess/classify fast paths |
| `workflow/test_takeover.py` | Takeover guard (placeholder) |
| `tools/test_gateway.py` | Allowlist enforcement / 403 |
| `core/test_audit.py` | Audit event writing |
| `test_chunker.py` | Chunking: single-chunk short articles, validation errors, 10-article run with overlap/title-prefix assertions |
| `tests/workflow/persona.py` | Shared `PERSONA_VOICE` + `GROUNDING_RULE` prompt strings (mirrored inline in `triage.py`) |
| `performance/locustfile.py` | Locust: health/ready weighted tasks (auth'd endpoints are mocked as health hits) |

```bash
docker compose exec backend pytest tests/ -v
# or locally: cd backend && pytest tests/ -v
```

### Frontend

- `e2e/workflow.spec.ts` — Playwright user stories: US1 automated intake & resolution, US2 escalation → engineer takeover, US3 similar-incidents visibility. `npx playwright test` (first run: `npx playwright install`).
- `tests/base.test.ts` — Vitest placeholder.

### CI (`.github/workflows/ci.yml`, on push/PR to `main`)

| Job | Steps |
|---|---|
| `backend-test` | Python 3.12 → install → `pytest tests/` → `bandit -r src/` |
| `frontend-test` | Node 20 → `npm ci` → `npm run lint` (zero-warning ESLint) → Playwright with deps → E2E |
| `performance-test` | Postgres 16 + pgvector service → `alembic upgrade head` → uvicorn in background → Locust headless: **50 users, 10/s ramp, 15 s** |

---

## Project Structure

```
├── docker-compose.yml              # db / backend / frontend / adminer
├── .env.example                    # provider + observability template
├── .github/workflows/ci.yml        # pytest + bandit + lint + E2E + Locust
│
├── backend/
│   ├── alembic/                    # async migrations (8 revisions)
│   ├── src/
│   │   ├── main.py                 # FastAPI app, middleware, routers
│   │   ├── api/                    # auth, conversations, tickets, diagnostics, health
│   │   ├── auth/security.py        # JWT, bcrypt, RoleChecker
│   │   ├── core/                   # db, llm factory, logging (trace ids), observability (Langfuse)
│   │   ├── models/                 # user, chat, ticket, knowledge (SQLAlchemy + pgvector)
│   │   ├── rag/chunker.py          # section-aware chunking (1800/150)
│   │   ├── services/               # retrieval_service (pgvector + keyword fallback), ticket_service
│   │   ├── tools/gateway.py        # tool allowlist gateway
│   │   └── workflow/
│   │       ├── graph.py            # StateGraph wiring + conditional edges
│   │       ├── state.py            # AgentState TypedDict
│   │       ├── constants.py        # SIMILARITY_THRESHOLD 0.62, MIN_DOC_SCORE 0.55, rounds 5, history 10, markers
│   │       ├── escalation.py       # EscalationPolicy
│   │       ├── nodes/              # intake, triage, retrieval, resolution, confirmation, handoff
│   │       └── utils/              # guardrails, history_utils
│   ├── kb_articles.json            # 100 KB articles (seeding source)
│   ├── seed_kb.py                  # chunk-aware seeder (25/batch, 5 retries, 16s×1.5 backoff)
│   ├── requirements.txt / pyproject.toml / Dockerfile
│   └── tests/                      # pytest suites (see Testing)
│
└── frontend/
    ├── src/
    │   ├── App.tsx                 # role-based view switching + login/signup screen
    │   ├── api/                    # client.ts (fetch + JWT), types.ts
    │   ├── auth/session.ts         # sessionStorage token/user
    │   ├── components/MarkdownRenderer.tsx
    │   └── portals/                # EmployeePortal, EngineerDashboard, AdminDashboard
    ├── e2e/workflow.spec.ts        # Playwright E2E
    ├── vite.config.ts              # /api proxy → backend:8000
    └── package.json / Dockerfile
```

---

## Code-Accuracy Notes

Small inconsistencies observable in the current source (listed so nobody is surprised by them):

1. **Frontend displays a hardcoded 72% cutoff.** `EmployeePortal.buildActivity` prints `RAG Retrieval Similarity Score: X% (Cutoff: 72.0%)`, but the backend's actual resolve gate defaults to **`SIMILARITY_THRESHOLD = 0.62`** and is env-tunable. The backend score shown is correct; only the cutoff label is stale.
2. **`engineer@example.com` dev password.** Backend defines it as `dev-password11`; the login page quick-fill uses `dev-password`. `l1@example.com` / `dev-password` always matches.
3. **Keyword-fallback cap comment.** `_keyword_fallback` caps scores at 0.70 "below SIMILARITY_THRESHOLD" per its comment, but 0.70 > 0.62, so strong keyword-only matches can clear the resolve gate.
4. `requirements.txt` lists `langchain-xai`, but `core/llm.py` talks to xAI through the OpenAI-compatible `ChatOpenAI` path (`XAI_BASE_URL`); the xAI embeddings path uses `OpenAIEmbeddings` with the xAI key/base URL.
5. `POST /tickets/{id}/confirm-resolution` checks `ticket.created_by`, a field that doesn't exist on the `Ticket` model — effectively an ownership check to treat with care until fixed.
