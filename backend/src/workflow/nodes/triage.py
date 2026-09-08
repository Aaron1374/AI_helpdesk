from src.workflow.state import AgentState
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
import os

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None

def get_llm():
    if not ChatGoogleGenerativeAI or not os.getenv("GEMINI_API_KEY"):
        return None
    return ChatGoogleGenerativeAI(model="gemini-3.6-flash", temperature=0)

def clarify_node(state: AgentState):
    text = state.get("input", "")
    llm = get_chat_model()
    
    if llm:
        try:
            prompt = [
                SystemMessage(content="If the user's issue is too short or vague, reply with a clarifying question. Otherwise, reply 'OK'."),
                HumanMessage(content=text)
            ]
            res = llm.invoke(prompt)
            if res.content.strip() != "OK":
                return {"needs_clarification": True, "messages": [AIMessage(content=res.content)]}
            return {"needs_clarification": False}
        except Exception:
            pass

    if len(text.strip()) < 10:
        return {"needs_clarification": True, "messages": [AIMessage(content="Could you please provide more details about your issue?")]}
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
