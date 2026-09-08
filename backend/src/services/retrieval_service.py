from src.models.knowledge import KnowledgeDocument
from src.models.ticket import Ticket
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import List, Dict, Any
import logging

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
except ImportError:
    GoogleGenerativeAIEmbeddings = None

logger = logging.getLogger(__name__)

class RetrievalService:
    @staticmethod
    async def get_similar_documents(
        db: AsyncSession, 
        query_text: str, 
        user_department: str = None,
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        # Graceful fallback if no embeddings provider
        embeddings_model = None
        if GoogleGenerativeAIEmbeddings and os.getenv("GEMINI_API_KEY"):
            try:
                embeddings_model = GoogleGenerativeAIEmbeddings(
                    model="gemini-embedding-001"
                )
            except Exception as e:
                logger.warning(f"Could not initialize embeddings: {e}")
                
        if not embeddings_model:
            logger.warning("No embeddings provider available. Returning empty retrieval.")
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
