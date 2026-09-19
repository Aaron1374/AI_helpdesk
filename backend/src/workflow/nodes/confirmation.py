import logging
import re

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from src.workflow.state import AgentState
from src.workflow.constants import CONFIRM_MARKER, CONFIRM_FINAL_MARKER
from src.core.llm import get_chat_model, normalize_content

logger = logging.getLogger(__name__)

# Detects follow-up questions asked mid-confirmation
# (e.g. "how do I check the firewall?", "what does step 3 mean?")
_FOLLOWUP_QUESTION_RE = re.compile(
    r"\b(how (do|to|can|should)|what (is|does|do|are|should)|where (do|can|is)|why (is|does|would)|when (do|should)|can you (explain|tell|show|help)|could you|please (explain|clarify|tell)|step [0-9]+|which (step|option|one))",
    re.I,
)


def _is_followup_question(raw_reply: str) -> bool:
    """True when the user is asking a clarifying/follow-up question rather
    than confirming yes/no/unsure. Detected by question words or '?' present."""
    if "?" in raw_reply:
        return True
    return bool(_FOLLOWUP_QUESTION_RE.search(raw_reply))


def _answer_followup_with_llm(
    question: str,
    state: AgentState,
    config: RunnableConfig = None,
) -> str:
    """Answer a follow-up IT question using the LLM's general knowledge,
    grounded in the conversation context (the resolution steps already given)."""
    llm = get_chat_model()
    if not llm:
        return (
            "I'd recommend checking your IT department's documentation or "
            "contacting the support team for detailed guidance on that step."
        )

    # Build a short context from the last AI resolution message
    last_ai_content = ""
    for m in reversed(state.get("messages", []) or []):
        if isinstance(m, AIMessage) and m.content:
            last_ai_content = m.content[:1500]  # cap to avoid huge prompts
            break

    try:
        prompt = [
            SystemMessage(content=(
                "You are a knowledgeable IT helpdesk assistant. "
                "The user was just given troubleshooting steps for an IT issue. "
                "They are now asking a follow-up question about one of the steps or a related detail. "
                "Answer their question directly and clearly using your general IT knowledge. "
                "Be concise — 2 to 5 sentences is ideal. Do not repeat the full troubleshooting list."
                + (f"\n\nContext (previous answer given):\n{last_ai_content}" if last_ai_content else "")
            )),
            HumanMessage(content=question),
        ]
        res = llm.invoke(prompt, config=config)
        return (res.content or "").strip() or "I'm not sure — let me get an engineer to clarify that for you."
    except Exception as exc:
        logger.warning("Follow-up LLM answer failed: %s", exc)
        return "I'm not sure — let me get an engineer to clarify that for you."


def _confirmation_already_presented(state: AgentState) -> bool:
    for m in state.get("messages", []) or []:
        content = getattr(m, "content", "") or ""
        if CONFIRM_MARKER in content or CONFIRM_FINAL_MARKER in content:
            return True
    return False


def _final_confirmation_already_sent(state: AgentState) -> bool:
    for m in state.get("messages", []) or []:
        content = getattr(m, "content", "") or ""
        if CONFIRM_FINAL_MARKER in content:
            return True
    return False


def present_confirmation_node(state: AgentState, config: RunnableConfig = None):
    if _confirmation_already_presented(state):
        content = (
            "I've updated my answer based on what you shared.\n\n"
            "If that's sorted, just let me know and I'll close this out — "
            "otherwise I'll bring in an engineer to take it from here.\n\n"
            f"{CONFIRM_FINAL_MARKER}"
        )
    else:
        content = (
            "Did that resolve the issue?\n\n"
            "- **1** — Yes, that fixed it \n"
            "- **2** — No, still having the issue \n"
            "- **3** — Not sure \n\n"
            "You can just reply with a number, or in your own words — and you "
            "can ask me to escalate to an engineer at any point.\n\n"
            f"{CONFIRM_MARKER}"
        )

    return {"messages": [AIMessage(content=content)], "status": "awaiting_confirmation"}


_YES = re.compile(r"\b(1|yes|yep|yeah|resolved|fixed|works?|solved)\b", re.I)
_NO = re.compile(r"\b(2|no|nope|still|not working|didn'?t work|same issue)\b", re.I)

_ACK_PHRASES = {
    "ok got it", "ohk got it", "okay got it", "got it", "ok i got it", "okay i got it",
    "gotcha", "ok gotcha", "okay gotcha", "ohk gotcha",
    "will do", "will try", "i'll try", "ill try", "let me try", "let me check",
    "i'll check", "ill check", "i will try", "i will check", "let me do that",
    "ok thanks", "okay thanks", "thanks", "thank you", "thx", "thanks!", "thank you!",
    "ok", "okay", "ohk", "okey", "alright", "all right", "sure", "sounds good",
    "understood", "understod", "makes sense", "cool", "k", "kk",
    "will give it a try", "i will give it a try", "let me test", "i'll test", "ill test",
    "i will try that", "will try that", "i'll try that", "ill try that", "let me try that"
}

_ACK_RE = re.compile(
    r"\b(ok|okay|ohk|okey|got\s*it|gotcha|will\s*do|will\s*try|i'?ll\s*try|let\s*me\s*try|let\s*me\s*check|i'?ll\s*check|thanks|thank\s*you|thx|understood|sounds\s*good|alright|all\s*right|cool)\b",
    re.I,
)

# Fast, deterministic path for an explicit ask to talk to a human —
# checked BEFORE the yes/no/unsure classification, and honored
# unconditionally regardless of retry count. A direct request for a
# person shouldn't be gated by "you haven't used your one retry yet."
_ESCALATE_REQUEST_RE = re.compile(
    r"\b(escalate|escalation)\b|"
    r"\b(talk|speak) (to|with)\b|"
    r"\b(connect|transfer) me\b|"
    r"\b(get|need|call|bring|fetch|give me|want) (a |an )?(engineer|human|person|agent|support)\b|"
    r"\b(real|human) (person|human|being)\b|"
    r"\b(engineer|human|person|agent|support) (please|here|now|right now)?\b",
    re.I,
)


def _wants_escalation(raw_reply: str) -> bool:
    return bool(_ESCALATE_REQUEST_RE.search(raw_reply))


def _classify_confirmation_reply(raw_reply: str, config: RunnableConfig = None) -> str:
    """Returns 'yes' | 'no' | 'ack' | 'unsure' | 'escalate'."""
    clean = raw_reply.strip().lower()
    if _wants_escalation(clean):
        return "escalate"

    no_phrases = [
        "didn't work", "did not work", "not working", "still broken",
        "same issue", "didn't help", "not fixed", "not solved",
        "still not solved", "issue is still not solved", "issue still not solved",
        "still dropping", "still failing", "still disconnected", "persists",
        "doesn't work", "does not work"
    ]
    if clean in {"2", "no", "nope", "still broken", "not working"} or clean.startswith("2") or any(p in clean for p in no_phrases):
        return "no"

    yes_phrases = [
        "all fixed", "it works", "worked", "fixed it", "it resolved",
        "all good", "issue is resolved", "problem solved", "resolved now"
    ]
    if clean in {"1", "yes", "fixed", "resolved", "solved"} or clean.startswith("1") or any(p in clean for p in yes_phrases):
        return "yes"

    if clean in {"3", "not sure", "unsure"} or clean.startswith("3"):
        return "unsure"

    if clean in _ACK_PHRASES:
        return "ack"

    if _YES.search(clean) and not _NO.search(clean):
        return "yes"
    if _NO.search(clean) and not _YES.search(clean):
        return "no"
    if _ACK_RE.search(clean):
        return "ack"

    llm = get_chat_model()
    if llm:
        try:
            prompt = [
                SystemMessage(content=(
                    "The user was just asked whether their IT issue is resolved, or given troubleshooting instructions.\n"
                    "Classify their response into exactly one of these categories:\n"
                    "- YES: User confirms the issue is resolved or fixed (e.g., '1', 'yes', 'it worked', 'all fixed').\n"
                    "- NO: User states the issue is NOT resolved or still failing (e.g., '2', 'no', 'still not working', 'didn't work').\n"
                    "- ACK: User is acknowledging the instructions/steps and intends to try them (e.g., 'ok got it', 'will try', 'thanks', 'understood', 'let me check').\n"
                    "- ESCALATE: User directly requests a human, engineer, or agent.\n"
                    "- UNSURE: User says they don't know or gives an ambiguous response.\n\n"
                    "Reply with exactly one word: YES, NO, ACK, ESCALATE, or UNSURE."
                )),
                HumanMessage(content=raw_reply),
            ]
            res = llm.invoke(prompt, config=config)
            verdict = normalize_content(getattr(res, "content", res)).strip().upper()
            if "ESCALATE" in verdict:
                return "escalate"
            if "YES" in verdict:
                return "yes"
            if "NO" in verdict:
                return "no"
            if "ACK" in verdict:
                return "ack"
            if "UNSURE" in verdict:
                return "unsure"
        except Exception as exc:
            logger.warning("Confirmation sentiment check failed: %s", exc)

    return "unsure"


def handle_confirmation_node(state: AgentState, config: RunnableConfig = None):
    raw_reply = (state.get("input") or "").strip()

    # Follow-up question mid-confirmation: user asks "how to check the firewall"
    # etc. instead of giving yes/no. Answer it directly instead of escalating.
    if _is_followup_question(raw_reply):
        answer = _answer_followup_with_llm(raw_reply, state, config=config)
        confirm_suffix = (
            f"\n\nOnce you've had a chance to try that — was the original issue resolved? "
            f"(reply **1** for yes, **2** for no, or just tell me in your own words.)"
            f"\n\n{CONFIRM_MARKER}"
        )
        return {
            "confirmation_decision": "",  # stay in confirmation loop
            "awaiting_confirmation_reply": True,
            "messages": [AIMessage(content=answer + confirm_suffix)],
        }

    verdict = _classify_confirmation_reply(raw_reply, config=config)

    if verdict == "escalate":
        return {
            "confirmation_decision": "escalate",
            "escalate": True,
            "needs_handoff": True,
            "status": "escalated",
            "messages": [AIMessage(content="Understood — connecting you with an engineer now.")],
        }

    if verdict == "yes":
        return {
            "confirmation_decision": "resolved",
            "status": "resolved",
            "messages": [AIMessage(content="Glad that's sorted — closing this out. Reach out again if anything else comes up!")],
        }

    if verdict == "ack":
        confirm_msg = (
            "Great! Take your time to try those steps.\n\n"
            "Once you've tested it, please let me know if the issue is resolved "
            "(reply **1** for yes, **2** for no, or ask for an engineer if you need help).\n\n"
            f"{CONFIRM_MARKER}"
        )
        return {
            "confirmation_decision": "",
            "awaiting_confirmation_reply": True,
            "messages": [AIMessage(content=confirm_msg)],
        }

    is_final_stage = _final_confirmation_already_sent(state)

    if is_final_stage:
        return {
            "confirmation_decision": "escalate",
            "escalate": True,
            "needs_handoff": True,
            "status": "escalated",
            "messages": [AIMessage(content="Understood — connecting you with an engineer now.")],
        }

    if verdict == "no":
        human_messages = [
            m.content for m in (state.get("messages", []) or [])
            if isinstance(m, HumanMessage) and getattr(m, "content", "")
        ]
        orig_problem = human_messages[0] if human_messages else (state.get("sanitized_query") or state.get("input") or "")
        retry_q = orig_problem
        words = raw_reply.split()
        if len(words) > 3 and not raw_reply.lower().startswith("no, still"):
            retry_q = f"{orig_problem} {raw_reply}".strip()
        return {
            "confirmation_decision": "retry",
            "search_query": retry_q,
            "sanitized_query": retry_q,
        }

    # "unsure" — don't guess, escalate.
    return {
        "confirmation_decision": "escalate",
        "escalate": True,
        "needs_handoff": True,
        "status": "escalated",
        "messages": [AIMessage(content="I don't want to guess — let me bring in an engineer to take a look.")],
    }
