from backend.src.workflow.state import AgentState
from langchain_core.messages import AIMessage

def escalate_node(state: AgentState):
    # Prepare handoff
    return {"status": "escalated", "messages": [AIMessage(content="I am escalating this ticket to a human engineer.")]}

def human_node(state: AgentState):
    # This node simply passes the state forward, representing the human takeover boundary
    # No AI processing occurs here.
    return {"status": "human_takeover"}
