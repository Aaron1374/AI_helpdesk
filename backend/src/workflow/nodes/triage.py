from src.workflow.state import AgentState
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from src.core.llm import get_chat_model

def clarify_node(state: AgentState):
    text = (state.get("input", "") or "").strip()
    
    # Only request clarification if the user only entered a brief greeting or empty string
    if len(text) < 4 or text.lower() in {"hi", "hello", "hey", "help", "test", "ok"}:
        return {
            "needs_clarification": True,
            "messages": [AIMessage(content="Hello! I am your AI IT Helpdesk Assistant. Please describe the IT issue or problem you are experiencing, and I will assist or route it to an engineer.")]
        }
    return {"needs_clarification": False}

def classify_node(state: AgentState):
    text = state.get("input", "")
    llm = get_chat_model()
    
    if llm:
        try:
            prompt = [
                SystemMessage(content="Classify the IT issue. Reply with only the category name."),
                HumanMessage(content=text)
            ]
            res = llm.invoke(prompt)
            return {"category": res.content.strip()}
        except Exception:
            pass

    return {"category": "general_support"}
