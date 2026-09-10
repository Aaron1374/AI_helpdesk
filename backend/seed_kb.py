"""
seed_kb.py — Knowledge Base Population Script
==============================================
Reads articles from kb_articles.json, generates vector embeddings,
and upserts them into the knowledge_documents table.

USAGE
-----
Run from the backend/ directory:

  # With Docker running (recommended for teams):
  docker-compose exec backend python seed_kb.py

  # Or locally (requires a .env file and running DB):
  python seed_kb.py

OPTIONS
-------
  --dry-run     Print what would be inserted without writing to the DB.
  --reset       Delete all existing KB documents before seeding.
  --file PATH   Path to the articles JSON file (default: kb_articles.json).

ADDING NEW ARTICLES
-------------------
Edit kb_articles.json — no Python knowledge required.
Then re-run this script. Existing articles (matched by title) will be
updated; new ones will be inserted.
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make sure src/ is importable and env vars are set BEFORE imports
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")  # load root .env

# Set fallback DATABASE_URL before importing src so src.core.db doesn't crash locally
if not os.getenv("DATABASE_URL"):
    os.environ["DATABASE_URL"] = "postgresql+asyncpg://helpdesk_user:helpdesk_password@localhost:5432/helpdesk_db"

from sqlalchemy import select, delete
from src.core.db import AsyncSessionLocal
from src.models.knowledge import KnowledgeDocument
from src.core.llm import get_embedding_model

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
        # Skip comment/instruction objects (they have '_comment' or '_fields' keys)
        if "_comment" in item or "_fields" in item:
            continue
        if not item.get("title") or not item.get("content"):
            print(f"[WARN] Skipping entry with missing title or content: {item}")
            continue
        articles.append(item)

    return articles


def generate_embeddings(articles: list[dict]) -> list[list[float]]:
    """Batch-generate embeddings for all article content strings."""
    model = get_embedding_model()
    if not model:
        print("[ERROR] No embedding model configured.")
        print("        Set OPENAI_API_KEY (or GOOGLE_API_KEY) in your .env file.")
        sys.exit(1)

    contents = [a["content"] for a in articles]
    print(f"  Generating embeddings for {len(contents)} article(s)...")
    embeddings = model.embed_documents(contents)
    print(f"  Done. Each embedding has {len(embeddings[0])} dimensions.")
    return embeddings


# ---------------------------------------------------------------------------
# Core seeding logic
# ---------------------------------------------------------------------------

async def seed(articles: list[dict], embeddings: list[list[float]], reset: bool, dry_run: bool):
    async with AsyncSessionLocal() as db:

        if reset and not dry_run:
            await db.execute(delete(KnowledgeDocument))
            await db.commit()
            print("  [RESET] Cleared all existing knowledge documents.")

        inserted = 0
        updated = 0

        for article, embedding in zip(articles, embeddings):
            title = article["title"]
            content = article["content"]
            department = article.get("department")  # None = global
            metadata = article.get("metadata", {})

            if dry_run:
                dept_label = department or "ALL DEPARTMENTS"
                print(f"  [DRY RUN] Would upsert: '{title}' (dept: {dept_label})")
                continue

            # Check if an article with this title already exists
            result = await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.title == title)
            )
            existing = result.scalar_one_or_none()

            if existing:
                existing.content = content
                existing.embedding = embedding
                existing.department = department
                existing.metadata_ = metadata
                db.add(existing)
                updated += 1
                print(f"  [UPDATE] '{title}'")
            else:
                doc = KnowledgeDocument(
                    title=title,
                    content=content,
                    embedding=embedding,
                    department=department,
                    metadata_=metadata,
                )
                db.add(doc)
                inserted += 1
                print(f"  [INSERT] '{title}'")

        if not dry_run:
            await db.commit()
            print(f"\n  Seeding complete. {inserted} inserted, {updated} updated.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed the Knowledge Base from kb_articles.json")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to DB")
    parser.add_argument("--reset", action="store_true", help="Delete all KB docs before seeding")
    parser.add_argument("--file", default="kb_articles.json", help="Path to articles JSON file")
    args = parser.parse_args()

    print(f"\n{'=' * 55}")
    print(f"  KB Seeder {'[DRY RUN] ' if args.dry_run else ''}— {args.file}")
    print(f"{'=' * 55}\n")

    articles = load_articles(args.file)
    print(f"  Loaded {len(articles)} article(s) from {args.file}.\n")

    if not articles:
        print("  No valid articles found. Nothing to do.")
        return

    if args.dry_run:
        # No need to call the embedding API in dry-run mode
        for article in articles:
            dept_label = article.get("department") or "ALL DEPARTMENTS"
            print(f"  [DRY RUN] Would upsert: '{article['title']}' (dept: {dept_label})")
        return

    embeddings = generate_embeddings(articles)
    asyncio.run(seed(articles, embeddings, reset=args.reset, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
