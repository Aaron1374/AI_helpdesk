import asyncio
import logging

from src.workflow.state import AgentState
from src.services.retrieval_service import RetrievalService
from src.core.db import AsyncSessionLocal
from src.workflow.utils.guardrails import sanitize_input

logger = logging.getLogger(__name__)

async def retrieve_node(state: AgentState):
    """Retrieval node for strict RAG.

    - Sanitizes the raw user input.
    - Calls RetrievalService which returns (documents, max_similarity).
    - Stores sanitized_query, evidence and retrieval_score in the state.
    """
    raw_query = state.get("input", "")
    sanitized = sanitize_input(raw_query)
    state["sanitized_query"] = sanitized

    user_context = state.get("user_context", {})
    user_department = user_context.get("department", "general")

    try:
        async with AsyncSessionLocal() as session:
            docs, score = await RetrievalService.get_similar_documents(
                session, sanitized, user_department
            )
    except Exception as e:
        logger.error(f"Retrieval failed: {e}", exc_info=True)
        docs, score = [], 0.0

    state["evidence"] = docs
    state["retrieval_score"] = score
    logger.info(f"Retrieval score: {score}")
    logger.info(f"Retrieved {len(docs)} documents")

    return {"evidence": docs, "retrieval_score": score, "sanitized_query": sanitized}
