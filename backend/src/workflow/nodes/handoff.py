import uuid
import logging
from datetime import datetime
from langchain_core.messages import AIMessage
from src.workflow.state import AgentState

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.setLevel(logging.INFO)
    # Ensure the logs directory exists
    import os
    log_dir = os.path.join(os.path.dirname(__file__), "..", "..", "workflow", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "handoff_node.log")
    _h = logging.FileHandler(log_path)
    _h.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(_h)


def handoff_node(state: AgentState) -> dict:
    """Execute only when state['needs_handoff'] is True.

    Builds a structured escalation payload:
      - ticket_summary: concise ticket metadata for the engineer dashboard
      - evidence: full list of raw KB docs + mock-tool JSONs
    """
    if not state.get("needs_handoff", False):
        logger.warning("handoff_node reached without needs_handoff=True; no-op.")
        return {}

    sanitized_query = state.get("sanitized_query", state.get("input", "Unknown query"))
    evidence = state.get("evidence", [])
    retrieval_score = state.get("retrieval_score", 0.0)
    category = state.get("category", "general")

    ticket_summary = {
        "ticket_id": str(uuid.uuid4()),
        "created_at": datetime.utcnow().isoformat() + "Z",
        "query": sanitized_query,
        "category": category,
        "retrieval_score": retrieval_score,
        "summary": "User issue could not be resolved automatically. Requires L1 engineer review.",
        "evidence_count": len(evidence),
    }

    escalation_payload = {
        "ticket_summary": ticket_summary,
        "evidence": evidence,
    }

    tid = ticket_summary["ticket_id"]
    logger.info("Handoff initiated ticket_id=%s evidence_count=%d score=%.3f",
                tid, len(evidence), retrieval_score)

    score_str = f"{retrieval_score:.2f}"
    user_msg = (
        "I could not resolve your issue automatically "
        "(RAG score: " + score_str + "). "
        "Escalation ticket " + tid + " has been raised and "
        "forwarded to an L1 support engineer who will follow up shortly."
    )

    return {
        "status": "escalated",
        "escalate": True,
        "handoff_payload": escalation_payload,
        "messages": [AIMessage(content=user_msg)],
    }


def human_node(state: AgentState) -> dict:
    """Signals that a human engineer has taken over the conversation."""
    payload = state.get("handoff_payload", {})
    ticket_id = payload.get("ticket_summary", {}).get("ticket_id", "N/A")
    logger.info("Human takeover ticket_id=%s", ticket_id)
    return {"status": "human_takeover"}
