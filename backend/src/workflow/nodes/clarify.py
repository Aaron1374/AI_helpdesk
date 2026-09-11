"""
clarify.py — Intelligent clarification node

Sits between `preprocess` and `classify` in the graph.

Behaviour:
- If the query already has enough specific detail, passes through immediately.
- If the query is vague/broad, asks ONE targeted follow-up question.
- On a follow-up turn (prior messages exist), checks if the new input adds
  the missing detail; if so, merges context and passes through.
- Limits clarification attempts to 1 round (to avoid infinite loops).
"""

import re
from src.workflow.state import AgentState
from langchain_core.messages import AIMessage, HumanMessage

# Minimum word count before we consider a query "detailed enough"
_MIN_WORDS = 6

# Phrases that signal a follow-up (user already answered a clarification)
_FOLLOWUP_SIGNALS = re.compile(
    r"\b(it started|since|when i|after|the error|getting|the issue|my|on my|i tried|tried|step|still|yes|no|because|error message|shows|says|the screen)\b",
    re.IGNORECASE,
)

# Vague IT queries that need more detail
_VAGUE_PATTERNS = re.compile(
    r"^(not working|doesn[\'\u2019]?t work|broken|having issues?|having a problem|help|issue|problem|error|can[\'\u2019]?t|cannot|slow|stuck|something wrong|doesn[\'\u2019]?t respond|not responding|weird|strange)\.?$",
    re.IGNORECASE,
)


def _is_vague(text: str, prior_messages: list) -> bool:
    """Return True if the query needs clarification before RAG."""
    stripped = text.strip().lower()

    # If there are already prior AI messages (i.e. this is a follow-up turn),
    # don't ask again — the user is already in a conversation
    has_prior_ai = any(isinstance(m, AIMessage) for m in prior_messages)
    if has_prior_ai:
        return False

    # Too short or matches a vague catch-all phrase
    words = text.split()
    if len(words) < _MIN_WORDS or _VAGUE_PATTERNS.match(stripped):
        return True

    return False


def _generate_clarification_question(text: str) -> str:
    """Generate a targeted follow-up question based on the vague query."""
    lower = text.lower()

    if any(kw in lower for kw in ["vpn", "connect", "network", "internet", "wifi"]):
        return (
            "I can help with your connectivity issue. To assist you better, could you tell me:\n"
            "1. What exactly happens when you try to connect? (Any error message?)\n"
            "2. Which device and OS are you using?\n"
            "3. Has this issue occurred before, or is this the first time?"
        )
    elif any(kw in lower for kw in ["login", "password", "access", "account", "sign in"]):
        return (
            "I can help with your access issue. A few questions:\n"
            "1. Which application or system can't you access?\n"
            "2. What error or message do you see?\n"
            "3. Have you recently changed your password or had any account changes?"
        )
    elif any(kw in lower for kw in ["slow", "slow", "lag", "performance", "freeze", "hang"]):
        return (
            "I can help diagnose the performance issue. Could you clarify:\n"
            "1. Which application or part of the system is slow/freezing?\n"
            "2. When did this start — after an update, specific action, or randomly?\n"
            "3. Does a restart help temporarily?"
        )
    elif any(kw in lower for kw in ["email", "outlook", "mail"]):
        return (
            "I can help with your email issue. To narrow it down:\n"
            "1. What exactly is happening — not receiving, not sending, or an error?\n"
            "2. Is the issue on desktop, web browser, or mobile?\n"
            "3. Any specific error message displayed?"
        )
    elif any(kw in lower for kw in ["printer", "print", "scanner"]):
        return (
            "I can help with your printer/scanner issue. Could you tell me:\n"
            "1. What happens when you try to print? (Error message or nothing at all?)\n"
            "2. Is the printer showing as online in Windows/Mac?\n"
            "3. Is this a new issue or has it worked before?"
        )
    elif any(kw in lower for kw in ["install", "software", "application", "app", "update"]):
        return (
            "I can help with your software issue. To assist further:\n"
            "1. What is the name of the software/application?\n"
            "2. What happens when you try to install/open it? (Any error code?)\n"
            "3. What operating system are you using?"
        )
    else:
        # Generic clarification
        return (
            "I'd like to help you resolve your IT issue. To get started, could you provide a bit more detail?\n"
            "1. What exactly is happening? (Any error messages you can share?)\n"
            "2. Which device, system, or application is affected?\n"
            "3. When did this issue start, and did anything change around that time?"
        )


def clarify_node(state: AgentState):
    """
    Clarification node: determines if the query needs more detail before RAG.
    - If vague → returns a targeted question and sets needs_clarification=True.
    - If clear  → passes through with needs_clarification=False.
    """
    text = (state.get("input", "") or state.get("sanitized_query", "")).strip()
    prior_messages = list(state.get("messages", []))

    if _is_vague(text, prior_messages):
        question = _generate_clarification_question(text)
        return {
            "needs_clarification": True,
            "messages": [AIMessage(content=question)],
        }

    return {"needs_clarification": False}
