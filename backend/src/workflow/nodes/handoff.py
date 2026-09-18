from langchain_core.runnables import RunnableConfig
import json
import logging
from src.workflow.state import AgentState
from langchain_core.messages import AIMessage

logger = logging.getLogger(__name__)

def handoff_node(state: AgentState, config: RunnableConfig = None,):
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
    last_msg = msgs[-1] if msgs else None
    has_recent_escalation_msg = (
        isinstance(last_msg, AIMessage)
        and last_msg.content
        and any(k in last_msg.content.lower() for k in ["escalat", "engineer", "security alert", "connecting you", "recorded your issue"])
    )
    new_msgs = []
    if not has_recent_escalation_msg:
        new_msgs.append(
            AIMessage(
                content=(
                    "I have recorded your issue and created an escalated support ticket for an L1 Support Engineer. "
                    "A team member will review the diagnostic details gathered and assist you shortly."
                )
            )
        )
        
    logger.info(f"Handoff node executed for query: '{query}'. Summary payload created.")
    return {
        "status": "escalated",
        "needs_handoff": True,
        "escalate": True,
        "evidence": evidence,
        "messages": new_msgs
    }

# Alias for backward compatibility with graph wiring
escalate_node = handoff_node

def human_node(state: AgentState, config: RunnableConfig = None,):
    return {"status": "human_takeover"}
