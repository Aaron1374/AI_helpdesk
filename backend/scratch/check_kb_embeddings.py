import asyncio
import sys
sys.path.insert(0, ".")
from src.core.db import AsyncSessionLocal
from sqlalchemy import select
from src.models.knowledge import KnowledgeDocument

async def main():
    async with AsyncSessionLocal() as s:
        res = await s.execute(select(KnowledgeDocument.id, KnowledgeDocument.title, KnowledgeDocument.embedding != None))
        rows = res.all()
        print("Total KB rows:", len(rows))
        print("Sample embeddings present:", [r[2] for r in rows[:5]])

if __name__ == "__main__":
    asyncio.run(main())
