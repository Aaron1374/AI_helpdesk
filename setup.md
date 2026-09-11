# AI L1 IT Helpdesk — Complete Setup Guide

> **Last Updated:** September 2026
>
> This guide walks you through every step required to set up and run the AI L1 IT Helpdesk from a fresh clone. It is written for Windows but includes macOS/Linux equivalents where commands differ.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [Configure Environment Variables](#3-configure-environment-variables)
4. [Start the Application (Docker)](#4-start-the-application-docker)
5. [Initialize the Database](#5-initialize-the-database)
6. [Seed the Knowledge Base](#6-seed-the-knowledge-base)
7. [Access the Application](#7-access-the-application)
8. [Default Login Accounts](#8-default-login-accounts)
9. [Switching AI Providers](#9-switching-ai-providers)
10. [Local Development Setup (Without Docker)](#10-local-development-setup-without-docker)
11. [Running Tests](#11-running-tests)
12. [Useful Commands Reference](#12-useful-commands-reference)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Prerequisites

Install the following **before** doing anything else. All items are required.

| Tool | Version | Purpose | Download |
|:-----|:--------|:--------|:---------|
| **Git** | Any recent | Clone the repository | [git-scm.com](https://git-scm.com/download/win) |
| **Docker Desktop** | 4.x+ | Runs PostgreSQL, Backend, Frontend, and Adminer in containers | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Python** | 3.10 – 3.11 | Required only for local development / running tests outside Docker | [python.org](https://www.python.org/downloads/) |
| **Node.js + npm** | 18 LTS | Required only for local frontend development / running tests outside Docker | [nodejs.org](https://nodejs.org/) |
| **VS Code** (recommended) | Any | Code editor | [code.visualstudio.com](https://code.visualstudio.com/) |

> **⚠️ Windows Users:** When installing Python, check **"Add Python to PATH"** during installation. Without this, `python` commands will not work from the terminal.

### Verify Installation

Open a terminal (PowerShell on Windows) and run:

```bash
git --version        # e.g. git version 2.45.0
docker --version     # e.g. Docker version 27.x
docker compose version  # e.g. Docker Compose version v2.x
python --version     # e.g. Python 3.11.x
node --version       # e.g. v18.x
npm --version        # e.g. 10.x
```

Make sure **Docker Desktop is running** (look for the green whale icon in the system tray).

---

## 2. Clone the Repository

```bash
git clone https://github.com/Aaron1374/AI_helpdesk.git
cd AI_helpdesk
```

> If you already have the code, make sure you are on the latest version:
> ```bash
> git pull origin develop
> ```

---

## 3. Configure Environment Variables

The application requires a `.env` file in the **project root** (the `helpdesk/` folder) to configure AI providers, API keys, and authentication settings.

### Step 3.1 — Create the `.env` File

The `.env` file is git-ignored and will **not** exist after a fresh clone. Create it manually:

```bash
# Windows (PowerShell)
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

> If `.env.example` does not exist, create a blank file named `.env` in the project root.

### Step 3.2 — Choose Your AI Provider and Fill In the File

You only need to configure **one** AI provider. Pick the one you have an API key for.

#### Option A: Google Gemini (Recommended)

```env
# ── AI Provider ──────────────────────────────────────
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.5-flash
LLM_TEMPERATURE=0

# ── Embedding Model ─────────────────────────────────
EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini-embedding-2

# ── API Key ──────────────────────────────────────────
GOOGLE_API_KEY=your-google-api-key-here

# ── Application Settings ────────────────────────────
SECRET_KEY=change-me-to-a-random-string
DEV_USER_EMAIL=employee@example.com
DEV_USER_PASSWORD=dev-password
DEV_USER_ROLE=employee
```

Get your API key at: [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

#### Option B: OpenAI

```env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small

OPENAI_API_KEY=sk-your-openai-api-key-here

SECRET_KEY=change-me-to-a-random-string
DEV_USER_EMAIL=employee@example.com
DEV_USER_PASSWORD=dev-password
DEV_USER_ROLE=employee
```

Get your API key at: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

#### Option C: xAI (Grok)

```env
LLM_PROVIDER=xai
LLM_MODEL=grok-3-mini
LLM_TEMPERATURE=0

EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
OPENAI_API_KEY=your-openai-key-for-embeddings

XAI_API_KEY=your-xai-api-key-here
XAI_BASE_URL=https://api.x.ai/v1

SECRET_KEY=change-me-to-a-random-string
DEV_USER_EMAIL=employee@example.com
DEV_USER_PASSWORD=dev-password
DEV_USER_ROLE=employee
```

### Step 3.3 — Understanding Each Variable

| Variable | Required | Description |
|:---------|:---------|:------------|
| `LLM_PROVIDER` | ✅ | AI provider for the chat model. One of: `gemini`, `openai`, `xai`, `openai_compatible`, `ollama` |
| `LLM_MODEL` | ✅ | The specific model name (e.g., `gemini-2.5-flash`, `gpt-4o-mini`, `grok-3-mini`) |
| `LLM_TEMPERATURE` | ✅ | Controls randomness. Use `0` for deterministic outputs. |
| `EMBEDDING_PROVIDER` | ✅ | Provider for text embeddings. Same options as `LLM_PROVIDER`. |
| `EMBEDDING_MODEL` | ✅ | Embedding model name (e.g., `gemini-embedding-2`, `text-embedding-3-small`) |
| `GOOGLE_API_KEY` | If Gemini | Your Google AI Studio API key. |
| `OPENAI_API_KEY` | If OpenAI | Your OpenAI platform API key. |
| `XAI_API_KEY` | If xAI | Your xAI API key. |
| `SECRET_KEY` | ✅ | Random string used to sign JWT authentication tokens. |
| `DEV_USER_EMAIL` | ❌ | Email for the auto-created dev account (default: `employee@example.com`). |
| `DEV_USER_PASSWORD` | ❌ | Password for the dev account (default: `dev-password`). |
| `DEV_USER_ROLE` | ❌ | Role for the dev account (default: `employee`). |

> **🔴 Important:** The `.env` file is **not mounted** into Docker containers. Docker Compose reads it and passes values as environment variables. If you change `.env`, you must recreate the container:
> ```bash
> docker compose up -d backend
> ```
> A simple `docker compose restart` will **NOT** pick up `.env` changes.

---

## 4. Start the Application (Docker)

This is the recommended way to run the entire stack. Docker Compose will automatically build and start:
- **PostgreSQL + pgvector** (database)
- **FastAPI Backend** (Python API + AI agent)
- **React Frontend** (Vite dev server)
- **Adminer** (web-based database viewer)

### Step 4.1 — Build and Start All Containers

```bash
docker compose up --build -d
```

> **First run:** This will take **5–10 minutes** to download base images and install dependencies. Subsequent runs are fast.

### Step 4.2 — Verify Everything is Running

```bash
docker ps
```

You should see **4 containers** running:

| Container | Image | Port |
|:----------|:------|:-----|
| `helpdesk-frontend-1` | `helpdesk-frontend` | `5173` |
| `helpdesk-backend-1` | `helpdesk-backend` | `8001` |
| `helpdesk-db-1` | `ankane/pgvector:v0.5.1` | `5432` |
| `helpdesk-adminer-1` | `adminer` | `8080` |

### Step 4.3 — Check Logs (If Something Goes Wrong)

```bash
# View all container logs
docker compose logs

# View logs for a specific service
docker compose logs backend
docker compose logs frontend

# Follow logs in real time
docker compose logs -f backend
```

---

## 5. Initialize the Database

The database container starts empty. You need to run Alembic migrations to create all the required tables (`users`, `conversations`, `messages`, `tickets`, `knowledge_documents`, etc.).

```bash
docker compose exec backend alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> 20260907_baseline
INFO  [alembic.runtime.migration] Running upgrade 20260907_baseline -> 20260907_add_ticket_models
INFO  [alembic.runtime.migration] Running upgrade 20260907_add_ticket_models -> 20260907_add_knowledge
INFO  [alembic.runtime.migration] Running upgrade 20260907_add_knowledge -> 20260907_add_ticket_embeddings
```

> **Note on Gemini Embeddings:** If you are using Gemini as your embedding provider, the `knowledge_documents.embedding` column must be `Vector(3072)` instead of the default `Vector(1536)`. Check `backend/src/models/knowledge.py` and the migration file `backend/alembic/versions/20260907_add_knowledge.py` to ensure dimensions match your provider. If you need to change it after the fact:
> ```bash
> docker compose exec db psql -U helpdesk_user -d helpdesk_db \
>   -c "ALTER TABLE knowledge_documents ALTER COLUMN embedding TYPE vector(3072);"
> ```

---

## 6. Seed the Knowledge Base

The AI agent uses a **Retrieval-Augmented Generation (RAG)** pipeline. It searches a Knowledge Base of pre-written IT troubleshooting articles to find answers. You must populate this Knowledge Base before the AI can provide useful responses.

The articles are defined in `backend/kb_articles.json` (29 articles covering VPN issues, password resets, hardware problems, etc.).

```bash
docker compose exec backend python seed_kb.py
```

**Expected output:**
```
=======================================================
  KB Seeder — kb_articles.json
=======================================================

  Loaded 29 article(s) from kb_articles.json.
  Generating embeddings for 29 article(s)...
  Done. Each embedding has 3072 dimensions.
  [INSERT] 'VPN Connection Fails After Windows Update'
  [INSERT] 'Account Locked Out or Forgot Password'
  ...
  Seeding complete. 29 inserted, 0 updated.
```

### Seed Script Options

| Flag | Description |
|:-----|:------------|
| `--dry-run` | Preview what would be inserted without writing to the database. |
| `--reset` | Delete all existing KB documents before re-seeding. |
| `--file PATH` | Use a custom JSON file instead of the default `kb_articles.json`. |

> **Re-running is safe.** The script is idempotent — it matches articles by title and updates existing ones.

---

## 7. Access the Application

Once all containers are running, the database is migrated, and the KB is seeded, open your browser:

| Service | URL | Description |
|:--------|:----|:------------|
| **Employee Chat Portal** | [http://localhost:5173](http://localhost:5173) | Main frontend — chat with the AI assistant |
| **Backend API Docs** | [http://localhost:8001/docs](http://localhost:8001/docs) | Swagger UI — interactive API documentation |
| **Database Viewer** | [http://localhost:8080](http://localhost:8080) | Adminer — browse tables and run SQL queries |

### Adminer Login Credentials

When accessing the database viewer at `http://localhost:8080`:

| Field | Value |
|:------|:------|
| System | PostgreSQL |
| Server | `db` |
| Username | `helpdesk_user` |
| Password | `helpdesk_password` |
| Database | `helpdesk_db` |

---

## 8. Default Login Accounts

The application auto-provisions development accounts on first login. No manual user creation is needed.

| Email | Password | Role | Portal |
|:------|:---------|:-----|:-------|
| `employee@example.com` | `dev-password` | `employee` | Employee Chat Portal |
| `engineer@example.com` | `dev-password` | `l1` | Engineer Dashboard |
| `l1@example.com` | `dev-password` | `l1` | Engineer Dashboard |
| `admin@example.com` | `dev-password` | `admin` | Admin Access |

> These accounts are defined in `backend/src/api/auth.py` and are created in the database automatically the first time you log in with them. The `DEV_USER_*` variables in `.env` control the first account.

---

## 9. Switching AI Providers

To switch between providers (e.g., from Gemini to OpenAI), edit your `.env` file and recreate the backend container:

```bash
# 1. Edit .env with the new provider settings

# 2. Recreate the backend container to pick up changes
docker compose up -d backend
```

> ⚠️ **Embedding dimension mismatch:** Different providers output different vector sizes. If you switch embedding providers, you may need to:
> 1. Update `Vector(N)` in `backend/src/models/knowledge.py`
> 2. Alter the database column: `ALTER TABLE knowledge_documents ALTER COLUMN embedding TYPE vector(N);`
> 3. Re-run the seeder: `docker compose exec backend python seed_kb.py --reset`
>
> | Provider | Embedding Model | Dimensions |
> |:---------|:----------------|:-----------|
> | Gemini | `gemini-embedding-2` | 3072 |
> | OpenAI | `text-embedding-3-small` | 1536 |

---

## 10. Local Development Setup (Without Docker)

If you want to edit code with hot-reload, run tests natively, or debug outside Docker, follow these steps. **You still need Docker running for the PostgreSQL database.**

### Step 10.1 — Start Only the Database

```bash
docker compose down          # Stop everything
docker compose up -d db      # Start just PostgreSQL
```

### Step 10.2 — Set Up the Python Backend

```bash
cd backend

# Create a virtual environment
python -m venv venv

# Activate it
# Windows (PowerShell):
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

**Set the local database URL** (since you're connecting to `localhost` instead of Docker's internal `db` hostname):

```bash
# Windows (PowerShell)
$env:DATABASE_URL = "postgresql+asyncpg://helpdesk_user:helpdesk_password@localhost:5432/helpdesk_db"

# macOS / Linux
export DATABASE_URL="postgresql+asyncpg://helpdesk_user:helpdesk_password@localhost:5432/helpdesk_db"
```

**Run database migrations:**

```bash
alembic upgrade head
```

**Start the backend server:**

```bash
uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
```

The backend API will be available at `http://localhost:8000/docs`.

### Step 10.3 — Set Up the React Frontend

Open a **new terminal window**:

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The frontend will be available at `http://localhost:5173`.

---

## 11. Running Tests

### Backend Tests (pytest)

```bash
# If running via Docker:
docker compose exec backend pytest tests/ -v

# If running locally (with venv activated):
cd backend
pytest tests/ -v
```

### Frontend E2E Tests (Playwright)

The application must be running (via Docker or local dev servers) before executing these tests.

```bash
cd frontend

# Install Playwright and browser binaries (first time only)
npm install -D @playwright/test
npx playwright install

# Run the tests
npx playwright test
```

---

## 12. Useful Commands Reference

### Docker Compose

| Command | Description |
|:--------|:------------|
| `docker compose up --build -d` | Build and start all services in background |
| `docker compose up -d backend` | Recreate just the backend (picks up `.env` changes) |
| `docker compose down` | Stop and remove all containers |
| `docker compose logs -f backend` | Follow backend logs in real time |
| `docker compose exec backend bash` | Open a shell inside the backend container |
| `docker ps` | List all running containers |

### Database

| Command | Description |
|:--------|:------------|
| `docker compose exec backend alembic upgrade head` | Run all pending migrations |
| `docker compose exec backend python seed_kb.py` | Seed the Knowledge Base |
| `docker compose exec backend python seed_kb.py --reset` | Clear and re-seed the KB |
| `docker compose exec db psql -U helpdesk_user -d helpdesk_db` | Open a PostgreSQL shell |

### Quick SQL Queries (via psql)

```bash
# Check seeded KB articles
docker compose exec db psql -U helpdesk_user -d helpdesk_db \
  -c "SELECT title, department FROM knowledge_documents;"

# Check registered users
docker compose exec db psql -U helpdesk_user -d helpdesk_db \
  -c "SELECT email, role FROM users;"

# Check tickets
docker compose exec db psql -U helpdesk_user -d helpdesk_db \
  -c "SELECT title, status, category FROM tickets;"
```

---

## 13. Troubleshooting

### Docker Issues

| Problem | Solution |
|:--------|:---------|
| `Docker daemon is not running` | Open Docker Desktop and wait for the engine to start. |
| `port is already allocated` | Another process is using that port. Stop it or change the port mapping in `docker-compose.yml`. |
| `network helpdesk_default not found` | Run `docker compose up -d` to create the network. |
| Container keeps restarting | Check logs: `docker compose logs backend` for errors. |

### Backend Issues

| Problem | Solution |
|:--------|:---------|
| `No embedding model configured` | Your API key is missing or `.env` was not picked up. Run `docker compose up -d backend` to recreate. |
| `404 NOT_FOUND` on embedding model | The model name is wrong. Use `gemini-embedding-2` for Gemini or `text-embedding-3-small` for OpenAI. |
| `expected 1536 dimensions, not 3072` | Embedding provider changed but DB column was not updated. See [Switching AI Providers](#9-switching-ai-providers). |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` (local) or rebuild: `docker compose up --build -d backend`. |

### Frontend Issues

| Problem | Solution |
|:--------|:---------|
| Blank page or module errors | Run `docker compose exec frontend npm install` to install new dependencies. |
| Hot-reload not working (Windows) | File-watching through Docker volumes can be flaky on Windows. Set `CHOKIDAR_USEPOLLING=true` (already configured). |
| `CORS` errors in browser console | Ensure the backend is running and accessible on the expected port. |

### Environment Issues

| Problem | Solution |
|:--------|:---------|
| `.env` changes not taking effect | You must recreate the container: `docker compose up -d backend`. A simple `restart` does **not** reload `.env`. |
| `Database Connection Refused` (local) | Use `@localhost:5432` in `DATABASE_URL`, not `@db:5432` (which is Docker's internal hostname). |

---

## Quick Start Cheat Sheet

For the impatient — run these commands in order from the project root:

```bash
# 1. Create your .env file and add your API key (see Section 3)

# 2. Start everything
docker compose up --build -d

# 3. Create database tables
docker compose exec backend alembic upgrade head

# 4. Seed the Knowledge Base
docker compose exec backend python seed_kb.py

# 5. Open the app
# → http://localhost:5173  (Frontend)
# → http://localhost:8001/docs  (API Docs)
# → http://localhost:8080  (Database Viewer)
```
