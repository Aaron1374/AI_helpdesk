from src.workflow.state import AgentState
from langchain_core.messages import AIMessage

def escalate_node(state: AgentState):
    msgs = list(state.get("messages", []))
    if not msgs:
        msgs.append(AIMessage(content="I have created a ticket and escalated this issue to an L1 support engineer."))
    return {"status": "escalated", "messages": msgs}

def human_node(state: AgentState):
    return {"status": "human_takeover"}
