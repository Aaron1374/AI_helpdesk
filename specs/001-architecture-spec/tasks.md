# Task Breakdown: AI Helpdesk Architecture Specification

**Branch**: `001-architecture-spec` | **Date**: 2026-09-07 | **Plan**: [plan.md](./plan.md)

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create monolithic project directory structure (`backend/` and `frontend/`)
- [x] T002 Initialize Python 3.11+ backend project with FastAPI in `backend/`
- [x] T003 Initialize React + TypeScript + Vite project in `frontend/`
- [x] T004 Create `docker-compose.yml` for unified execution (FastAPI, React, PostgreSQL/pgvector)
- [x] T005 [P] Configure Python linting (ruff/black) in `backend/`
- [x] T006 [P] Configure TypeScript linting (eslint/prettier) in `frontend/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Configure PostgreSQL database connection and Alembic migrations in `backend/src/core/db.py`
- [x] T008 [P] Setup base testing frameworks (pytest in backend, vitest in frontend)
- [x] T009 Implement trace ID injection middleware and structured logging in `backend/src/core/logging.py`
- [x] T010 Implement JWT authentication and RBAC middleware in `backend/src/auth/security.py`
- [x] T011 Create base User SQLAlchemy model in `backend/src/models/user.py`
- [x] T012 Implement `/health` and `/ready` observability endpoints in `backend/src/api/health.py`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - E2E AI Conversation & Triage (Priority: P1)

**Goal**: Users can submit an issue, and the AI correctly routes it through the LangGraph workflow utilizing diagnostic tools via the Tool Gateway.

**Independent Test**: Can be fully tested by sending an API request and verifying the LangGraph state transitions and mocked tool invocations.

### Tests for User Story 1

- [x] T013 [P] [US1] Add automated test for Tool Gateway authorization (reject unauthorized LLM calls) in `backend/tests/tools/test_gateway.py`
- [x] T014 [P] [US1] Add automated test for prompt-injection defense in `backend/tests/workflow/test_injection.py`
- [x] T015 [P] [US1] Add automated test verifying AI does not invent system state without diagnostic evidence in `backend/tests/workflow/test_hallucination.py`

### Implementation for User Story 1

- [x] T016 [P] [US1] Create Conversation and Message models in `backend/src/models/chat.py`
- [x] T017 [US1] Implement Tool Gateway to enforce server-side tool authorization and reject unauthorized LLM-requested tool calls in `backend/src/tools/gateway.py`
- [x] T018 [P] [US1] Implement mock diagnostic endpoints (VPN, account, device) in `backend/src/api/diagnostics.py`
- [x] T019 [US1] Implement LangGraph Intake and Injection Pre-Check nodes in `backend/src/workflow/nodes/intake.py`
- [x] T020 [US1] Implement LangGraph Clarify and Classify nodes in `backend/src/workflow/nodes/triage.py`
- [x] T021 [US1] Implement LangGraph Diagnose, Resolve, and Verify nodes in `backend/src/workflow/nodes/resolution.py`
- [x] T022 [US1] Wire LangGraph state machine (Intake → Injection Pre-Check → Clarify → Classify → [Retrieve placeholder] → Diagnose → Resolve → Verify) in `backend/src/workflow/graph.py`
- [x] T023 [US1] Implement `/conversations` and `/conversations/{id}/messages` API endpoints in `backend/src/api/conversations.py`
- [x] T024 [US1] Implement base Employee Portal UI and chat component in `frontend/src/portals/EmployeePortal.tsx`
- [x] T025 [US1] Integrate chat UI with `/conversations/{id}/messages` endpoint

**Checkpoint**: User Story 1 functional (AI chat and triage works without escalation).

---

## Phase 4: User Story 2 - Human Takeover & Ticket State (Priority: P1)

**Goal**: When an issue escalates, the AI stops processing and an engineer takes over explicit ownership of the conversation and ticket state.

**Independent Test**: Simulate an escalation trigger and verify subsequent messages do not invoke the LLM.

### Tests for User Story 2

- [x] T026 [P] [US2] Add automated test for deterministic escalation rules in `backend/tests/workflow/test_escalation.py`
- [x] T027 [P] [US2] Add automated test ensuring human takeover prevents further AI processing in `backend/tests/workflow/test_takeover.py`

### Implementation for User Story 2

- [x] T028 [P] [US2] Create Ticket, TicketHistory, and AuditEvent models in `backend/src/models/ticket.py`
- [x] T029 [US2] Implement server-side ticket state machine and validated transitions (NEW → TRIAGED → IN_PROGRESS → RESOLVED → CLOSED/ESCALATED) in `backend/src/services/ticket_service.py`
- [x] T030 [US2] Implement deterministic Escalation Policy rules in `backend/src/workflow/escalation.py`
- [x] T031 [US2] Implement LangGraph Close/Escalate and Handover/Human nodes in `backend/src/workflow/nodes/handoff.py`
- [x] T032 [US2] Wire Escalate and Handover transitions into LangGraph with human takeover interrupt logic in `backend/src/workflow/graph.py`
- [x] T033 [P] [US2] Implement `/tickets` CRUD and `/tickets/{id}/confirm-resolution` endpoints in `backend/src/api/tickets.py`
- [x] T034 [US2] Implement `/conversations/{id}/takeover` endpoint in `backend/src/api/conversations.py`
- [x] T035 [US2] Build Engineer Dashboard UI for viewing escalated tickets in `frontend/src/portals/EngineerDashboard.tsx`
- [x] T036 [US2] Integrate Engineer Takeover functionality in dashboard UI

**Checkpoint**: User Story 2 functional (Escalation triggers human takeover logic, ticketing works).

---

## Phase 5: User Story 3 - Secure Retrieval & Duplicate Detection (Priority: P2)

**Goal**: The system accurately retrieves KB articles and similar past tickets using pgvector semantic search without leaking cross-tenant data.

**Independent Test**: Query the retrieval node with an authenticated context and verify only authorized documents are retrieved.

### Tests for User Story 3

- [x] T037 [P] [US3] Add automated test for RBAC/object-level authorization in retrieval in `backend/tests/workflow/test_retrieval.py`

### Implementation for User Story 3

- [x] T038 [P] [US3] Update database schema with `pgvector` extension and `KnowledgeDocument` model in `backend/src/models/knowledge.py`
- [x] T039 [P] [US3] Create pgvector migration in `backend/alembic/versions/`rag.py`
- [x] T040 [US3] Implement semantic similarity search functions with object-level auth filters in `backend/src/services/rag.py`
- [x] T041 [US3] Implement LangGraph Retrieve node in `backend/src/workflow/nodes/retrieve.py`
- [x] T042 [US3] Wire Retrieve node into the LangGraph state machine after Classify in `backend/src/workflow/graph.py`
- [x] T043 [US3] Expose relevant similar/duplicate incidents in the Engineer Dashboard UI to display retrieved duplicate incidents

**Checkpoint**: User Story 3 functional (RAG pipeline active).

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Documentation & E2E Validation for Polish Phase

- [x] T044 [P] Generate OpenAPI documentation and Export Postman collection in `docs/api/postman_collection.json`
- [x] T045 [P] Create Playwright E2E tests validating the core flows (intake, diagnosis, escalation) in `frontend/e2e/workflow.spec.ts`
- [x] T046 [P] Verify all append-only audit events consistently capture trace_id in `backend/tests/core/test_audit.py`
- [x] T047 Execute the quickstart.md validation scenarios end-to-end where the environment supports it

---

## Dependencies & Execution Order

### Phase Dependencies
- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3+)**: All depend on Foundational phase completion
  - US1 (Phase 3) and US2 (Phase 4) can theoretically proceed in parallel once Phase 2 is done, as they are both P1.
  - US3 (Phase 5) should follow US1 since it enhances the AI workflow.
- **Polish (Final Phase)**: Depends on all desired user stories being complete

### Parallel Opportunities
- Initialization of backend (T002) and frontend (T003) can be done simultaneously.
- Python and TypeScript linting setup (T005, T006).
- Base testing setups (T008).
- Data model creation can occur in parallel for independent domains (T016, T018).
- Endpoints (T033) and Models (T028) in US2 can be created parallel to UI elements (T035).

---

## Parallel Example: User Story 2

```bash
# Backend Developer: Create models and API endpoints
Task: "Create Ticket, TicketHistory, and AuditEvent models in backend/src/models/ticket.py"
Task: "Implement /tickets CRUD endpoints in backend/src/api/tickets.py"

# Frontend Developer: Create UI scaffolding
Task: "Build Engineer Dashboard UI for viewing escalated tickets in frontend/src/portals/EngineerDashboard.tsx"
```

## Implementation Strategy

### MVP First (User Story 1 & 2)
1. Complete Phase 1 & 2.
2. Complete Phase 3 (US1) to get the AI chatbot successfully answering queries.
3. Complete Phase 4 (US2) to handle safety boundaries and escalation.
4. **STOP and VALIDATE**: Core architecture is functional, secure, and meets MVP definition.
5. Proceed to Phase 5 (US3) for RAG enhancements.
