import os
import logging
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from src.models.knowledge import KnowledgeDocument
from src.models.ticket import Ticket
from src.core.llm import get_embedding_model

logger = logging.getLogger(__name__)

class RetrievalService:
    @staticmethod
    async def get_similar_documents(
        db: AsyncSession, 
        query_text: str, 
        user_department: str = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        if not query_text or not query_text.strip():
            return []

        # Graceful fallback if no embeddings provider
        embeddings_model = None
        try:
            embeddings_model = get_embedding_model()
        except Exception as e:
            logger.warning(f"Could not initialize embeddings: {e}")
                
        if not embeddings_model:
            return []

        try:
            query_embedding = embeddings_model.embed_query(query_text)
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            return []

        # Knowledge Base Retrieval
        # Object-level auth: match department or allow generic (None)
        kb_stmt = select(KnowledgeDocument).where(
            or_(KnowledgeDocument.department == user_department, KnowledgeDocument.department == None)
        ).order_by(KnowledgeDocument.embedding.cosine_distance(query_embedding)).limit(limit)
        
        kb_result = await db.execute(kb_stmt)
        kb_docs = kb_result.scalars().all()

        # Ticket/Incident Retrieval (Duplicate incidents)
        # Object-level auth: strict department matching only
        ticket_stmt = select(Ticket).where(
            Ticket.department == user_department
        ).order_by(Ticket.embedding.cosine_distance(query_embedding)).limit(limit)
        
        ticket_result = await db.execute(ticket_stmt)
        ticket_docs = ticket_result.scalars().all()
        
        filtered = []
        for doc in kb_docs:
            filtered.append({
                "type": "knowledge",
                "title": doc.title,
                "content": doc.content
            })
            
        for t in ticket_docs:
            filtered.append({
                "type": "ticket",
                "title": t.title,
                "content": t.description,
                "status": t.status.value
            })
                
        return filtered
