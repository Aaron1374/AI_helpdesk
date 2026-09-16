from langchain_core.runnables import RunnableConfig
from src.workflow.state import AgentState
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from src.core.llm import get_chat_model

from src.workflow.utils.guardrails import sanitize_input, is_it_support_query

def preprocess_node(state: AgentState, config: RunnableConfig = None,):
    raw_text = (state.get("input", "") or "").strip()
    
    # Only request clarification if the user only entered a brief greeting or empty string
    if len(raw_text) < 4 or raw_text.lower() in {"hi", "hello", "hey", "help", "test", "ok"}:
        return {
            "needs_clarification": True,
            "sanitized_query": raw_text,
            "messages": [AIMessage(content="Hello! I am your AI IT Helpdesk Assistant. Please describe the IT issue or problem you are experiencing, and I will assist or route it to an engineer.")]
        }
    
    sanitized = sanitize_input(raw_text)
    
    # Early out-of-scope check: reject non-IT queries without running classification or vector search
    if not is_it_support_query(sanitized, config=config):
        return {
            "needs_clarification": False,
            "out_of_scope": True,
            "sanitized_query": sanitized,
            "status": "resolved",
            "messages": [AIMessage(content=(
                "I'm sorry, but your request doesn't appear to be related to IT support. "
                "I can help with issues like VPN problems, password resets, software installation, "
                "email issues, hardware problems, and other IT-related topics.\n\n"
                "Please describe an IT issue and I'll be happy to assist!"
            ))]
        }

    return {
        "needs_clarification": False,
        "out_of_scope": False,
        "sanitized_query": sanitized
    }


# Backward compatibility alias
clarify_node = preprocess_node


import json
from src.core.llm import get_chat_model

ALLOWED_CATEGORIES = {
    "access",
    "network",
    "hardware",
    "software",
    "email",
    "security",
    "application",
}

ALLOWED_PRIORITIES = {
    "critical",
    "high",
    "medium",
    "low",
}

def classify_node(state: AgentState, config: RunnableConfig = None,):
    text = state.get("sanitized_query") or state.get("input", "")
    llm = get_chat_model()

    cat = "general_support"
    priority = "medium"
    rationale = "Default fallback applied."

    if llm:
        try:
            prompt = [
                SystemMessage(
                    content=(
                        "Classify the IT issue into exactly ONE of these categories:\n"
                        "Access, Network, Hardware, Software, Email, Security, Application.\n\n"
                        "Also assign a priority (CRITICAL, HIGH, MEDIUM, LOW) based on these rules:\n"
                        "- CRITICAL: Security incidents, complete work stoppage affecting multiple users.\n"
                        "- HIGH: Single user completely blocked from working.\n"
                        "- MEDIUM: User impacted but has a workaround or it's not urgent.\n"
                        "- LOW: Minor inconvenience, cosmetic, or a general request.\n\n"
                        "Return ONLY a JSON object with keys: 'category', 'priority', and 'rationale' (a short explanation)."
                    )
                ),
                HumanMessage(content=text),
            ]

            res = llm.invoke(prompt, config=config)
            # Try to parse JSON from the response
            content = res.content.strip()
            # Clean up markdown JSON blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            parsed = json.loads(content)
            
            c = parsed.get("category", "").strip().lower()
            if c in ALLOWED_CATEGORIES:
                cat = c
                
            p = parsed.get("priority", "").strip().lower()
            if p in ALLOWED_PRIORITIES:
                priority = p
                
            r = parsed.get("rationale", "").strip()
            if r:
                rationale = r

        except Exception:
            # Fallback keyword logic for priority
            text_lower = text.lower()
            if any(k in text_lower for k in ["malware", "phishing", "security", "breach", "outage"]):
                priority = "critical"
                rationale = "Critical keyword detected."
            elif any(k in text_lower for k in ["locked out", "won't boot", "can't login", "bsod", "blocked"]):
                priority = "high"
                rationale = "High priority keyword detected."
            elif any(k in text_lower for k in ["how do i", "request"]):
                priority = "low"
                rationale = "Low priority keyword detected."

    return {
        "category": cat,
        "priority": priority.upper(),
        "priority_rationale": rationale
    }
