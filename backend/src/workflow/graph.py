from langgraph.graph import StateGraph, END
from src.workflow.state import AgentState
from src.workflow.nodes.intake import intake_node, injection_pre_check_node
from src.workflow.nodes.triage import classify_node
from src.workflow.nodes.preprocess import preprocess_node
from src.workflow.nodes.clarify import clarify_node
from src.workflow.nodes.retrieval import retrieve_node
from src.workflow.nodes.resolution import resolve_node, verify_node, diagnose_node
from src.workflow.nodes.handoff import handoff_node, human_node
from src.workflow.escalation import EscalationPolicy, escalate_node

# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------
workflow = StateGraph(AgentState)

# Register all nodes
workflow.add_node("intake",               intake_node)
workflow.add_node("injection_pre_check",  injection_pre_check_node)
workflow.add_node("preprocess",           preprocess_node)
workflow.add_node("clarify",              clarify_node)
workflow.add_node("classify",             classify_node)
workflow.add_node("retrieve",             retrieve_node)
workflow.add_node("diagnose",             diagnose_node)
workflow.add_node("resolve",              resolve_node)
workflow.add_node("handoff",              handoff_node)
workflow.add_node("escalate",             escalate_node)
workflow.add_node("verify",               verify_node)
workflow.add_node("human",                human_node)

# Entry point
workflow.set_entry_point("intake")

# ---------------------------------------------------------------------------
# Edge: intake → (human_takeover check) → injection_pre_check | human
# ---------------------------------------------------------------------------
def check_takeover(state: AgentState) -> str:
    if state.get("status") == "human_takeover":
        return "human"
    return "injection_pre_check"

workflow.add_conditional_edges("intake", check_takeover, {
    "human":               "human",
    "injection_pre_check": "injection_pre_check",
})

# ---------------------------------------------------------------------------
# Edge: injection_pre_check → (injection/hard-escalation check) → preprocess | escalate
# ---------------------------------------------------------------------------
def check_injection(state: AgentState) -> str:
    if EscalationPolicy.should_escalate(state):
        return "escalate"
    return "preprocess"

workflow.add_conditional_edges("injection_pre_check", check_injection, {
    "escalate":  "escalate",
    "preprocess": "preprocess",
})

# ---------------------------------------------------------------------------
# Edge: preprocess → (off-topic / greeting?) → clarify | END
# ---------------------------------------------------------------------------
def check_preprocess(state: AgentState) -> str:
    """Reject off-topic / greeting immediately; otherwise go to clarify."""
    if state.get("needs_clarification"):
        return END
    return "clarify"

workflow.add_conditional_edges("preprocess", check_preprocess, {
    END:       END,
    "clarify": "clarify",
})

# ---------------------------------------------------------------------------
# Edge: clarify → (query too vague?) → END | classify
# ---------------------------------------------------------------------------
def check_clarification(state: AgentState) -> str:
    """If clarify asked a question, pause and wait for user reply; else run RAG."""
    if state.get("needs_clarification"):
        return END
    return "classify"

workflow.add_conditional_edges("clarify", check_clarification, {
    END:        END,
    "classify": "classify",
})

# ---------------------------------------------------------------------------
# Core RAG & Diagnostic path: classify → retrieve → diagnose → resolve
# ---------------------------------------------------------------------------
workflow.add_edge("classify", "retrieve")
workflow.add_edge("retrieve", "diagnose")
workflow.add_edge("diagnose", "resolve")

# ---------------------------------------------------------------------------
# Edge: resolve → handoff | verify
#   "handoff" when resolve_node sets needs_handoff=True (score too low or guard fail)
#   "verify"  when answer is good
# ---------------------------------------------------------------------------
def check_resolution(state: AgentState) -> str:
    return "handoff" if state.get("needs_handoff", False) else "verify"

workflow.add_conditional_edges("resolve", check_resolution, {
    "handoff": "handoff",
    "verify":  "verify",
})

# ---------------------------------------------------------------------------
# Remaining edges
# ---------------------------------------------------------------------------
workflow.add_edge("handoff",  "escalate")
workflow.add_edge("escalate", "human")
workflow.add_edge("human",    END)
workflow.add_edge("verify",   END)

# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------
app = workflow.compile()
