import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.db import AsyncSessionLocal
from sqlalchemy import select, func
from src.models.knowledge import KnowledgeDocument
from src.services.retrieval_service import RetrievalService

async def main():
    async with AsyncSessionLocal() as session:
        count_res = await session.execute(select(func.count(KnowledgeDocument.id)))
        count = count_res.scalar()
        print(f"Total KB documents in database: {count}")

        query = "I did update my windows a moment ago and it just doesn't allow my VPN to get connected"
        docs, score = await RetrievalService.get_similar_documents(session, query, "general")
        print(f"Retrieval score: {score}")
        print(f"Retrieved docs count: {len(docs)}")
        for d in docs:
            print("Doc title:", d.get("title"), "score:", d.get("score"))

if __name__ == "__main__":
    asyncio.run(main())
