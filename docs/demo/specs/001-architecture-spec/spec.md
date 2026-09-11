# Feature Specification: AI Helpdesk Architecture Specification

**Feature Branch**: `001-architecture-spec`

**Created**: 2026-09-07

**Status**: Draft

**Input**: User description: "Create the initial architecture/system design specification for the AI L1 IT Helpdesk. Read BRD, blueprint, constitution. Document agreed architecture without redesigning it, including system components, module boundaries, frontend/backend boundary, FastAPI, LangGraph AI workflow, LangChain usage, PostgreSQL + pgvector, RAG, Tool Gateway, ticket state machine, authentication/RBAC, human takeover, audit logging, observability, deployment structure. Clearly document responsibility and boundaries of each module. Do not implement code. Do not introduce new technologies or architectural alternatives. Flag genuine ambiguities instead of making assumptions."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - E2E AI Conversation & Triage (Priority: P1)

Users can submit an issue, and the AI correctly routes it through the LangGraph workflow, clarifying, retrieving context, and utilizing diagnostic tools.

**Why this priority**: Validates the core application boundary, FastAPI integration, LangGraph state machine, and Tool Gateway.

**Independent Test**: Can be fully tested by sending an API request and verifying the LangGraph state transitions and mocked tool invocations.

**Acceptance Scenarios**:

1. **Given** an authenticated employee submitting an issue, **When** the FastAPI backend processes it, **Then** it triggers the LangGraph workflow.
2. **Given** a LangGraph diagnosis step, **When** the AI attempts to use a mock tool, **Then** the Tool Gateway enforces authorization before executing.

---

### User Story 2 - Human Takeover & Ticket State (Priority: P1)

When an issue escalates, the AI stops processing and an engineer takes over explicit ownership of the conversation and ticket state.

**Why this priority**: Validates the strict server-side state machine and ownership model defined in the constitution and blueprint.

**Independent Test**: Can be fully tested by simulating an escalation trigger and verifying that subsequent messages do not invoke the LLM.

**Acceptance Scenarios**:

1. **Given** an AI conversation, **When** the deterministic escalation policy fires, **Then** the conversation ownership switches to HUMAN and the ticket state moves to ESCALATED.
2. **Given** a human-owned conversation, **When** a user replies, **Then** the AI does not intervene.

---

### User Story 3 - Secure Retrieval & Duplicate Detection (Priority: P2)

The system accurately retrieves knowledge base articles and similar past tickets using pgvector semantic search without leaking cross-tenant data.

**Why this priority**: Validates PostgreSQL/pgvector integration and object-level authorization for RAG.

**Independent Test**: Can be fully tested by querying the retrieval node with an authenticated context and verifying only authorized documents are embedded/returned.

**Acceptance Scenarios**:

1. **Given** a new ticket submission, **When** the RAG node executes, **Then** pgvector semantic search identifies likely related incidents.
2. **Given** a search for related incidents, **When** unauthorized tickets exist, **Then** object-level authorization prevents them from being retrieved.

## Requirements *(mandatory)*

### Functional Requirements

#### Module Boundaries and System Components
- **FR-001**: System MUST be structured as a modular monolith without unnecessary microservices.
- **FR-002**: System MUST use React + TypeScript + Vite for the Employee Portal and Engineer Dashboard.
- **FR-003**: System MUST use FastAPI to own the application/API boundary, authentication, and WebSocket/REST routing.
- **FR-004**: System MUST use PostgreSQL as the single system of record for tickets, conversations, audit logs, and users.
- **FR-005**: System MUST use `pgvector` within PostgreSQL for semantic retrieval and duplicate/related-incident detection.

#### AI & Workflow
- **FR-006**: System MUST use LangGraph to orchestrate the explicit AI workflow and state machine (Intake → Clarify → Classify → Retrieve → Diagnose → Resolve → Verify → Escalate).
- **FR-007**: System MUST use LangChain selectively for model integrations, structured outputs, and embeddings, without hiding business rules.
- **FR-008**: System MUST utilize a deterministic Escalation Policy outside of the LLM to trigger handovers for sensitive, unsupported, or low-confidence requests.

#### Security, Auth, & Audit
- **FR-009**: System MUST enforce server-side authentication and object-level authorization. The LLM is never the security boundary.
- **FR-010**: System MUST route all tool executions through a Tool Gateway that enforces independent authorization checks.
- **FR-011**: System MUST append a `trace_id` to all critical operations (request → AI decision → retrieval → tool call → ticket creation → audit event).
- **FR-012**: System MUST NOT allow the AI to invent system states, diagnostic results, fixes, policies, or permissions.
- **FR-013**: System MUST simulate diagnostic endpoints (e.g., VPN, application, device, account) and remain mocked/synthetic. No autonomous privileged production actions are permitted.

#### Ambiguities Flagged for Clarification
- **FR-014**: System MUST handle duplicate ticket detection via an automated pgvector RAG workflow node, surfacing related incidents automatically without requiring an explicit LLM tool call.
- **FR-015**: System MUST handle state-changing actions via immediate deterministic escalation. All privileged actions must strictly route to human intervention rather than simulating resolution in the Tool Gateway.

### Key Entities

- **User**: Represents employees and support engineers with RBAC roles.
- **Conversation**: The chat session state, explicitly owned by `AI` or `HUMAN`.
- **Ticket**: The structured issue tracker with server-enforced state transitions (NEW → TRIAGED → IN_PROGRESS → RESOLVED → CLOSED → ESCALATED).
- **Message**: Individual conversation entries carrying trace IDs.
- **AuditEvent**: Append-only log of security-sensitive operations tied to a `trace_id`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tool invocations execute through the server-side Tool Gateway authorization check before running.
- **SC-002**: 100% of escalated tickets result in the conversation ownership flag transferring to HUMAN, preventing further AI generation.
- **SC-003**: 100% of critical system interactions log a traceable, end-to-end `trace_id` in the database.
- **SC-004**: System deployment consists of a unified monolithic backend container and associated database/frontend containers, with 0 distributed microservices.

## Assumptions

- We assume deployment structure uses Docker and Docker Compose for a contained modular monolith.
- We assume all enterprise integrations remain strictly mocked and synthetic for this phase.
- We assume the LLM provider will be configurable via standard LangChain integration patterns.
