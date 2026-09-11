# AI L1 IT Helpdesk

An automated, AI-powered internal IT support platform that handles first-line (L1) employee issues through a conversational assistant. It uses a Retrieval-Augmented Generation (RAG) pipeline to ground every response in a curated Knowledge Base, runs mock diagnostic tools, and deterministically escalates complex or sensitive issues to human engineers — all without inventing information.

---

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [How It Works (Non-Technical Overview)](#how-it-works-non-technical-overview)
- [Architecture](#architecture)
- [Technology Stack](#technology-stack)
- [The AI Workflow (LangGraph Pipeline)](#the-ai-workflow-langgraph-pipeline)
- [Key Backend Components](#key-backend-components)
- [Frontend Portals](#frontend-portals)
- [Database Schema Overview](#database-schema-overview)
- [Security & Authorization](#security--authorization)
- [Quick Start](#quick-start)
- [Default Login Accounts](#default-login-accounts)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Configuration Reference](#configuration-reference)

---

## What This Project Does

Imagine you are an employee at a company and your VPN stops working. Instead of waiting in a queue for an IT engineer, you open a chat portal and type: *"My VPN stopped working after the latest Windows update."*

Here is what happens behind the scenes:

1. **The AI reads your message** and checks it for prompt-injection attacks (security).
2. **It sanitizes your input** — removing any template injection patterns or SQL fragments.
3. **It classifies the issue** into a category like "Network", "Hardware", "Access", etc.
4. **It searches the Knowledge Base** — a curated library of 29 troubleshooting articles — using vector similarity search to find the most relevant article.
5. **If a match is found (≥ 72% similarity)**, the AI generates a step-by-step troubleshooting guide using *only* the retrieved article as evidence. It never makes things up.
6. **If the issue involves VPN or a device**, it automatically runs a mock diagnostic tool (`vpn_check` or `device_check`) to gather additional evidence.
7. **If the AI is not confident enough**, or the issue is too complex (security incident, hardware failure, datacenter outage), it **creates a support ticket and escalates** the conversation to a human L1 engineer.
8. **The engineer sees the full chat transcript**, the diagnostic tool results, the retrieved KB articles, and the similarity scores — so the employee never has to repeat themselves.

---

## How It Works (Non-Technical Overview)

```
Employee types a message
        │
        ▼
┌───────────────────────┐
│  Security Check       │ ◄── Is this a prompt injection attack?
│  (injection_pre_check)│     If yes → block and escalate
└───────────┬───────────┘
            │ Safe
            ▼
┌───────────────────────┐
│  Preprocess & Sanitize│ ◄── Is this even an IT question?
│  (preprocess)         │     If not → politely reject
└───────────┬───────────┘
            │ IT-related
            ▼
┌───────────────────────┐
│  Classify the Issue   │ ◄── Network? Hardware? Access? Email?
│  (classify)           │     Security? Software? Application?
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  Search Knowledge Base│ ◄── pgvector cosine similarity search
│  (retrieve)           │     Returns top articles + scores
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  Run Diagnostic Tools │ ◄── vpn_check, device_check (mock)
│  (diagnose)           │     Results become "evidence"
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐     Score ≥ 0.72?
│  Resolve or Escalate  │────────────────────┐
│  (resolve)            │                    │
└───────────┬───────────┘                    │
            │ Yes                            │ No
            ▼                                ▼
┌───────────────────┐           ┌────────────────────┐
│  AI gives answer  │           │  Create ticket and  │
│  grounded in KB   │           │  escalate to human  │
│  (verify → END)   │           │  engineer (handoff) │
└───────────────────┘           └────────────────────┘
```

---

## Architecture

The application follows a modern, containerized full-stack architecture with clear separation of concerns.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Docker Compose                           │
│                                                                 │
│  ┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   Frontend    │  │     Backend      │  │    Database       │  │
│  │              │  │                  │  │                  │  │
│  │  React + TS  │──│  FastAPI (Python) │──│  PostgreSQL      │  │
│  │  Vite        │  │  LangGraph       │  │  + pgvector      │  │
│  │  Port: 5173  │  │  LangChain       │  │  Port: 5432      │  │
│  │              │  │  Port: 8001      │  │                  │  │
│  └──────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                 │
│  ┌──────────────┐                                               │
│  │   Adminer     │ ◄── Web-based database viewer                │
│  │   Port: 8080  │                                              │
│  └──────────────┘                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

### Why Each Technology Was Chosen

| Layer | Technology | Why It's Used |
|:------|:-----------|:--------------|
| **Frontend** | React 18 + TypeScript | Industry-standard for building interactive UIs with type safety. |
| **Frontend Build** | Vite | Blazing-fast development server with hot-reload, much faster than Webpack. |
| **Frontend Routing** | React Router v6 | Handles navigation between the Employee Portal and Engineer Dashboard without full page reloads. |
| **Markdown Rendering** | react-markdown + remark-gfm | Renders the AI's responses as formatted markdown (bold, lists, code blocks) instead of plain text. |
| **Backend Framework** | FastAPI (Python) | High-performance async Python web framework with automatic OpenAPI docs generation. |
| **ORM** | SQLAlchemy 2.0 (Async) | Maps Python classes to database tables, handles queries safely, and supports async operations. |
| **Database Migrations** | Alembic | Version-controls the database schema so tables can be created, modified, and tracked in Git. |
| **Database** | PostgreSQL | Enterprise-grade relational database for storing users, tickets, conversations, and messages. |
| **Vector Search** | pgvector | PostgreSQL extension that enables storing and querying high-dimensional vectors directly in the database — used for semantic similarity search in the RAG pipeline. |
| **AI Orchestration** | LangGraph | State-machine framework for building multi-step AI agent workflows with conditional branching, tool use, and human-in-the-loop handoffs. |
| **AI Abstractions** | LangChain | Provides a unified interface to multiple LLM providers (OpenAI, Gemini, xAI) and embedding models, so switching providers requires only a config change. |
| **LLM Providers** | OpenAI / Google Gemini / xAI | The actual large language models that power the AI's ability to understand issues, classify them, and generate responses. |
| **Authentication** | JWT (JSON Web Tokens) | Stateless authentication — the server issues a signed token on login, and the frontend includes it in every request. No session storage needed. |
| **Password Hashing** | bcrypt via Passlib | Industry-standard one-way hashing so passwords are never stored in plain text. |
| **Containerization** | Docker + Docker Compose | Packages the entire stack (DB, Backend, Frontend) into reproducible containers that work identically on any machine. |
| **Database Viewer** | Adminer | Lightweight web UI for inspecting and querying the database without installing desktop tools. |

---

## The AI Workflow (LangGraph Pipeline)

The AI brain is a **state machine** built with LangGraph. Each message from the employee flows through a series of **nodes** (processing steps), with **conditional edges** that route the conversation based on what happens at each step.

### Nodes (Processing Steps)

| Node | File | What It Does |
|:-----|:-----|:-------------|
| `intake` | `nodes/intake.py` | Entry point. Captures the raw user input and passes it forward. |
| `injection_pre_check` | `nodes/intake.py` | **Security gate.** Uses the LLM to classify the message as `SAFE` or `INJECTION`. If the LLM is unavailable, falls back to pattern-matching against known injection strings (e.g., "ignore all previous instructions"). Malicious messages are blocked immediately. |
| `preprocess` | `nodes/triage.py` | Sanitizes the input (strips template injections, SQL fragments, truncates to 512 tokens). Checks if the message is a greeting (asks for clarification) or not IT-related (rejects politely). |
| `classify` | `nodes/triage.py` | Uses the LLM to classify the issue into exactly one category: `Access`, `Network`, `Hardware`, `Software`, `Email`, `Security`, or `Application`. Falls back to `general_support` if the LLM fails. |
| `retrieve` | `nodes/retrieval.py` | Searches the Knowledge Base and historical tickets using pgvector cosine similarity. Returns the top matching documents and a **similarity score**. Results are scoped to the user's department. |
| `diagnose` | `nodes/resolution.py` | Runs mock diagnostic tools (`vpn_check`, `device_check`) through the `ToolGateway` based on query keywords. Also uses LLM tool-calling to let the AI decide which tools to invoke. |
| `resolve` | `nodes/resolution.py` | **The decision engine.** If the retrieval score is ≥ 0.72, generates a response using *only* the retrieved evidence. Runs a grounding check to verify the response actually references the KB. If grounding fails → escalate. If score < 0.72 → escalate. |
| `verify` | `nodes/resolution.py` | Final confirmation step. Marks the conversation status. |
| `escalate` / `handoff` | `nodes/handoff.py` | Creates a handoff summary with the query, evidence count, and retrieval score. Ensures the employee receives a friendly message informing them a ticket has been created. |
| `human` | `nodes/handoff.py` | Terminal node. Sets the status to `human_takeover`, signaling that a human engineer has taken over. |

### Conditional Routing

| After Node | Condition | Routes To |
|:-----------|:----------|:----------|
| `intake` | Human already took over? | → `human` (skip AI entirely) |
| `injection_pre_check` | Escalation policy triggered? | → `escalate` |
| `preprocess` | Needs clarification or out of scope? | → `END` (respond and wait) |
| `diagnose` | Escalation policy triggered? | → `escalate` |
| `resolve` | Low confidence or grounding failure? | → `escalate` |

### Escalation Policy

The `EscalationPolicy` class (`escalation.py`) defines when the AI must stop and hand off to a human:

- The AI explicitly flags `escalate = True` or `needs_handoff = True`
- The issue category is one of: `security_incident`, `hardware_failure`, `datacenter_outage`
- Two or more diagnostic tool errors occurred during the conversation

### Guardrails (`utils/guardrails.py`)

| Function | Purpose |
|:---------|:--------|
| `sanitize_input()` | Strips `{{ }}` template injections, SQL `--` comments, and truncates to 512 tokens. |
| `is_it_support_query()` | Two-layer filter: LLM-based triage gatekeeper + keyword heuristic fallback. Rejects non-IT queries like "what colour is my laptop" or "order food". |
| `is_response_from_knowledge_base()` | Post-generation grounding check. Verifies the AI's answer references actual KB document titles, content keywords, or tool results. Rejects fabricated answers. |
| `select_mock_tool()` | Keyword matcher that decides whether to run `vpn_check` or `device_check` based on the query. |

### Key Constants (`constants.py`)

| Constant | Default | Purpose |
|:---------|:--------|:--------|
| `SIMILARITY_THRESHOLD` | `0.72` | Minimum cosine similarity score required to trust a KB match. Below this → escalate. |
| `LLM_TEMPERATURE` | `0.0` | Forces deterministic (non-random) LLM outputs. |
| `LLM_SEED` | `42` | Fixed seed for reproducible token sampling. |

---

## Key Backend Components

### API Routes (`src/api/`)

| Route Module | Prefix | Purpose |
|:-------------|:-------|:--------|
| `auth.py` | `/auth` | Login endpoint. Issues JWT tokens. Auto-provisions development accounts on first login. |
| `conversations.py` | `/conversations` | Create conversations, send messages, trigger the LangGraph workflow, takeover by engineers. |
| `tickets.py` | `/tickets` | CRUD for support tickets. Lists, filters, and updates ticket status. |
| `diagnostics.py` | `/diagnostics` | Mock diagnostic tool endpoints. |
| `health.py` | `/health` | Health check endpoint for observability. |

### Services (`src/services/`)

| Service | Purpose |
|:--------|:--------|
| `RetrievalService` | Performs vector similarity search against both `knowledge_documents` and `tickets` tables. Scopes results by department. Returns documents and a max similarity score. |
| `TicketService` | Creates, updates, and manages the lifecycle of support tickets. |

### Tool Gateway (`src/tools/gateway.py`)

The `ToolGateway` is a security layer between the AI and any server-side actions. The LLM is **never** allowed to execute code directly. Instead:

1. The AI requests a tool call (e.g., `vpn_check`)
2. The gateway checks if the tool is in the `allowed_tools` set
3. If unauthorized → HTTP 403 and the attempt is logged
4. If authorized → the mock tool executes and returns results

Currently allowed tools: `vpn_check`, `device_check`.

---

## Frontend Portals

### Employee Portal (`EmployeePortal.tsx`)

The main chat interface where employees interact with the AI assistant. Features:
- Real-time chat with markdown-rendered AI responses
- Message history persistence across page refreshes
- Login/authentication flow
- Visual distinction between user messages, AI responses, and system messages

### Engineer Dashboard (`EngineerDashboard.tsx`)

The L1 support engineer's view. Features:
- Queue of escalated tickets requiring human attention
- Full conversation transcript view (user messages + AI diagnostic context)
- Ability to "take over" a conversation from the AI
- Ticket status management (IN_PROGRESS, RESOLVED, CLOSED)

---

## Database Schema Overview

The application uses 7 PostgreSQL tables:

| Table | Purpose |
|:------|:--------|
| `users` | All user accounts (employees, L1/L2 engineers, admins). Role-based access control. |
| `conversations` | Chat threads. Tracks who owns the conversation (`AI` or `HUMAN`). |
| `messages` | Individual messages within conversations. Sender can be `USER`, `AI`, or `SYSTEM`. |
| `tickets` | Structured IT issues with status lifecycle (`NEW` → `TRIAGED` → `IN_PROGRESS` → `RESOLVED` → `CLOSED` or `ESCALATED`). |
| `ticket_history` | Audit trail of every status change on a ticket (who changed it, when, from what to what). |
| `audit_events` | Security log for privileged actions (escalations, tool calls, takeovers). |
| `knowledge_documents` | The RAG Knowledge Base. 29 curated IT troubleshooting articles with vector embeddings for semantic search. |

> For the complete schema with every column, type, and constraint, see [schema_documentation.md](schema_documentation.md).

---

## Security & Authorization

| Layer | Mechanism | Details |
|:------|:----------|:--------|
| **Authentication** | JWT tokens | Issued on login via `/auth/login`. Expire after 30 minutes. Signed with `SECRET_KEY`. |
| **Role-Based Access** | `RoleChecker` class | Server-side enforcement. Routes can restrict access to specific roles (e.g., only `l1` and `admin` can view escalated tickets). |
| **Prompt Injection Defense** | Two-layer check | LLM-based classifier + deterministic pattern matching. Blocks attempts to override system instructions, reveal prompts, or bypass restrictions. |
| **Input Sanitization** | `sanitize_input()` | Strips template injections (`{{ }}`), SQL injection patterns (`--`, `;`), and enforces max input length. |
| **Tool Execution** | `ToolGateway` | AI cannot execute tools directly. All calls go through a gateway that checks authorization and logs attempts. |
| **Data Isolation** | Department scoping | RAG queries and ticket retrieval are filtered by the user's department to prevent cross-tenant data leakage. |
| **Grounding Verification** | `is_response_from_knowledge_base()` | Post-generation check that the AI's response actually references retrieved evidence. Prevents hallucinated answers from reaching users. |
| **Out-of-Scope Rejection** | `is_it_support_query()` | Prevents the AI from engaging with non-IT questions (trivia, personal requests, etc.). |

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Aaron1374/AI_helpdesk.git
cd AI_helpdesk

# 2. Create .env file with your API key (see setup.md for full details)
#    At minimum, you need: LLM_PROVIDER, EMBEDDING_PROVIDER, and an API key

# 3. Build and start all containers
docker compose up --build -d

# 4. Create database tables
docker compose exec backend alembic upgrade head

# 5. Seed the Knowledge Base (29 IT troubleshooting articles)
docker compose exec backend python seed_kb.py

# 6. Open the app
#    Frontend:        http://localhost:5173
#    API Docs:        http://localhost:8001/docs
#    Database Viewer: http://localhost:8080
```

> For the complete step-by-step guide including environment configuration, provider setup, and troubleshooting, see **[setup.md](setup.md)**.

---

## Default Login Accounts

These accounts are auto-created on first login. No manual setup required.

| Email | Password | Role | Access |
|:------|:---------|:-----|:-------|
| `employee@example.com` | `dev-password` | Employee | Chat with the AI assistant |
| `engineer@example.com` | `dev-password` | L1 Engineer | View escalated tickets, take over conversations |
| `l1@example.com` | `dev-password` | L1 Engineer | Same as above |
| `admin@example.com` | `dev-password` | Admin | Full system access |

---

## API Documentation

FastAPI automatically generates interactive API documentation:

| Format | URL | Description |
|:-------|:----|:------------|
| Swagger UI | [http://localhost:8001/docs](http://localhost:8001/docs) | Interactive — test API calls directly from the browser |
| ReDoc | [http://localhost:8001/redoc](http://localhost:8001/redoc) | Read-only — cleaner layout for reading |

### Key API Endpoints

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `POST` | `/auth/login` | Authenticate and receive a JWT token |
| `POST` | `/conversations/` | Create a new conversation |
| `POST` | `/conversations/{id}/messages` | Send a message (triggers the AI workflow) |
| `POST` | `/conversations/{id}/takeover` | Engineer takes over a conversation from the AI |
| `GET` | `/conversations/{id}/messages` | Retrieve full message history |
| `GET` | `/tickets/` | List tickets (filtered by role/permissions) |
| `PATCH` | `/tickets/{id}` | Update ticket status |
| `GET` | `/health/` | Service health check |

---

## Project Structure

```
helpdesk/
│
├── backend/                          # Python FastAPI Backend
│   ├── alembic/                      # Database migration scripts
│   │   └── versions/                 # Individual migration files
│   ├── src/
│   │   ├── api/                      # REST API route handlers
│   │   │   ├── auth.py               #   Login, JWT token generation
│   │   │   ├── conversations.py      #   Chat CRUD, message sending, AI workflow trigger
│   │   │   ├── tickets.py            #   Ticket CRUD, status updates
│   │   │   ├── diagnostics.py        #   Mock diagnostic endpoints
│   │   │   └── health.py             #   Health check
│   │   ├── auth/
│   │   │   └── security.py           # JWT creation/validation, password hashing, role checker
│   │   ├── core/
│   │   │   ├── db.py                 # Database engine & session factory
│   │   │   ├── llm.py               # LLM & embedding model factory (multi-provider)
│   │   │   └── logging.py           # Trace ID middleware for observability
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── user.py              #   Users table + UserRole enum
│   │   │   ├── chat.py              #   Conversations + Messages tables
│   │   │   ├── ticket.py            #   Tickets + TicketHistory + AuditEvents tables
│   │   │   └── knowledge.py         #   Knowledge Base (RAG) documents table
│   │   ├── services/
│   │   │   ├── retrieval_service.py  # pgvector similarity search (KB + tickets)
│   │   │   └── ticket_service.py     # Ticket lifecycle management
│   │   ├── tools/
│   │   │   └── gateway.py           # Secure tool execution gateway
│   │   └── workflow/                 # LangGraph AI Agent
│   │       ├── graph.py             #   State machine definition & wiring
│   │       ├── state.py             #   AgentState TypedDict
│   │       ├── escalation.py        #   EscalationPolicy rules
│   │       ├── constants.py         #   Thresholds (similarity, temperature, seed)
│   │       ├── nodes/
│   │       │   ├── intake.py        #   Intake + injection pre-check
│   │       │   ├── triage.py        #   Preprocess + classify
│   │       │   ├── retrieval.py     #   KB vector search
│   │       │   ├── resolution.py    #   Diagnose + resolve + verify
│   │       │   └── handoff.py       #   Escalate + human takeover
│   │       └── utils/
│   │           └── guardrails.py    #   Input sanitization, grounding checks, scope filtering
│   ├── tests/                        # Pytest test suites
│   ├── kb_articles.json              # 29 curated KB articles (RAG source data)
│   ├── seed_kb.py                    # Script to embed and load KB into the database
│   ├── requirements.txt              # Python dependencies
│   └── Dockerfile                    # Backend container definition
│
├── frontend/                         # React + TypeScript Frontend
│   ├── src/
│   │   ├── App.tsx                   # Root component, routing, auth state
│   │   ├── main.tsx                  # React entry point
│   │   ├── styles.css                # Global styles
│   │   ├── api/
│   │   │   ├── client.ts            #   HTTP client (fetch wrapper with JWT)
│   │   │   └── types.ts             #   TypeScript interfaces for API data
│   │   ├── auth/                     # Authentication context & hooks
│   │   ├── components/
│   │   │   └── MarkdownRenderer.tsx  #   Renders AI responses as formatted markdown
│   │   └── portals/
│   │       ├── EmployeePortal.tsx    #   Employee chat interface
│   │       └── EngineerDashboard.tsx #   L1 engineer ticket queue & takeover view
│   ├── package.json                  # Node.js dependencies
│   └── Dockerfile                    # Frontend container definition
│
├── docker-compose.yml                # Container orchestration (all 4 services)
├── .env                              # Environment variables (git-ignored)
├── setup.md                          # Detailed setup & installation guide
├── schema_documentation.md           # Complete database schema reference
└── AI_L1_IT_Helpdesk_BRD.md          # Business Requirements Document
```

---

## Testing

### Backend Tests (pytest)

```bash
# Via Docker
docker compose exec backend pytest tests/ -v

# Locally (with virtual environment activated)
cd backend
pytest tests/ -v
```

Test suites cover:
- RAG pipeline behavior (retrieval scores, grounding checks)
- Hallucination detection (AI must not fabricate answers)
- Workflow state transitions
- Tool gateway authorization

### Frontend E2E Tests (Playwright)

```bash
cd frontend
npx playwright install    # First time only
npx playwright test
```

---

## Configuration Reference

All configuration is done through the `.env` file in the project root. See [setup.md](setup.md) for complete details.

### Supported AI Providers

| Provider | `LLM_PROVIDER` | Recommended Model | Embedding Model | Embedding Dimensions |
|:---------|:----------------|:-------------------|:-----------------|:---------------------|
| Google Gemini | `gemini` | `gemini-2.5-flash` | `gemini-embedding-2` | 3072 |
| OpenAI | `openai` | `gpt-4o-mini` | `text-embedding-3-small` | 1536 |
| xAI (Grok) | `xai` | `grok-3-mini` | Uses OpenAI embeddings | 1536 |

---

## License

This project is a capstone training exercise for the AI Engineer New-Joiner Program. See [AI_L1_IT_Helpdesk_BRD.md](AI_L1_IT_Helpdesk_BRD.md) for the full business requirements document.
