import logging
import re

from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage

from src.workflow.state import AgentState
from src.workflow.constants import CONFIRM_MARKER, CONFIRM_FINAL_MARKER
from src.core.llm import get_chat_model

logger = logging.getLogger(__name__)


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

# Fast, deterministic path for an explicit ask to talk to a human —
# checked BEFORE the yes/no/unsure classification, and honored
# unconditionally regardless of retry count. A direct request for a
# person shouldn't be gated by "you haven't used your one retry yet."
_ESCALATE_REQUEST_RE = re.compile(
    r"\bescalate\b|\btalk to (a |an )?(person|human|someone|agent)\b|"
    r"\bspeak (to|with) (a |an )?(person|human|someone|agent)\b|"
    r"\b(connect|transfer) me\b|\breal (person|human)\b|"
    r"\b(an? )?(human|engineer|agent) (please|now)\b",
    re.I,
)


def _wants_escalation(raw_reply: str) -> bool:
    return bool(_ESCALATE_REQUEST_RE.search(raw_reply))


def _classify_confirmation_reply(raw_reply: str, config: RunnableConfig = None) -> str:
    """Returns 'yes' | 'no' | 'unsure' | 'escalate'."""
    if _wants_escalation(raw_reply):
        return "escalate"

    llm = get_chat_model()
    if llm:
        try:
            prompt = [
                SystemMessage(content=(
                    "The user was just asked whether their IT issue is resolved, with "
                    "options: 1) Yes it's fixed, 2) No, still an issue, 3) Not sure. "
                    "They may also directly ask to escalate or speak to a human/engineer "
                    "instead of answering the question. Classify their reply as exactly "
                    "one word: YES, NO, UNSURE, or ESCALATE."
                )),
                HumanMessage(content=raw_reply),
            ]
            res = llm.invoke(prompt, config=config)
            verdict = (res.content or "").strip().upper()
            if "ESCALATE" in verdict:
                return "escalate"
            if "YES" in verdict:
                return "yes"
            if "NO" in verdict:
                return "no"
            if "UNSURE" in verdict:
                return "unsure"
        except Exception as exc:
            logger.warning("Confirmation sentiment check failed, using keyword fallback: %s", exc)

    if _YES.search(raw_reply) and not _NO.search(raw_reply):
        return "yes"
    if _NO.search(raw_reply):
        return "no"
    return "unsure"


def handle_confirmation_node(state: AgentState, config: RunnableConfig = None):
    raw_reply = (state.get("input") or "").strip()
    verdict = _classify_confirmation_reply(raw_reply, config=config)

    if verdict == "escalate":
        # Honored immediately, regardless of retry stage — the user asked
        # directly, no reason to make them go through another full cycle
        # or hit a round cap first.
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

    is_final_stage = _final_confirmation_already_sent(state)

    if is_final_stage:
        return {"confirmation_decision": "escalate", "escalate": True, "needs_handoff": True, "status": "escalated"}

    if verdict == "no":
        return {"confirmation_decision": "retry"}

    # "unsure" — don't guess, escalate.
    return {"confirmation_decision": "escalate", "escalate": True, "needs_handoff": True, "status": "escalated"}