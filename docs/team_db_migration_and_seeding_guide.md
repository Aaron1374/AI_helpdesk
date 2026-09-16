# Teammate Guide: Database Migration & KB Seeding

This guide provides step-by-step instructions for teammates to pull the latest changes, run Alembic migrations, and populate the PostgreSQL/pgvector database with chunked knowledge base documents.

---

## Prerequisites

1. Ensure **Docker Desktop** (or Docker engine) is running.
2. Ensure your `.env` file in the project root contains valid database credentials and API key:
   ```env
   DATABASE_URL=postgresql+asyncpg://helpdesk_user:helpdesk_password@db:5432/helpdesk_db
   OPENAI_API_KEY=your-openai-api-key   # or GOOGLE_API_KEY
   ```

---

## Step 1: Pull Latest Code & Start Containers

Pull the latest repository commits and start the container stack:

```bash
# Pull latest code
git pull origin main

# Navigate to backend/project folder if needed
cd AI_helpdesk

# Start Docker containers
docker compose up -d
```

---

## Step 2: Apply Alembic Schema Migrations

Run Alembic to apply all database schema updates (including `de3b484134cf_add_document_and_chunk_metadata` which adds `document_id`, `chunk_index`, and alters `content` to `TEXT`):

```bash
docker compose exec backend alembic upgrade head
```

### Verify Table Schema
Confirm that `knowledge_documents` contains `document_id` (UUID) and `chunk_index` (integer):

```bash
docker compose exec db psql -U helpdesk_user -d helpdesk_db -c "\d knowledge_documents"
```

*Expected output:*
```text
                     Table "public.knowledge_documents"
   Column    |            Type             | Collation | Nullable | Default 
-------------+-----------------------------+-----------+----------+---------
 id          | uuid                        |           | not null | 
 title       | character varying           |           | not null | 
 content     | text                        |           | not null | 
 embedding   | vector(3072)                |           |          | 
 metadata    | jsonb                       |           |          | 
 department  | character varying           |           |          | 
 created_at  | timestamp without time zone |           |          | 
 updated_at  | timestamp without time zone |           |          | 
 document_id | uuid                        |           | not null | 
 chunk_index | integer                     |           | not null | 
Indexes:
    "knowledge_documents_pkey" PRIMARY KEY, btree (id)
    "ix_knowledge_documents_document_id" btree (document_id)
```

---

## Step 3: Seed PostgreSQL with Chunked Documents & Vectors

Run `seed_kb.py` inside the backend container.

### Option A: Preview Chunks (Dry Run)
Check how many chunks will be generated without calling the embedding API or altering the database:

```bash
docker compose exec backend python seed_kb.py --dry-run
```

### Option B: Reset & Seed Database (Full Execution)
Clear old records, generate 3,072-dimensional vector embeddings, and insert all section-aware chunks:

```bash
docker compose exec backend python seed_kb.py --reset
```

*Console log output during seeding:*
```text
============================================================
  KB Chunk-Aware Seeder — kb_articles.json
============================================================

  Loaded 100 article(s) from kb_articles.json.
  Prepared 107 chunk(s) from 100 article(s).

  Generating embeddings for 107 chunk(s) in batches of 25...
    - Processing batch 1/5 (25 chunks)...
    - Processing batch 2/5 (25 chunks)...
    - Processing batch 3/5 (25 chunks)...
    - Processing batch 4/5 (25 chunks)...
    - Processing batch 5/5 (7 chunks)...
  Done. Generated 107 embedding(s) of 3072 dimensions.
  [RESET] Cleared all existing knowledge documents.

  Inserting 107 chunk(s) into database...
  [SUCCESS] Database populated with 107 chunks across 100 unique articles.
```

---

## Step 4: Verification

### 1. Check Row & Unique Article Counts
Run a PostgreSQL SQL check:

```bash
docker compose exec db psql -U helpdesk_user -d helpdesk_db -c "SELECT COUNT(*) AS total_chunks, COUNT(DISTINCT document_id) AS unique_articles, COUNT(embedding) AS embedded_chunks FROM knowledge_documents;"
```

*Expected result:*
```text
 total_chunks | unique_articles | embedded_chunks 
--------------+-----------------+-----------------
          107 |             100 |             107
```

### 2. Run Backend Unit Test Suite
Ensure all unit tests pass cleanly:

```bash
docker compose exec backend python -m pytest tests/ -v
```

---

## Troubleshooting

- **429 Rate Limit Error**: `seed_kb.py` includes automatic exponential backoff retry. If your API quota limit is reached, it will pause for 15-25 seconds and automatically resume.
- **Database Connection Error**: Ensure the `db` container is healthy (`docker compose ps`).
