import re
import json
import logging

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.workflow.state import AgentState
from src.core.llm import get_chat_model, normalize_content
from src.workflow.constants import MAX_CLARIFICATION_ROUNDS
from src.workflow.utils.guardrails import sanitize_input, is_it_support_query

logger = logging.getLogger(__name__)

GREETING_ONLY = {"hi", "hello", "hey", "help", "test", "ok"}

# Hardcoded inline — no persona.py dependency. Same voice used in
# preprocess's clarifying question and resolve_node's final answer, kept
# here as a single string constant so both stay consistent.
PERSONA_VOICE = (
    "You are the AI IT Helpdesk Assistant. Sound like a calm, competent "
    "colleague on the helpdesk — plain language, no corporate stiffness, "
    "no over-apologizing. Keep this same tone whether you're asking a "
    "follow-up question or giving the fix."
)


def _conversation_transcript(state: AgentState, current_input: str) -> str:
    lines = []
    for m in state.get("messages", []) or []:
        if isinstance(m, SystemMessage) and m.content:
            lines.append(f"[{m.content}]")
        elif isinstance(m, HumanMessage) and m.content:
            lines.append(f"User: {m.content}")
        elif isinstance(m, AIMessage) and m.content:
            lines.append(f"Assistant: {m.content}")
    lines.append(f"User: {current_input}")
    return "\n".join(lines)


def _prior_ai_turns(state: AgentState) -> int:
    return sum(1 for m in state.get("messages", []) or [] if isinstance(m, AIMessage))


def _extract_search_query(state: AgentState, current_input: str) -> str:
    """
    Extract a focused search query for vector retrieval, avoiding conversational
    boilerplate (like 'Did that resolve the issue?', '1 - Yes', 'hello').
    """
    human_messages = [
        m.content for m in (state.get("messages", []) or [])
        if isinstance(m, HumanMessage) and getattr(m, "content", "")
    ]
    if not human_messages:
        return current_input.strip()

    first_problem = human_messages[0].strip()
    words = current_input.strip().split()
    if len(words) <= 4 or current_input.strip().lower() in {"no", "nope", "2", "still broken", "same issue", "not working"}:
        return first_problem

    return f"{first_problem} {current_input.strip()}".strip()


_TOPIC_PIVOT_PATTERNS = [
    r"\border me\b", r"\bpizza\b", r"\bfood delivery\b", r"\bzomato\b", r"\bswiggy\b",
    r"\buber\b", r"\btell me a joke\b", r"\bplay (some )?music\b", r"\bwhat'?s the weather\b",
    r"\bforget (it|this)\b.{0,20}\b(order|book|play|tell)\b",
]
_TOPIC_PIVOT_RE = re.compile("|".join(_TOPIC_PIVOT_PATTERNS), re.I)


def _is_hard_topic_pivot(raw_text: str) -> bool:
    """Cheap, deterministic. Catches an unambiguous abandonment of the IT
    issue — ordering food, chit-chat, unrelated requests — regardless of
    conversation history. Can't misfire on a confirmation reply since none
    of these phrases overlap with 'yes'/'still broken'/'confirmed'."""
    return bool(_TOPIC_PIVOT_RE.search(raw_text))


def _transcript_still_on_topic(transcript: str, config: RunnableConfig = None) -> bool:
    """LLM check, run only when the hard-pivot regex didn't already catch it.
    Framed as topic continuity, not scope. Defaults to True (continue) on
    any failure or ambiguity: wrongly rejecting a real continuation is worse
    than missing a subtle pivot, which just costs one wasted retrieval call
    downstream, never a fabricated answer."""
    llm = get_chat_model()
    if not llm:
        return True
    try:
        prompt = [
            SystemMessage(content=(
                "This is an ongoing IT helpdesk conversation. Look at the latest "
                "user message in context. Has the user CLEARLY abandoned the IT "
                "issue for something unrelated (e.g. ordering food, casual chat, "
                "a completely different non-IT request)? Answering, confirming, "
                "saying yes/no, or giving more detail about the SAME issue is "
                "NOT abandonment, even if short.\n\n"
                "Reply with exactly one word: CONTINUE or ABANDONED."
            )),
            HumanMessage(content=transcript),
        ]
        res = llm.invoke(prompt, config=config)
        verdict = normalize_content(getattr(res, "content", res)).strip().upper()
        return "ABANDONED" not in verdict
    except Exception as exc:
        logger.warning("Topic-continuity check failed, defaulting to continue: %s", exc)
        return True


def preprocess_node(state: AgentState, config: RunnableConfig = None):
    raw_text = (state.get("input", "") or "").strip()
    prior_rounds = _prior_ai_turns(state)

    if prior_rounds == 0:
        # Cold open — the only place the empty-greeting and full scope
        # checks run.
        if len(raw_text) < 4 or raw_text.lower() in GREETING_ONLY:
            return {
                "needs_clarification": True,
                "sanitized_query": raw_text,
                "search_query": raw_text,
                "messages": [AIMessage(content=(
                    "Hello! I'm your AI IT Helpdesk Assistant. Please describe the IT issue "
                    "you're experiencing — what you were doing, what happened, and any error "
                    "message you saw — and I'll help or route you to an engineer."
                ))],
            }

        sanitized = sanitize_input(raw_text)

        if not is_it_support_query(sanitized, config=config):
            return {
                "needs_clarification": False,
                "out_of_scope": True,
                "sanitized_query": sanitized,
                "search_query": sanitized,
                "status": "resolved",
                "messages": [AIMessage(content=(
                    "I'm sorry, but your request doesn't appear to be related to IT support. "
                    "I can help with issues like VPN problems, password resets, software installation, "
                    "email issues, hardware problems, and other IT-related topics.\n\n"
                    "Please describe an IT issue and I'll be happy to assist!"
                ))],
            }
    else:
        sanitized = sanitize_input(raw_text)
        transcript_so_far = _conversation_transcript(state, sanitized)

        if _is_hard_topic_pivot(raw_text) or not _transcript_still_on_topic(transcript_so_far, config=config):
            return {
                "needs_clarification": False,
                "out_of_scope": True,
                "sanitized_query": sanitized,
                "status": "resolved",
                "messages": [AIMessage(content=(
                    "It looks like we've moved away from the IT issue we were troubleshooting. "
                    "I can only help with IT support topics — if you still need help with the "
                    "original issue, just let me know and we can pick it back up."
                ))],
            }

    transcript = _conversation_transcript(state, sanitized)
    search_q = _extract_search_query(state, sanitized)

    if prior_rounds >= MAX_CLARIFICATION_ROUNDS:
        return {
            "needs_clarification": False,
            "out_of_scope": False,
            "sanitized_query": sanitize_input(transcript),
            "search_query": search_q,
        }

    llm = get_chat_model()
    if not llm:
        return {
            "needs_clarification": False,
            "out_of_scope": False,
            "sanitized_query": sanitize_input(transcript),
            "search_query": search_q,
        }

    try:
        prompt = [
            SystemMessage(content=(
                f"{PERSONA_VOICE}\n\n"
                "Read the conversation so far and assess the IT issue:\n"
                "1. Is there sufficient detail to search the knowledge base and troubleshoot? (sufficient: true/false)\n"
                "   If false, provide at most ONE short, specific follow-up question (never a list, never an essay).\n"
                "2. If sufficient, classify into Category (Access, Network, Hardware, Software, Email, Security, Application)\n"
                "   and Priority (CRITICAL, HIGH, MEDIUM, LOW) with a short rationale.\n\n"
                "Return ONLY a JSON object with keys: 'sufficient', 'question', 'category', 'priority', and 'rationale'."
            )),
            HumanMessage(content=transcript),
        ]
        res = llm.invoke(prompt, config=config)
        content = normalize_content(getattr(res, "content", res)).strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        parsed = json.loads(content.strip())

        if not parsed.get("sufficient", True):
            question = (parsed.get("question") or "").strip() or (
                "Could you share a bit more detail — what exact error or symptom "
                "are you seeing, and when did it start?"
            )
            return {
                "needs_clarification": True,
                "sanitized_query": sanitize_input(transcript),
                "search_query": search_q,
                "messages": [AIMessage(content=question)],
            }

        # Sufficient: extract category and priority if valid
        cat = parsed.get("category", "").strip().lower()
        pri = parsed.get("priority", "").strip().lower()
        rat = parsed.get("rationale", "").strip()

        updates = {
            "needs_clarification": False,
            "out_of_scope": False,
            "sanitized_query": sanitize_input(transcript),
            "search_query": search_q,
        }
        if cat in ALLOWED_CATEGORIES:
            updates["category"] = cat
        if pri in ALLOWED_PRIORITIES:
            updates["priority"] = pri.upper()
        if rat:
            updates["priority_rationale"] = rat

        return updates

    except Exception as exc:
        logger.warning("Clarification sufficiency check failed, proceeding without it: %s", exc)

    return {
        "needs_clarification": False,
        "out_of_scope": False,
        "sanitized_query": sanitize_input(transcript),
        "search_query": search_q,
    }


# Backward compatibility alias
clarify_node = preprocess_node


ALLOWED_CATEGORIES = {
    "access", "network", "hardware", "software", "email", "security", "application",
}
ALLOWED_PRIORITIES = {"critical", "high", "medium", "low"}

def classify_node(state: AgentState, config: RunnableConfig = None):
    # Fast path: if already classified in unified triage, avoid redundant LLM call
    if state.get("category") and state.get("category") != "general_support" and state.get("priority"):
        return {
            "category": state["category"],
            "priority": state["priority"],
            "priority_rationale": state.get("priority_rationale", "Classified during triage."),
        }

    text = state.get("search_query") or state.get("sanitized_query") or state.get("input", "")
    llm = get_chat_model()

    cat = "general_support"
    priority = "medium"
    rationale = "Default fallback applied."

    if llm:
        try:
            prompt = [
                SystemMessage(content=(
                    "Classify the IT issue into exactly ONE of these categories:\n"
                    "Access, Network, Hardware, Software, Email, Security, Application.\n\n"
                    "Also assign a priority (CRITICAL, HIGH, MEDIUM, LOW) based on these rules:\n"
                    "- CRITICAL: Security incidents, complete work stoppage affecting multiple users.\n"
                    "- HIGH: Single user completely blocked from working.\n"
                    "- MEDIUM: User impacted but has a workaround or it's not urgent.\n"
                    "- LOW: Minor inconvenience, cosmetic, or a general request.\n\n"
                    "Return ONLY a JSON object with keys: 'category', 'priority', and 'rationale' "
                    "(a short explanation)."
                )),
                HumanMessage(content=text),
            ]
            res = llm.invoke(prompt, config=config)
            content = normalize_content(getattr(res, "content", res)).strip()
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
        "priority_rationale": rationale,
    }