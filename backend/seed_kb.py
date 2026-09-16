"""
seed_kb.py — Knowledge Base Population Script (Chunk-Aware)
==============================================================================
Reads articles from kb_articles.json, chunks them using section-aware chunker,
generates 3072-dimensional vector embeddings for each chunk with rate-limit retries/batching,
and populates the knowledge_documents table.
"""

import argparse
import asyncio
import json
import os
import sys
import time
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make sure src/ is importable and env vars are set BEFORE imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")  # load root .env

if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://helpdesk_user:helpdesk_password@localhost:5432/helpdesk_db"

from sqlalchemy import select, delete
from src.core.db import AsyncSessionLocal
from src.models.knowledge import KnowledgeDocument
from src.core.llm import get_embedding_model
from src.rag.chunker import chunk_article

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_articles(filepath: str) -> list[dict]:
    """Load and validate articles from the JSON file."""
    path = Path(filepath)
    if not path.exists():
        print(f"[ERROR] File not found: {path.resolve()}")
        sys.exit(1)

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    articles = []
    for item in raw:
        if "_comment" in item or "_fields" in item:
            continue
        if not item.get("title") or not item.get("content"):
            print(f"[WARN] Skipping entry with missing title or content: {item}")
            continue
        articles.append(item)

    return articles


def prepare_chunks(articles: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Chunk articles using chunker.py and assign parent document_id.
    Returns (chunk_records, list_of_content_strings_for_embedding).
    """
    chunk_records = []
    content_strings = []

    for article in articles:
        doc_id = uuid.uuid4()
        title = article["title"]
        content = article["content"]
        department = article.get("department")
        metadata = article.get("metadata", {})

        chunks = chunk_article(title, content)
        for chunk_data in chunks:
            c_text = chunk_data["content"]
            record = {
                "id": uuid.uuid4(),
                "document_id": doc_id,
                "chunk_index": chunk_data["chunk_index"],
                "title": title,
                "content": c_text,
                "department": department,
                "metadata_": metadata,
            }
            chunk_records.append(record)
            content_strings.append(c_text)

    return chunk_records, content_strings


def generate_embeddings(content_strings: list[str], batch_size: int = 25) -> list[list[float]]:
    """Batch-generate 3072-dim embeddings for chunk content strings with rate-limit retries."""
    model = get_embedding_model()
    if not model:
        print("[ERROR] No embedding model configured.")
        print("        Set OPENAI_API_KEY (or GOOGLE_API_KEY) in your .env file.")
        sys.exit(1)

    print(f"  Generating embeddings for {len(content_strings)} chunk(s) in batches of {batch_size}...")
    all_embeddings = []

    for i in range(0, len(content_strings), batch_size):
        batch = content_strings[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(content_strings) + batch_size - 1) // batch_size
        print(f"    - Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)...")

        max_retries = 5
        retry_delay = 16.0

        for attempt in range(1, max_retries + 1):
            try:
                batch_embeddings = model.embed_documents(batch)
                all_embeddings.extend(batch_embeddings)
                break
            except Exception as e:
                err_msg = str(e)
                if "RESOURCE_EXHAUSTED" in err_msg or "429" in err_msg:
                    print(f"      [RATE LIMIT] Rate limited on batch {batch_num}. Retrying in {retry_delay:.1f}s (Attempt {attempt}/{max_retries})...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
                else:
                    print(f"      [ERROR] Embedding batch {batch_num} failed: {e}")
                    raise e

        # Small pause between successful batches
        if i + batch_size < len(content_strings):
            time.sleep(1.0)

    print(f"  Done. Generated {len(all_embeddings)} embedding(s) of {len(all_embeddings[0])} dimensions.")
    return all_embeddings


# ---------------------------------------------------------------------------
# Core seeding logic
# ---------------------------------------------------------------------------

async def seed(chunk_records: list[dict], embeddings: list[list[float]], reset: bool, dry_run: bool):
    async with AsyncSessionLocal() as db:

        if reset and not dry_run:
            await db.execute(delete(KnowledgeDocument))
            await db.commit()
            print("  [RESET] Cleared all existing knowledge documents.")

        if dry_run:
            print(f"\n  [DRY RUN] Would insert {len(chunk_records)} chunk(s) into database:")
            for rec in chunk_records[:5]:
                print(f"    - Doc ID {rec['document_id']} | Chunk {rec['chunk_index']} | Title: '{rec['title']}' ({len(rec['content'])} chars)")
            if len(chunk_records) > 5:
                print(f"    ... and {len(chunk_records) - 5} more chunk(s).")
            return

        print(f"\n  Inserting {len(chunk_records)} chunk(s) into database...")

        for rec, emb in zip(chunk_records, embeddings):
            doc = KnowledgeDocument(
                id=rec["id"],
                document_id=rec["document_id"],
                chunk_index=rec["chunk_index"],
                title=rec["title"],
                content=rec["content"],
                embedding=emb,
                department=rec["department"],
                metadata_=rec["metadata_"],
            )
            db.add(doc)

        await db.commit()
        print(f"  [SUCCESS] Database populated with {len(chunk_records)} chunks across {len(set(r['document_id'] for r in chunk_records))} unique articles.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed Knowledge Base Chunks from kb_articles.json")
    parser.add_argument("--dry-run", action="store_true", help="Preview chunks without embedding or writing to DB")
    parser.add_argument("--reset", action="store_true", help="Delete all KB docs before seeding")
    parser.add_argument("--file", default="kb_articles.json", help="Path to articles JSON file")
    args = parser.parse_args()

    print(f"\n{'=' * 60}")
    print(f"  KB Chunk-Aware Seeder {'[DRY RUN] ' if args.dry_run else ''}— {args.file}")
    print(f"{'=' * 60}\n")

    articles = load_articles(args.file)
    print(f"  Loaded {len(articles)} article(s) from {args.file}.")

    if not articles:
        print("  No valid articles found. Nothing to do.")
        return

    chunk_records, content_strings = prepare_chunks(articles)
    print(f"  Prepared {len(chunk_records)} chunk(s) from {len(articles)} article(s).\n")

    if args.dry_run:
        asyncio.run(seed(chunk_records, [], reset=args.reset, dry_run=True))
        return

    embeddings = generate_embeddings(content_strings)
    asyncio.run(seed(chunk_records, embeddings, reset=args.reset, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
