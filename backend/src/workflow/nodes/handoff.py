import json
import logging
from src.workflow.state import AgentState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

def handoff_node(state: AgentState):
    msgs = list(state.get("messages", []))
    evidence = list(state.get("evidence", []))
    query = state.get("sanitized_query") or state.get("input", "")
    
    summary_payload = {
        "query": query,
        "summary": "User issue could not be resolved automatically by RAG assistant.",
        "evidence_count": len(evidence),
        "retrieval_score": state.get("retrieval_score", 0.0)
    }
    
    evidence.append({"source": "handoff_summary", "payload": summary_payload})
    
    # Ensure there is a friendly user-facing message informing them of the ticket escalation
    has_ai_response = any(isinstance(m, AIMessage) and m.content for m in msgs)
    if not has_ai_response:
        msgs.append(AIMessage(content="I have recorded your issue and created an escalated support ticket for an L1 Support Engineer to review and assist shortly."))
        
    logger.info(f"Handoff node executed for query: '{query}'. Summary payload created.")
    return {
        "status": "escalated",
        "needs_handoff": True,
        "escalate": True,
        "evidence": evidence,
        "messages": msgs
    }

# Alias for backward compatibility with graph wiring
escalate_node = handoff_node

def human_node(state: AgentState):
    return {"status": "human_takeover"}
