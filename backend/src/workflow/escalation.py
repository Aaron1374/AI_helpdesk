import logging
from src.workflow.state import AgentState

logger = logging.getLogger(__name__)


class EscalationPolicy:
    HARD_ESCALATION_CATEGORIES = {"security_incident", "hardware_failure", "network_outage"}

    @classmethod
    def should_escalate(cls, state: dict) -> bool:
        # Explicit handoff flag set by resolve_node
        if state.get("needs_handoff") is True:
            return True
        # Explicit escalate flag
        if state.get("escalate") is True:
            return True
        # Hard-coded categories always escalate
        category = state.get("category")
        if category in cls.HARD_ESCALATION_CATEGORIES:
            return True
        # Too many tool errors in evidence
        errors = [e for e in state.get("evidence", []) if isinstance(e, dict) and "error" in e]
        if len(errors) >= 2:
            return True
        return False


def escalate_node(state: AgentState) -> dict:
    """Forward the escalation payload to the engineer dashboard.

    In production this would publish to a queue / call an API.
    Here it logs the full payload and returns status=escalated.
    """
    payload = state.get("handoff_payload", {})
    ticket_id = payload.get("ticket_summary", {}).get("ticket_id", "N/A")
    evidence_count = payload.get("ticket_summary", {}).get("evidence_count", 0)
    logger.info(
        "escalate_node: forwarding ticket_id=%s evidence_count=%d to engineer dashboard",
        ticket_id, evidence_count,
    )
    msgs = list(state.get("messages", []))
    return {"status": "escalated", "messages": msgs}
