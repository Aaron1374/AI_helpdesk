# Implementation Plan: AI Helpdesk Architecture Specification

**Branch**: `001-architecture-spec` | **Date**: 2026-09-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-architecture-spec/spec.md`

## Summary

Implement the foundational architecture for the AI L1 IT Helpdesk, establishing a modular monolith with a FastAPI backend, React/TS frontend, and a PostgreSQL database utilizing pgvector. The system enforces strict security boundaries where the LLM (orchestrated via LangGraph) has no authority over escalation, tool authorization, or access control.

## Technical Context

**Language/Version**: Python 3.11+, TypeScript 5+

**Primary Dependencies**: FastAPI, React, Vite, LangGraph, LangChain

**Storage**: PostgreSQL (with pgvector extension)

**Testing**: pytest (Python backend), Playwright (E2E), Jest/Vitest (Frontend)

**Target Platform**: Linux containers (Docker)

**Project Type**: Web Application (Backend API + React Frontend)

**Performance Goals**: Fast tool execution (mocked).

**Constraints**: Strict server-side RBAC; deterministic escalation; append-only audit events with `trace_id`.

**Scale/Scope**: Modular monolith handling employee IT issues, human takeover workflows, and synthetic diagnostic tools.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Modular Monolith**: Yes.
- **FastAPI / React / PostgreSQL / pgvector**: Yes.
- **LangGraph AI workflow**: Yes.
- **LLM is not the security boundary**: Yes (Tool Gateway).
- **Object-level authorization**: Yes.
- **Deterministic escalation**: Yes.
- **Trace IDs on important actions**: Yes.

## Project Structure

### Documentation (this feature)

```text
specs/001-architecture-spec/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
backend/
├── src/
│   ├── api/             # FastAPI routes (auth, tickets, dash, websocket)
│   ├── auth/            # JWT & RBAC
│   ├── core/            # Config, db, trace_id middleware
│   ├── models/          # SQLAlchemy schemas
│   ├── services/        # Ticket state machine, CRUD
│   ├── tools/           # Tool Gateway & mocks
│   └── workflow/        # LangGraph nodes and orchestrator
└── tests/               # Pytest suite

frontend/
├── src/
│   ├── components/      # Shared UI
│   ├── portals/         # Employee & Engineer views
│   └── api/             # API client
└── tests/               # Vitest / Playwright
```

**Structure Decision**: A dual-folder structure (`backend/` and `frontend/`) representing the modular monolith. They will be containerized via a single Docker Compose setup, satisfying the blueprint's "modular monolith" constraint while keeping React and Python dependencies cleanly separated.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

*(No violations. Structure strictly adheres to the Constitution.)*
