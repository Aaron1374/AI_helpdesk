from src.workflow.state import AgentState
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from src.core.llm import get_chat_model

from src.workflow.utils.guardrails import sanitize_input

def preprocess_node(state: AgentState):
    raw_text = (state.get("input", "") or "").strip()
    
    # Only request clarification if the user only entered a brief greeting or empty string
    if len(raw_text) < 4 or raw_text.lower() in {"hi", "hello", "hey", "help", "test", "ok"}:
        return {
            "needs_clarification": True,
            "sanitized_query": raw_text,
            "messages": [AIMessage(content="Hello! I am your AI IT Helpdesk Assistant. Please describe the IT issue or problem you are experiencing, and I will assist or route it to an engineer.")]
        }
    
    sanitized = sanitize_input(raw_text)
    return {
        "needs_clarification": False,
        "sanitized_query": sanitized
    }

# Backward compatibility alias
clarify_node = preprocess_node


def classify_node(state: AgentState):
    text = state.get("sanitized_query") or state.get("input", "")
    llm = get_chat_model()
    
    if llm:
        try:
            prompt = [
                SystemMessage(content="Classify the IT issue into one of these standard categories: Access, Network, Hardware, Software, Email, Security, Application. Reply with only the category name."),
                HumanMessage(content=text)
            ]
            res = llm.invoke(prompt)
            cat = res.content.strip().lower()
            return {"category": cat}
        except Exception:
            pass

    return {"category": "general_support"}

