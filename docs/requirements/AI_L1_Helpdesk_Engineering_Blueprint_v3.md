# AI L1 IT Helpdesk — Engineering Blueprint (v3 Consolidated)

**Source:** *Improved Architecture & 6-Day Delivery Plan v3.0*
**Purpose of this document:** a single, execution-ready blueprint — the architecture decisions, the data contracts, the AI control flow, and the delivery plan — condensed into the form a tech lead would actually keep open during the six days.

---

## 1. The One-Paragraph System Story

> FastAPI owns application and security boundaries. LangGraph owns the AI workflow as an explicit, inspectable state machine. LangChain is used only where it removes integration boilerplate (model calls, structured output, embeddings) — never for business logic. PostgreSQL is the single system of record; pgvector lives inside it for semantic retrieval and duplicate detection, so there is no second database to operate. Every tool call passes through a Tool Gateway that authorizes independently of what the LLM asked for. Escalation is a deterministic policy, not a model opinion. Human takeover is an explicit ownership flag, not a soft pause. Every important action carries one `trace_id` from request to audit log.

This sentence is the answer to almost every "why did you build it this way" question in §16 below.

---

## 2. Final Target Architecture

```
                    Employee Portal (React/TS/Vite)          Engineer Dashboard (React/TS/Vite)
                              │                                          │
                              └──────────────── REST / WebSocket ────────┘
                                                 │
                              ┌──────────────────────────────────────────┐
                              │              FASTAPI APPLICATION          │
                              │  Auth/RBAC · Conversations · Tickets ·    │
                              │  Dashboard · Audit                        │
                              │                    │                      │
                              │                    ▼                      │
                              │           AI Orchestrator                 │
                              │                    │                      │
                              │          Injection Pre-Check              │
                              │                    │                      │
                              │                    ▼                      │
                              │              LangGraph                    │
                              │        ┌───────────┼────────────┐         │
                              │        ▼            ▼            ▼         │
                              │   Retrieval   Tool Gateway  Escalation     │
                              │                                Policy      │
                              └──────┬────────────┬──────────────────────┘
                                     ▼             ▼
                              PostgreSQL       pgvector
                              users/tickets/   KB embeddings /
                              messages/audit/  ticket embeddings /
                              diagnostics       similarity
                                     │
                                     ▼
                              Mock Integrations
                              VPN · Account · Application · Device
```

**Deployment shape:** modular monolith. Logical module boundaries (listed in §3) are real code boundaries, but the initial deployable is a small number of containers — not independent microservices. This is a scoping decision for a 6-day build, not a permanent architectural ceiling; the module boundaries are what make later extraction credible.

---

## 3. Module Boundary Map (code-level, even inside one deployable)

| Module | Owns |
|---|---|
| Employee Portal | auth UI, issue submission, chat, resolution confirm/reject, ticket status |
| Engineer Dashboard | open/escalated queues, AI analysis view, takeover/guide/return controls, basic analytics |
| FastAPI app layer | routing, auth, authorization, WebSocket, dashboard APIs |
| Conversation & case management | conversation ownership, message persistence |
| AI Orchestrator | injection pre-check → LangGraph invocation → deterministic policy layer |
| LangGraph workflow | Intake → Clarify → Classify → Retrieve → Diagnose → Resolve → Verify → Escalate/Handover |
| RAG / retrieval | pgvector queries, evidence assembly |
| Tool Gateway | tool wrapper, authorization, allowlist, mock integration dispatch |
| Ticketing / state machine | ticket status transitions, idempotency |
| Auth/RBAC | JWT/session, role checks, object-level authorization |
| Audit | append-only event log |
| PostgreSQL | all transactional/operational state |
| pgvector | semantic retrieval + duplicate detection |
| Observability | trace IDs, structured logs, health/ready |

---

## 4. Technology Decision Matrix

| Area | Decision | One-line reason |
|---|---|---|
| Frontend | React + TS + Vite | fast, familiar, fine for two thin UIs |
| Backend | Python + FastAPI | async, WebSocket, easy AI integration |
| AI orchestration | **LangGraph** | explicit stateful workflow, branching, human-in-loop |
| AI integration | **LangChain, selectively** | model abstraction, tools, structured output, embeddings — not business logic |
| LLM | configurable provider | avoid hard-coupling |
| Primary DB | **PostgreSQL** | dominant workload is transactional (tickets, RBAC, audit) |
| Vector search | **pgvector** | semantic retrieval without a second database |
| ORM | SQLAlchemy | mature |
| Auth | JWT/session | server-side identity is non-negotiable |
| Real-time | WebSocket where useful, REST otherwise | don't let real-time become a blocker |
| Testing | pytest + Playwright | unit/API/security/E2E |
| Containers | Docker + Compose | repeatable, no orchestration overhead |
| CI/CD | GitHub Actions | automated quality gates |
| Observability | structured JSON logs + trace IDs + health/ready | required for failure diagnosis |

**PostgreSQL vs Neo4j (explicitly rejected):** the dominant workload is CRUD ticketing, RBAC, conversation history, audit, and semantic retrieval — not multi-hop graph traversal. A graph-*shaped* domain (employee→device→app→service→incident) does not automatically require a graph database. Neo4j becomes justified only if the product grows into deep IT-dependency/knowledge-graph reasoning — not for this scope.

---

## 5. Core Architecture Principles (the non-negotiables)

1. **AI-first, human-backed** — automate supported L1 work; don't force automation when confidence/authorization is insufficient.
2. **The LLM is not the security boundary** — server-side identity, RBAC, object-level authorization, tool allowlisting, deterministic escalation, audit logging all sit outside the model.
3. **Evidence before claims** — the AI never invents system state, outage status, fixes, policy, or permissions; it calls a diagnostic tool instead.
4. **Application state and knowledge are distinct** — Postgres answers "what's happening"; pgvector answers "what's relevant."
5. **Human takeover is explicit** — `conversation.owner = HUMAN` and the AI stops generating for that conversation until ownership returns.
6. **State transitions are explicit** — tickets cannot arbitrarily jump status.
7. **Every important action is traceable** — one `trace_id` from request → AI decision → retrieval → tool call → ticket creation → audit event.

---

## 6. Data Model Blueprint

### 6.1 PostgreSQL (system of record)

```
users(id, name, email, role)
  role ∈ {employee, l1, l2, support_lead, admin}

conversations(id, user_id, owner_type, status, created_at, updated_at)
  owner_type ∈ {AI, HUMAN}

messages(id, conversation_id, sender_type, content, created_at, trace_id)

tickets(id, conversation_id, user_id, category, priority, status,
        summary, resolution, created_at, updated_at)

ticket_history(id, ticket_id, from_status, to_status, actor_id, reason,
               created_at, trace_id)

diagnostics(id, ticket_id, tool_name, input_summary, result,
            created_at, trace_id)

tool_invocations(id, tool_name, authorized, actor_type, result,
                  created_at, trace_id)

audit_events(id, actor_id, event_type, resource_type, resource_id,
             metadata, created_at, trace_id)

resolution_confirmations(id, ticket_id, user_id, result, feedback,
                          created_at, trace_id)
```

Every row that matters for security or reconstruction of "what happened" carries `trace_id` — this is what makes the observability story (§10) real rather than aspirational.

### 6.2 pgvector (knowledge + similarity, same Postgres instance)

```
knowledge_documents(id, title, source, content, metadata, embedding)
ticket_embeddings(ticket_id, embedding)
```

Retrieval metadata fields worth indexing on: `document_id, title, category, issue_type, source_type, version, updated_at, access_scope`.

### 6.3 Ticket state machine (server-enforced, not suggested)

```
NEW → TRIAGED → IN_PROGRESS → RESOLVED → CLOSED
                     │              │
                     └→ ESCALATED   └→ IN_PROGRESS (on user rejection)
```

| From | To | Allowed |
|---|---|---|
| NEW | TRIAGED | yes |
| TRIAGED | IN_PROGRESS | yes |
| TRIAGED | ESCALATED | yes |
| IN_PROGRESS | RESOLVED | yes |
| IN_PROGRESS | ESCALATED | yes |
| RESOLVED | CLOSED | yes, after confirmation |
| RESOLVED | IN_PROGRESS | yes, if user rejects resolution |
| CLOSED | IN_PROGRESS | **no**, unless an explicit reopen policy exists |

A rejected resolution reopens the ticket — it never silently closes.

---

## 7. AI Workflow Blueprint (LangGraph)

```
START → Intake → Injection Pre-Check → Clarify? ─yes→ Clarify ─┐
                                          │no                   │
                                          └───────────────┬─────┘
                                                           ▼
                                                       Classify
                                                           │
                                                           ▼
                                                       Retrieve (RAG)
                                                           │
                                                           ▼
                                                       Diagnose (tools)
                                                           │
                                                           ▼
                                                        Resolve
                                                           │
                                                           ▼
                                                        Verify ─yes→ Close
                                                           │no
                                                           ▼
                                                       Escalate → Handover → Human/L1
```

| Node | Responsibility | Guardrail |
|---|---|---|
| Intake | capture message, authenticated identity, conversation_id, trace_id | identity comes from session, never from message text |
| Injection Pre-Check | detect attempts to override instructions, exfiltrate other users' data, invoke restricted tools | defense-in-depth, not the *only* control |
| Clarify | ask only what's needed for safe triage | — |
| Classify | return `{category, priority, confidence, rationale}` | **schema-validated structured output**, not free-text parsing |
| Retrieve | query synthetic KB + resolved historical tickets via pgvector | evidence returned with metadata, not raw generation |
| Diagnose | call `check_account_status`, `check_vpn_status`, `check_application_status`, `check_device_status` | identity/target from authenticated context, never LLM-invented |
| Resolve | propose a fix supported by retrieved evidence + diagnostic output + approved procedures | never invent a fix |
| Verify | ask explicitly whether the fix worked → `CONFIRMED / REJECTED / NEEDS_HUMAN` | directly satisfies "confirm resolution" requirement |
| Escalate | deterministic policy (§8) decides, not model discretion | |
| Handover | produce engineer-facing summary: issue, category, priority, clarification, evidence, diagnostics, actions tried, escalation reason, recommended next step | preserves full context so the engineer never restarts the investigation |

---

## 8. Deterministic Escalation Policy

The LLM proposes; hard rules decide.

```python
if sensitive_request:            escalate()
if privileged_action_requested:  escalate()
if unsupported_issue:            escalate()
if confidence < MIN_CONFIDENCE:  escalate()
if diagnostic_evidence_missing:  escalate()
if troubleshooting_failed:       escalate()
```

This is the concrete implementation of Principle 2 (§5) — escalation is never something the model talks itself into or out of.

---

## 9. Security & Authorization Blueprint

**Identity binding — never trust:**
- a `user_id` supplied by the frontend
- a `user_id` generated by the LLM

**Always:** `JWT/session → authenticated principal → server-side authorization → DB query`.

**Per-request pattern** (e.g. `GET /tickets/{id}`):
1. Authenticate user.
2. Load ticket.
3. Check ownership/role.
4. Allow or deny.
5. Record an audit event.

**Tool authorization matrix:**

| Tool/action | Access |
|---|---|
| Check own account | Employee / AI-in-employee-context |
| Check own VPN | Employee / AI-in-employee-context |
| Check application status | AI / L1 / L2 |
| Check device status | AI / L1 / L2 |
| Search another user's ticket | Restricted |
| Privileged state-changing action | Explicit authorization + confirmation |
| Security-sensitive operation | Escalate |

The tool layer **rejects unauthorized calls even if the LLM requests them** — the model asking is never sufficient.

**Prompt-injection defense in depth:**
```
User Input → Injection pre-check → LLM policy prompt → Tool allowlist
           → Authorization → Object-level access control → Audit
```
Attack test set to run in CI: instruction-override attempts, cross-user data requests, fake-admin claims, restricted-tool invocation, system-prompt exfiltration. **A successful result is not "the model refused" — it's that unauthorized data/tools stay inaccessible even if the model behaves incorrectly.**

---

## 10. API Contract (frozen Day 1)

```
POST   /auth/login

POST   /conversations
GET    /conversations/{id}
POST   /conversations/{id}/messages
POST   /conversations/{id}/takeover
POST   /conversations/{id}/return-to-ai

POST   /tickets                          (Idempotency-Key required)
GET    /tickets
GET    /tickets/{id}
PATCH  /tickets/{id}
GET    /tickets/{id}/history
POST   /tickets/{id}/confirm-resolution
POST   /tickets/{id}/reject-resolution

POST   /diagnostics/vpn
POST   /diagnostics/application
POST   /diagnostics/account
POST   /diagnostics/device

GET    /dashboard/summary
GET    /dashboard/tickets

GET    /health
GET    /ready
```

Idempotency: retrying `POST /tickets` with the same `Idempotency-Key` must never create a second ticket — this is distinct from duplicate detection (§11) and solves a different problem (retry safety vs. related-incident detection).

`docs/api-contracts.md` should define request/response schemas, error format, enum values (status/category/priority/escalation reason), tool I/O schemas, trace-ID requirements, and idempotency behavior — with an **automated contract test in CI** between AI Orchestrator and Ticketing API to kill contract drift early.

---

## 11. RAG & Duplicate Detection

**Corpus (deliberately small, realistic):** ~8–12 synthetic KB documents (VPN, password/account, application outage, device, email, software requests, security escalation, runbooks) + ~20–30 synthetic historical tickets.

**Retrieval rule:** answer from retrieved evidence. If evidence is insufficient — **do not guess; state uncertainty; clarify or escalate.**

**Duplicate/related-incident detection** (semantic, not string match):
```
New issue → embed → pgvector similarity search → filter by metadata
          → score: above threshold = "likely related", below = new issue
```
Similarity indicates *likely related*, never *automatically identical* — the dashboard must show the evidence so an engineer can judge it.

---

## 12. Observability & Reliability

Every log line carries `trace_id`:
```json
{"trace_id":"abc123","service":"ai-orchestrator","event":"tool_call",
 "user_id":"user-123","tool":"check_vpn_status","outcome":"success"}
```
Log the full lifecycle: request received → classification → retrieval → tool call/result → ticket creation → escalation → human takeover → resolution confirmation → authorization failure → service error.

`/health` and `/ready` are mandatory; the team must be able to **deliberately fail a component and diagnose it from logs alone** — this is tested in the demo (§15).

---

## 13. Team Ownership (4 engineers)

| Lane | Owns |
|---|---|
| **M1** — AI/Conversation/RAG | LangGraph nodes, classification, clarification, retrieval, KB, AI evaluation |
| **M2** — Backend/Ticketing/Auth | domain model, state machine, ticket API, JWT/RBAC, idempotency |
| **M3** — QA/Security | FR/AC matrix, injection attack list, pytest/Playwright scaffolding, security suite |
| **M4** — DevOps/Platform | repo scaffold, Docker/Compose, CI, structured logging, health endpoints |

Cross-training rule: daily standup + swap-in sessions + cross-lane PR review, so no single lane becomes a bus-factor risk during the six-day window.

---

## 14. Six-Day Execution Plan (condensed)

| Day | Theme | Exit criteria |
|---|---|---|
| **1** | Foundations, architecture, contracts | repo works · contracts documented · Compose starts · migrations run · health endpoint works · test framework runs · AI workflow stub executes |
| **2** | Core build + first vertical slice | **Employee → Portal → submit issue → AI classifies → ticket created → visible in UI** works end-to-end, even roughly |
| **3** | Integration, tools, RAG, security | one complete path — Issue → Clarify → Classify → Retrieve → Diagnose → Ticket/Resolution — works with visible evidence and trace ID |
| **4** | Escalation, human takeover, hardening | escalation works · takeover works · AI stops when human owns conversation · return-to-AI works · injection defense works · audit trail exists |
| **5** | Full coverage, performance, hardening | every AC has Requirement → Implementation → Test → Evidence → Demo path |
| **6** | Freeze, rehearse, present | midday code freeze (fix only demo/security/critical blockers); 17-step rehearsal run through |

**Governing rule:** do not reverse the priority order in §17 by polishing UI or adding infrastructure early. Day 2's vertical slice is the single most important checkpoint — if it slips, everything downstream compresses.

---

## 15. Final Demonstration Script (7 scenarios, rehearsed)

1. Password reset — safe L1 resolution + confirmation
2. HR Portal outage — diagnostic + ticket creation
3. VPN issue — clarification + diagnostic
4. Human takeover — explicit ownership handoff
5. Prompt injection attempt — defense-in-depth holds
6. Controlled failure — deliberately break a component, diagnose from logs
7. Analytics — dashboard metrics

Every team member narrates their own lane but should be able to explain the whole system — this is what the cross-training rule in §13 is for.

---

## 16. P0 / P1 Scope Fence

**P0 (must ship):** portal, dashboard, auth, RBAC, ticket state machine + CRUD, conversation persistence, LangGraph workflow, classification, clarification, RAG, ≥1 diagnostic tool, escalation, human takeover, resolution confirmation, duplicate detection, audit, trace IDs, structured logs, health endpoint, tests, CI, Docker Compose, final demo.

**P1 (only if P0 is stable):** richer analytics, more tools, deeper retrieval tuning, WebSocket polish, UI refinement, elaborate AI metrics, more failure-injection cases.

**Explicitly out of scope for six days:** message queues, event buses, Kubernetes, multi-region deployment, hosted vector infrastructure, unnecessary microservices, custom rate-limiting, real enterprise integrations, autonomous privileged production changes.

---

## 17. Risk Register

| Risk | Mitigation |
|---|---|
| Contract drift | freeze schemas Day 1, shared contract doc, automated contract test, CI gate |
| AI hallucination | RAG, diagnostic tools, structured outputs, deterministic escalation, explicit uncertainty behavior |
| Prompt injection | pre-check, policy prompt, tool allowlist, authorization, object-level access control, security tests |
| Unauthorized data access | server-side identity, RBAC, query scoping, object-level authorization, security tests |
| Duplicate tickets | idempotency key (retry safety) **+** semantic similarity (related-incident detection) — two different problems, both handled |
| RAG too weak | small curated corpus, realistic synthetic tickets, metadata, evaluation scenarios, retrieval tuning |
| Frontend becomes a late blocker | force the vertical slice by end of Day 2; functional before polished |
| Live LLM failure during demo | fallback run-through, deterministic mock tools, seeded data, verified demo environment |
| Team silos | daily standup, swap-in sessions, cross-lane PR review |

---

## 18. Acceptance Criteria Traceability (AC-01 → AC-12)

| AC | Requirement | Implementation | Test | Owner |
|---|---|---|---|---|
| 01 | Issue intake | Portal + conversation API | E2E | M2/M4 |
| 02 | Clarification | LangGraph clarify node | AI/E2E | M1 |
| 03 | Classification | Structured output | Unit/AI eval | M1 |
| 04 | Diagnostic | Tool Gateway | Integration/E2E | M1/M2 |
| 05 | Simple resolution | Resolution workflow | AI/E2E | M1 |
| 06 | Ticket creation | Ticket API | API/contract | M2 |
| 07 | Duplicate detection | pgvector | AI/integration | M1 |
| 08 | Escalation | Policy layer | AI/security | M1/M3 |
| 09 | Handover | Conversation ownership | E2E | M2 |
| 10 | Security | JWT/RBAC/object auth/tool auth | Security | M2/M3 |
| 11 | Automated quality | CI test suites | CI | M3/M4 |
| 12 | Observability | trace IDs/logs/health | Integration | M4 |

This matrix is the project's primary delivery checklist — treat it as more authoritative than any prose description of progress.

---

## 19. Definition of Done (gate for Day 6 freeze)

**Functional:** intake, clarification, classification, priority, diagnostics, simple resolution, confirmation/rejection, ticket creation, duplicate detection, escalation, handover, dashboard — all working.
**Security:** JWT/session auth, all 5 roles, ticket isolation, server-side RBAC, object-level auth, tool auth, injection tests passing, audit records present.
**AI quality:** structured outputs validated, RAG retrieves evidence, tools used instead of guessing, uncertainty stated, escalation deterministic, AI eval scenarios run automatically.
**Reliability/ops:** Compose works, CI works, health/readiness work, trace IDs propagate, structured logs exist, controlled failure is diagnosable, runbook exists.
**Evidence:** AC-01→12 mapped, automated test report, security evidence, architecture doc, API/tool contracts, synthetic data, deployment artifacts, rehearsed demo.

---

## 20. Architecture Defense — Condensed Q&A

- **Modular monolith over microservices?** Six days doesn't afford distributed-systems overhead; module boundaries keep extraction credible later.
- **PostgreSQL?** Dominant workload is transactional (tickets, RBAC, audit, conversations).
- **pgvector over a dedicated vector DB?** Semantic retrieval without operating a second database, at a KB size where pgvector's ceiling is nowhere close.
- **Not Neo4j?** No dominant multi-hop graph-traversal problem in this scope.
- **LangGraph?** Makes the AI workflow explicit, testable, and interruptible for human takeover.
- **LangChain?** Selectively, for model/tool/structured-output/retrieval integration — never core business logic.
- **Why not let the LLM decide everything?** Authorization, escalation, and privileged actions are safety-sensitive; deterministic controls sit outside the model.
- **Why RAG?** BRD requires grounded troubleshooting and prohibits invented state/fixes.
- **Why mock integrations?** Real enterprise system changes are explicitly out of scope; mocks demonstrate realism without production risk.
- **Why server-side RBAC?** UI restrictions are not security boundaries.
- **Why idempotency keys?** Retries (AI or network) must not create duplicate tickets — a distinct problem from semantic duplicate detection.

---

## 21. What This Blueprint Adds Over the Source Plan

- Consolidates 37 sections into one execution-ready reference organized around **decide → build → verify → ship**, so it can stay open during the sprint instead of being searched section-by-section.
- Makes the Postgres/pgvector schema and the ticket state machine sit next to each other, since they're the two things every module (backend, AI orchestrator, dashboard) touches daily.
- Pulls the deterministic escalation policy and the tool authorization matrix into direct view next to the security principles they implement, since "the LLM is not the security boundary" is only real if engineers can see the code that enforces it.
- Keeps the 6-day plan reduced to exit criteria only — the day-by-day task lists live in the source plan; this blueprint is the checkpoint sheet, not the task tracker.
