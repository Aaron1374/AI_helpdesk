from src.workflow.state import AgentState
from src.services.retrieval_service import RetrievalService
from src.core.db import AsyncSessionLocal
import logging

logger = logging.getLogger(__name__)

async def retrieve_node(state: AgentState):
    """Async retrieval node — runs on the same event loop as FastAPI/LangGraph."""
    query = state.get("sanitized_query") or state.get("input", "")
    user_context = state.get("user_context", {}) or {}
    user_department = user_context.get("department", "general")

    docs = []
    score = 0.0
    try:
        async with AsyncSessionLocal() as session:
            docs, score = await RetrievalService.get_similar_documents(
                session, query, user_department
            )
    except Exception as e:
        logger.warning(f"Error during retrieval node execution: {e}")
        docs = []
        score = 0.0

    evidence = list(state.get("evidence", []))
    if docs:
        evidence.append({"source": "knowledge_and_incidents", "documents": docs})

    logger.info(f"Retrieval completed — query: '{query[:60]}', score: {score:.4f}, docs: {len(docs)}")
    return {"evidence": evidence, "retrieval_score": score}
