from src.workflow.state import AgentState
from langchain_core.messages import AIMessage
from src.workflow.utils.guardrails import sanitize_input, is_it_related

def preprocess_node(state: AgentState):
    """Preprocess node (replaces old clarify node).

    - Detects short greetings or empty input and requests clarification.
    - Rejects off-topic (non-IT) queries immediately.
    - Otherwise sanitizes the user input and stores it in the state as `sanitized_query`.
    """
    text = (state.get("input", "") or "").strip()

    # Short greetings or empty input → ask for clarification
    if len(text) < 4 or text.lower() in {"hi", "hello", "hey", "help", "test", "ok"}:
        return {
            "needs_clarification": True,
            "messages": [AIMessage(content="Hello! I am your AI IT Helpdesk Assistant. Please describe the IT issue or problem you are experiencing, and I will assist or route it to an engineer.")]
        }

    # Off-topic guard: reject anything that is not IT-related
    if not is_it_related(text):
        return {
            "needs_clarification": True,
            "messages": [
                AIMessage(
                    content=(
                        "I\'m sorry, I can only assist with IT-related issues such as "
                        "network problems, software errors, account access, hardware faults, "
                        "and similar topics. Your question doesn\'t appear to be IT-related. "
                        "Please describe an IT issue and I\'ll be happy to help!"
                    )
                )
            ],
        }

    # Normal IT input: sanitize and store for later nodes
    sanitized = sanitize_input(text)
    state["sanitized_query"] = sanitized
    return {"needs_clarification": False}
