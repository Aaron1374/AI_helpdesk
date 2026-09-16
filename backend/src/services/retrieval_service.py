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
    @classmethod
    async def get_similar_documents(
        cls,
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
            logger.info("Embeddings model unavailable; falling back to keyword search.")
            return await cls._keyword_fallback(db, query_text, user_department, limit)

        query_embedding = None
        try:
            query_embedding = embeddings_model.embed_query(query_text)
        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}. Falling back to keyword search.")

        if not query_embedding:
            return await cls._keyword_fallback(db, query_text, user_department, limit)

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

        if not filtered or max_score < 0.5:
            logger.info("Vector retrieval yielded low score; running keyword fallback check.")
            kw_docs, kw_score = await cls._keyword_fallback(db, query_text, user_department, limit)
            if kw_score > max_score:
                return kw_docs, kw_score

        return filtered, max_score

    @staticmethod
    def generate_ticket_embedding(
    title: str,
        description: str,
        category: str = None,
    ) -> List[float]:
        """
        Generate an embedding representing the ticket/incident.
        """
        text_parts = [
            title or "",
            description or "",
            category or "",
        ]

        ticket_text = "\n".join(
            part.strip()
            for part in text_parts
            if part and part.strip()
        )

        if not ticket_text:
            raise ValueError("Cannot generate ticket embedding from empty text")

        embeddings_model = get_embedding_model()

        return embeddings_model.embed_query(ticket_text)

        
    @classmethod
    async def _keyword_fallback(
        cls,
        db: AsyncSession,
        query_text: str,
        user_department: str = None,
        limit: int = 5
    ) -> Tuple[List[Dict[str, Any]], float]:
        import re
        words = [w.lower() for w in re.findall(r"\w+", query_text) if len(w) > 2]
        stop_words = {"the", "and", "for", "that", "this", "with", "have", "from", "you", "are", "was", "not", "but", "what", "can", "how", "why", "did", "does", "will", "would", "could", "should", "some", "just", "about", "into", "after"}
        keywords = [w for w in words if w not in stop_words]
        if not keywords:
            return [], 0.0

        stmt = select(KnowledgeDocument).where(
            or_(KnowledgeDocument.department == user_department, KnowledgeDocument.department == None)
        )
        res = await db.execute(stmt)
        docs = res.scalars().all()

        scored_docs = []
        for doc in docs:
            t_lower = doc.title.lower()
            c_lower = doc.content.lower()
            title_matches = sum(1 for kw in keywords if kw in t_lower)
            content_matches = sum(1 for kw in keywords if kw in c_lower)
            total_matches = title_matches * 3 + content_matches
            if total_matches > 0:
                match_ratio = min(0.92, 0.72 + (total_matches * 0.04))
                scored_docs.append({
                    "type": "knowledge",
                    "title": doc.title,
                    "content": doc.content,
                    "score": match_ratio
                })

        scored_docs.sort(key=lambda d: d["score"], reverse=True)
        top_docs = scored_docs[:limit]
        max_score = top_docs[0]["score"] if top_docs else 0.0
        return top_docs, max_score


