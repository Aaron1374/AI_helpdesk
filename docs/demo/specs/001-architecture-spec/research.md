# Phase 0: Research & Architecture Decisions

## Decision 1: Monolithic Deployment vs. Microservices
- **Decision**: Modular Monolith containing a FastAPI backend and a React frontend served via Docker Compose.
- **Rationale**: The Constitution and Blueprint explicitly forbid introducing infrastructure complexity (e.g., K8s, message queues) unless explicitly justified. The 6-day build scope and the nature of the application strictly benefit from monolithic execution.
- **Alternatives considered**: Distributed microservices (rejected: high overhead, violates Constitution).

## Decision 2: Duplicate Ticket Detection
- **Decision**: Automated `pgvector` RAG workflow node.
- **Rationale**: Surfacing related incidents automatically during the LangGraph flow removes LLM decision overhead and reduces the risk of the model "forgetting" to check for duplicates. Object-level authorization filters the vector results.
- **Alternatives considered**: Explicit LLM tool call for searching tickets (rejected: relies on LLM agency, which the project aims to minimize for security).

## Decision 3: State-changing Mock Actions
- **Decision**: Immediate deterministic escalation to human engineers.
- **Rationale**: Strict security boundary. The AI must never execute privileged production changes, even if simulated. All state-changing workflows force `conversation.owner = HUMAN` and status `ESCALATED`.
- **Alternatives considered**: Implementing mock APIs for the AI to simulate resolution (rejected: blurs the security boundary and violates the explicit escalation instruction).

## Decision 4: AI Workflow Orchestration
- **Decision**: `LangGraph` for state machine; `LangChain` strictly for model integration.
- **Rationale**: LangGraph allows explicit human-in-the-loop interruption and deterministic state transitions. LangChain handles the API boilerplate but is strictly kept out of business rules.
- **Alternatives considered**: Free-form agent loop (rejected: violates "deterministic escalation" and makes human-takeover hard).
