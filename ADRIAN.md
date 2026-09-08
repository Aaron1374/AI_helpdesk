# Team Setup & Changes

## Navigation

* [Changes Made](#changes-made)
* [Prerequisites](#prerequisites)
* [Environment](#1-environment)
* [Fresh Backend Setup](#2-fresh-backend-setup)
* [PostgreSQL + pgvector](#3-verify-postgresql--pgvector)
* [Alembic Migrations](#4-run-alembic-migrations)
* [Backend Verification](#5-verify-backend)
* [Quick Start](#quick-start)
* [Notes](#notes)

---

## Changes Made

* Added root `.env` for PostgreSQL, Gemini API key, and `SECRET_KEY`.
* Updated `docker-compose.yml` to use environment variables and expose the backend on `8001`.
* Added `asyncpg` and `langchain-google-genai`; removed OpenAI-specific dependency.
* Enabled PostgreSQL `vector` extension.
* Added/fixed Alembic migrations.
* Added `backend/alembic/env.py` for Alembic DB configuration.
* Updated `src/core/db.py` to read `DATABASE_URL` from environment variables.
* Fixed `backend.src.*` imports to `src.*` for the Docker setup.
* Added `SECRET_KEY` validation in `auth/security.py`.
* Successfully ran all migrations and verified the backend/API.

> **Add future changes to this list only. Keep it short and chronological.**

---

## Prerequisites

* Docker Desktop installed and running
* Git installed
* Gemini API key

> Run Docker commands from the project root (`AI_helpdesk`).

## 1. Environment

Create `.env` in the project root:

```env
POSTGRES_USER=helpdesk_user
POSTGRES_PASSWORD=your_real_password
POSTGRES_DB=helpdesk_db
DATABASE_URL=postgresql+asyncpg://helpdesk_user:your_real_password@db:5432/helpdesk_db

GEMINI_API_KEY=your_actual_gemini_key
SECRET_KEY=your_own_secret
```

Each developer creates their own `.env`. It is **not committed to GitHub**.

Ensure `.env` is included in `.gitignore`.

## 2. Fresh Backend Setup

To verify the backend can be recreated from a completely clean state:

```powershell
docker compose down -v
docker compose up -d
docker compose ps
```

Expected services:

```text
backend → 8001
db      → 5432
```

## 3. Verify PostgreSQL + pgvector

Enable the extension:

```powershell
docker compose exec db psql -U helpdesk_user -d helpdesk_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

Verify:

```powershell
docker compose exec db psql -U helpdesk_user -d helpdesk_db -c "SELECT extversion FROM pg_extension WHERE extname='vector';"
```

## 4. Run Alembic Migrations

```powershell
docker compose exec backend alembic upgrade head
```

Verify the tables:

```powershell
docker compose exec db psql -U helpdesk_user -d helpdesk_db -c "\dt"
```

Expected tables include:

```text
users
conversations
messages
tickets
ticket_history
audit_events
knowledge_documents
alembic_version
```


## 5. Verify Backend

Check for incorrect imports:

```powershell
Get-ChildItem -Recurse backend\src -Filter *.py |
    Select-String "backend\.src"
```

Expected: **no output**.

Verify the application imports:

```powershell
docker compose exec backend python -c "from src.main import app; print(app)"
```

Verify the API:

```powershell
curl.exe http://127.0.0.1:8001/docs
```

Expected: **HTTP 200**.

You can also open:

`http://localhost:8001/docs`

If the Swagger page loads, the backend is running correctly.

---

## Quick Start

For an existing checkout where the database has already been initialized:

```powershell
docker compose up -d
docker compose exec db psql -U helpdesk_user -d helpdesk_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose exec backend alembic upgrade head
docker compose ps
```

Then verify the backend:

`http://localhost:8001/docs`

## Notes

* `backend/alembic/env.py` is already part of the setup — teammates should **not recreate it**.
* Tables should be created through Alembic, not manually.
* The Docker Compose `version` warning is harmless and can be removed from `docker-compose.yml`.
