import os
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from src.models.knowledge import KnowledgeDocument
from src.models.ticket import Ticket
from src.core.llm import get_embedding_model

logger = logging.getLogger(__name__)

from typing import List, Dict, Any, Tuple

class RetrievalService:
    @staticmethod
    async def get_similar_documents(
        db: AsyncSession, 
        query_text: str, 
        user_department: str = None,
        limit: int = 5
    ) -> Tuple[List[Dict[str, Any]], float]:
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

        scores: List[float] = []
        filtered = []

        try:
            # Knowledge Base Retrieval with Cosine Distance
            kb_dist = KnowledgeDocument.embedding.cosine_distance(query_embedding)
            kb_stmt = select(KnowledgeDocument, kb_dist.label("distance")).where(
                or_(KnowledgeDocument.department == user_department, KnowledgeDocument.department == None)
            ).order_by(kb_dist).limit(limit)
            
            kb_result = await db.execute(kb_stmt)
            kb_rows = kb_result.all()

            for row in kb_rows:
                doc = row[0]
                dist = row[1] if len(row) > 1 else None
                sim_score = max(0.0, 1.0 - float(dist)) if dist is not None else 0.0
                scores.append(sim_score)
                filtered.append({
                    "type": "knowledge",
                    "title": doc.title,
                    "content": doc.content,
                    "score": sim_score
                })
        except Exception as e:
            logger.warning(f"KB retrieval error: {e}")

        try:
            # Ticket/Incident Retrieval (Duplicate incidents)
            ticket_dist = Ticket.embedding.cosine_distance(query_embedding)
            ticket_stmt = select(Ticket, ticket_dist.label("distance")).where(
                Ticket.department == user_department
            ).order_by(ticket_dist).limit(limit)
            
            ticket_result = await db.execute(ticket_stmt)
            ticket_rows = ticket_result.all()

            for row in ticket_rows:
                t = row[0]
                dist = row[1] if len(row) > 1 else None
                sim_score = max(0.0, 1.0 - float(dist)) if dist is not None else 0.0
                scores.append(sim_score)
                filtered.append({
                    "type": "ticket",
                    "title": t.title,
                    "content": t.description,
                    "status": t.status.value,
                    "score": sim_score
                })
        except Exception as e:
            logger.warning(f"Ticket retrieval error: {e}")
                
        max_score = max(scores) if scores else 0.0
        return filtered, max_score

