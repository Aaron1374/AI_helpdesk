from langgraph.graph import StateGraph, END
from src.workflow.state import AgentState
from src.workflow.nodes.intake import intake_node, injection_pre_check_node
from src.workflow.nodes.triage import clarify_node, classify_node
from src.workflow.nodes.resolution import diagnose_node, resolve_node, verify_node
from src.workflow.nodes.handoff import escalate_node, human_node
from src.workflow.escalation import EscalationPolicy

from src.workflow.nodes.retrieval import retrieve_node

workflow = StateGraph(AgentState)

workflow.add_node("intake", intake_node)
workflow.add_node("injection_pre_check", injection_pre_check_node)
workflow.add_node("clarify", clarify_node)
workflow.add_node("classify", classify_node)
workflow.add_node("retrieve", retrieve_node)
workflow.add_node("diagnose", diagnose_node)
workflow.add_node("resolve", resolve_node)
workflow.add_node("verify", verify_node)
workflow.add_node("escalate", escalate_node)
workflow.add_node("human", human_node)

workflow.set_entry_point("intake")

def check_takeover(state: AgentState):
    # Interrupt if human took over
    if state.get("status") == "human_takeover":
        return "human"
    return "injection_pre_check"

workflow.add_conditional_edges("intake", check_takeover)

def check_injection(state: AgentState):
    if EscalationPolicy.should_escalate(state):
        return "escalate"
    return "clarify"

workflow.add_conditional_edges("injection_pre_check", check_injection)

def check_clarification(state: AgentState):
    if state.get("needs_clarification"):
        return END
    return "classify"

workflow.add_conditional_edges("clarify", check_clarification)
workflow.add_edge("classify", "retrieve")
workflow.add_edge("retrieve", "diagnose")

def check_diagnose(state: AgentState):
    if EscalationPolicy.should_escalate(state):
        return "escalate"
    return "resolve"

workflow.add_conditional_edges("diagnose", check_diagnose)

def check_resolution(state: AgentState):
    if EscalationPolicy.should_escalate(state):
        return "escalate"
    return "verify"

workflow.add_conditional_edges("resolve", check_resolution)
workflow.add_edge("verify", END)

workflow.add_edge("escalate", "human")
workflow.add_edge("human", END)

app = workflow.compile()
