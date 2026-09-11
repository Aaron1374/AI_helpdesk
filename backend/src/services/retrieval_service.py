import os
import logging
import math
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from src.models.knowledge import KnowledgeDocument
from src.models.ticket import Ticket
from src.core.llm import get_embedding_model

logger = logging.getLogger(__name__)

def calc_cosine_similarity(v1: Any, v2: Any) -> float:
    """Calculate cosine similarity between two vector lists."""
    if not v1 or not v2:
        return 0.0
    try:
        # Convert pgvector or array objects to standard float lists if needed
        list1 = [float(x) for x in v1]
        list2 = [float(x) for x in v2]
        if len(list1) != len(list2):
            return 0.0
        dot = sum(a * b for a, b in zip(list1, list2))
        norm1 = math.sqrt(sum(a * a for a in list1))
        norm2 = math.sqrt(sum(b * b for b in list2))
        return float(dot / (norm1 * norm2)) if (norm1 > 0 and norm2 > 0) else 0.0
    except Exception as e:
        logger.warning(f"Error calculating cosine similarity: {e}")
        return 0.0

class RetrievalService:
    @staticmethod
    async def get_similar_documents(
        db: AsyncSession,
        query_text: str,
        user_department: str = None,
        limit: int = 3
    ) -> tuple[list[dict[str, Any]], float]:
        if not query_text or not query_text.strip():
            return [], 0.0

        # Graceful fallback if no embeddings provider
        embeddings_model = None
        try:
            embeddings_model = get_embedding_model()
        except Exception as e:
            logger.warning(f"Could not initialize embeddings: {e}")

        if not embeddings_model:
            return [], 0.0

        try:
            query_embedding = embeddings_model.embed_query(query_text)
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            return [], 0.0

        # Knowledge Base Retrieval
        kb_stmt = select(KnowledgeDocument).where(
            or_(KnowledgeDocument.department == user_department, KnowledgeDocument.department == None)
        ).order_by(KnowledgeDocument.embedding.cosine_distance(query_embedding)).limit(limit)

        kb_result = await db.execute(kb_stmt)
        kb_docs = kb_result.scalars().all()

        # Ticket/Incident Retrieval (Duplicate incidents)
        ticket_stmt = select(Ticket).where(
            Ticket.department == user_department
        ).order_by(Ticket.embedding.cosine_distance(query_embedding)).limit(limit)

        ticket_result = await db.execute(ticket_stmt)
        ticket_docs = ticket_result.scalars().all()

        filtered: list[dict[str, Any]] = []
        max_similarity = 0.0

        for doc in kb_docs:
            similarity = calc_cosine_similarity(doc.embedding, query_embedding)
            if similarity > max_similarity:
                max_similarity = similarity
            filtered.append({
                "type": "knowledge",
                "title": doc.title,
                "content": doc.content,
                "similarity": similarity,
            })

        for t in ticket_docs:
            similarity = calc_cosine_similarity(t.embedding, query_embedding)
            if similarity > max_similarity:
                max_similarity = similarity
            filtered.append({
                "type": "ticket",
                "title": t.title,
                "content": t.description,
                "status": t.status.value,
                "similarity": similarity,
            })

        return filtered, max_similarity

