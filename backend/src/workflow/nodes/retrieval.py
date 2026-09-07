from backend.src.workflow.state import AgentState
from backend.src.services.retrieval_service import RetrievalService
from backend.src.core.db import AsyncSessionLocal
import asyncio

def retrieve_node(state: AgentState):
    query = state.get("input", "")
    user_context = state.get("user_context", {})
    user_department = user_context.get("department", "general")
    
    # Normally we'd pass db session down cleanly, but in async node we can manage it
    async def do_retrieval():
        async with AsyncSessionLocal() as session:
            docs = await RetrievalService.get_similar_documents(session, query, user_department)
            return docs
            
    try:
        # In actual langgraph async nodes this would just be awaited
        try:
            loop = asyncio.get_running_loop()
            docs = loop.run_until_complete(do_retrieval())
        except RuntimeError:
            docs = asyncio.run(do_retrieval())
    except Exception:
        docs = []

    evidence = state.get("evidence", [])
    if docs:
        evidence.append({"source": "knowledge_and_incidents", "documents": docs})
        
    return {"evidence": evidence}
