# AI L1 IT Helpdesk

An automated IT helpdesk system that leverages LLMs to triage, diagnose, and resolve employee IT issues. Built with an event-driven agentic architecture using LangGraph, it autonomously handles common problems, intelligently retrieves semantic context, and deterministically escalates complex issues to human engineers.

## 🚀 Features

- **Automated Intake & Triage (User Story 1):** Chatbot interface where employees report issues. AI autonomously clarifies symptoms, classifies the issue, and invokes server-side diagnostic tools securely via a Tool Gateway.
- **Human Handover & Escalation (User Story 2):** Deterministic policy engine that halts AI execution and escalates tickets to an L2 Engineer Dashboard based on severity or diagnostic failure. Supports seamless human takeover.
- **Knowledge Retrieval & Duplicate Detection (User Story 3):** RAG (Retrieval-Augmented Generation) pipeline using PostgreSQL + `pgvector`. Retrieves semantic KB articles and historical duplicate incidents to provide the AI with grounded evidentiary context, strictly enforcing object-level authorization (tenant/department isolation).

## 🏗️ Architecture

- **Frontend:** React, TypeScript, Vite, React Router
- **Backend:** Python, FastAPI, SQLAlchemy, Alembic
- **AI/Workflow:** LangGraph, LangChain, OpenAI (`gpt-4` / `ada-002` embeddings)
- **Database:** PostgreSQL with `pgvector`

## 📋 Prerequisites

- [Docker & Docker Compose](https://docs.docker.com/compose/)
- [Node.js 18+](https://nodejs.org/) (for local frontend development)
- [Python 3.10+](https://www.python.org/) (for local backend development)
- An OpenAI API Key (or compatible LLM provider)

## 🛠️ Setup & Installation

### 1. Environment Configuration

Create a `.env` file in the root of the repository (or set these in your environment):

```env
# Required for AI and RAG functionality
OPENAI_API_KEY=sk-your-openai-api-key

# Defaults provided in docker-compose.yml, override if running locally
DATABASE_URL=postgresql://helpdesk_user:helpdesk_password@db:5432/helpdesk_db
SECRET_KEY=supersecretkey
```

### 2. Start the Application

The simplest way to run the entire stack (Database, Backend, Frontend) is via Docker Compose:

```bash
docker-compose up --build -d
```

- **Frontend:** `http://localhost:5173`
- **Backend API:** `http://localhost:8000`
- **API Docs (Swagger):** `http://localhost:8000/docs`

### 3. Initialize the Database

Once the containers are running, execute the Alembic migrations to build the schema:

```bash
docker-compose exec backend alembic upgrade head
```

## 📁 Project Structure

```
├── backend/
│   ├── alembic/            # Database migrations
│   ├── src/
│   │   ├── api/            # FastAPI routes (Conversations, Tickets, Diagnostics)
│   │   ├── auth/           # Security, JWT, and Role-Based Access Control
│   │   ├── core/           # DB configuration, Logging middleware
│   │   ├── models/         # SQLAlchemy ORM models (Ticket, User, KnowledgeDocument)
│   │   ├── services/       # Core business logic (Retrieval, Ticket handling)
│   │   ├── tools/          # Server-side tool execution gateway
│   │   └── workflow/       # LangGraph state machine and AI agent nodes
│   └── tests/              # Pytest suites
├── frontend/
│   ├── e2e/                # Playwright End-to-End tests
│   └── src/
│       ├── components/     # Reusable React components
│       └── portals/        # Employee Chat & Engineer Dashboard views
├── docs/                   # Postman collections and architecture specs
├── specs/                  # Project specifications and architecture blueprints
└── docker-compose.yml      # Container orchestration
```

## 🧪 Testing

### Backend Unit & Integration Tests (Pytest)

Requires a local Python environment.

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

pytest tests/
```

### Frontend End-to-End Tests (Playwright)

Requires a local Node environment. The application must be running locally to execute these tests.

```bash
cd frontend
npm install
npx playwright install
npx playwright test
```

## 🔒 Security & Authorization

- **Tool Gateway:** LLMs are never permitted to execute code directly. All requested diagnostic actions are routed through `ToolGateway.execute()`, which enforces server-side Role-Based Access Control before execution.
- **Object-Level Authorization:** Context and RAG queries are heavily strictly scoped to the authenticated principal's logical boundary (e.g., `department`) to prevent cross-tenant data leakage of historical tickets or internal KB articles.

## 📖 API Documentation

FastAPI automatically generates OpenAPI documentation. Once the backend is running, navigate to:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

Additionally, a Postman collection is available at `docs/api/postman_collection.json` for manual API testing.
