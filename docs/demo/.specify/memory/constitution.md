<!--
Sync Impact Report:
- Version change: Unversioned/Template → 1.0.0
- Added sections: Architecture & Simplicity, Technology Stack, AI Engineering & Abstraction, Security & Authorization, Grounded AI Behavior, Explicit State & Escalation, Observability & Audit, Quality & Testing, Traceability Principle
- Removed sections: N/A
- Follow-up TODOs: None
-->

# AI L1 IT Helpdesk Constitution

## Core Principles

### I. Architecture & Simplicity
Use a modular monolith unless the requirements explicitly justify decomposition. Prefer explicit, understandable code over unnecessary abstraction. Do not introduce infrastructure merely because it is common in enterprise systems. Any architectural change from the blueprint must be explicitly justified.

### II. Technology Stack
FastAPI owns the application/API boundary. React + TypeScript + Vite is the frontend. PostgreSQL is the system of record. `pgvector` is used within PostgreSQL for semantic retrieval and duplicate/related-incident detection.

### III. AI Engineering & Abstraction
LangGraph owns the explicit AI workflow/state machine. LangChain is used selectively for model integration, structured output, embeddings and integration boilerplate. Business rules must not be hidden inside LangChain abstractions.

### IV. Security & Authorization
The LLM is never the security boundary. Authentication and authorization are enforced server-side. Object-level authorization is mandatory. Tool authorization is enforced independently of LLM output. No autonomous privileged production actions are permitted.

### V. Grounded AI Behavior
The AI must not invent system state, diagnostic results, fixes, policies or permissions. Diagnostic tools must be used whenever real/mock system state is required. Enterprise integrations remain mocked/synthetic unless explicitly added later.

### VI. Explicit State & Escalation
Escalation policy must be deterministic and enforced outside the LLM. Human takeover must be represented explicitly through conversation ownership. Ticket state transitions must be enforced server-side.

### VII. Observability & Audit
Important operations must carry a `trace_id`. Audit events must capture security-sensitive and important business actions.

## Quality & Testing

Tests are required for business logic, APIs, security boundaries and critical AI behavior. Every acceptance criterion must ultimately have implementation evidence and test evidence.

## Traceability Principle

**BRD requirement → specification → implementation → test → evidence.**

Do not add product requirements that are not supported by the BRD. Optimize for correctness, security, maintainability, testability, observability, traceability to the BRD, clean AI engineering practices, and reasonable implementation simplicity. Do not optimize architecture or implementation decisions for a short-term deadline.

## Governance

This Constitution establishes permanent engineering principles for this project and supersedes any short-term optimizations. Any architectural changes must be explicitly justified against this constitution and the engineering blueprint.

**Version**: 1.0.0 | **Ratified**: 2026-09-07 | **Last Amended**: 2026-09-07
