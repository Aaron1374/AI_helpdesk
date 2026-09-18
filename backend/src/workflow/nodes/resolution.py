import re
import json
import logging

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

from src.workflow.state import AgentState
from src.tools.gateway import ToolGateway
from src.core.llm import get_chat_model
from src.workflow.constants import SIMILARITY_THRESHOLD, LLM_TEMPERATURE, LLM_SEED
from src.workflow.utils.guardrails import select_mock_tool, is_response_from_knowledge_base

logger = logging.getLogger(__name__)

gateway = ToolGateway({"vpn_check", "device_check"})


@tool
def vpn_check(target_id: str) -> str:
    """Check the VPN status for a given target ID."""
    pass


@tool
def device_check(target_id: str) -> str:
    """Check the device compliance status for a given target ID."""
    pass


tools = [vpn_check, device_check]


def diagnose_node(state: AgentState, config: RunnableConfig = None):
    evidence = list(state.get("evidence", []))
    tool_history = list(state.get("tool_history", []))
    user_context = state.get("user_context", {}) or {}
    messages = list(state.get("messages", []))
    sanitized_query = state.get("sanitized_query") or state.get("input", "")

    tool_name = select_mock_tool(sanitized_query)
    if tool_name and tool_name not in tool_history:
        try:
            res = gateway.execute(user_context, tool_name, target_id="mock123")
            evidence.append({"source": "diagnostic_tool", "tool": tool_name, "result": res})
            tool_history.append(tool_name)
        except Exception as e:
            logger.warning(f"Failed to execute mock tool {tool_name}: {e}")
            evidence.append({"error": str(e)})

    llm = get_chat_model(temperature=LLM_TEMPERATURE, seed=LLM_SEED)
    if llm:
        llm_with_tools = llm.bind_tools(tools)
        prompt = [
            SystemMessage(content="You are an IT diagnostic agent. You MUST use tools to gather evidence before resolving issues."),
        ]
        if messages:
            prompt.extend(messages)
        else:
            prompt.append(HumanMessage(content=sanitized_query))
        try:
            response = llm_with_tools.invoke(prompt, config=config)
            new_messages = []
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    t_name, t_args, t_id = tool_call["name"], tool_call["args"], tool_call["id"]
                    try:
                        res = gateway.execute(user_context, t_name, **t_args)
                        evidence.append({"source": "diagnostic_tool", "tool": t_name, "result": res})
                        tool_history.append(t_name)
                        new_messages.append(response)
                        new_messages.append(ToolMessage(content=json.dumps(res), tool_call_id=t_id))
                    except Exception as e:
                        evidence.append({"error": str(e)})
                        new_messages.append(response)
                        new_messages.append(ToolMessage(content=str(e), tool_call_id=t_id))
            return {"evidence": evidence, "tool_history": tool_history, "messages": new_messages}
        except Exception as e:
            evidence.append({"error": str(e)})
            return {"evidence": evidence, "tool_history": tool_history}

    return {"evidence": evidence, "tool_history": tool_history}


def resolve_node(state: AgentState, config: RunnableConfig = None):
    evidence = list(state.get("evidence", []))
    sanitized_query = state.get("sanitized_query") or state.get("input", "")
    retrieval_score = float(state.get("retrieval_score", 0.0))
    user_context = state.get("user_context", {}) or {}
    tool_history = list(state.get("tool_history", []))

    logger.info(f"Resolve node processing query: '{sanitized_query}', similarity score: {retrieval_score}")

    # Below threshold: always escalate. Scope was already decided in
    # preprocess — reaching this node means the query IS in scope. A low
    # score is a knowledge-base gap, not evidence the topic doesn't belong;
    # there's no reliable way to distinguish "genuinely out of scope" from
    # "KB just doesn't cover this yet" at this point, so don't try.
    if retrieval_score < SIMILARITY_THRESHOLD:
        logger.info(f"Retrieval score {retrieval_score:.4f} below threshold {SIMILARITY_THRESHOLD}. Escalating.")
        return {"needs_handoff": True, "escalate": True, "status": "escalated"}

    llm = get_chat_model(temperature=LLM_TEMPERATURE, seed=LLM_SEED)
    if not llm:
        logger.warning("LLM model not available in resolve_node. Triggering handoff.")
        return {"needs_handoff": True, "escalate": True, "status": "escalated"}

    try:
        system_msg = (
            "You are an L1 IT helpdesk assistant. "
            "Provide concise, professional troubleshooting guidance. "
            "Only provide solutions supported by the retrieved knowledge base "
            "and diagnostic evidence. Do not invent troubleshooting steps."
        )
        messages = list(state.get("messages", []) or [])
        prompt = [SystemMessage(content=system_msg)]
        for m in messages:
            if isinstance(m, (HumanMessage, AIMessage)) and getattr(m, "content", ""):
                prompt.append(m)
        prompt.append(HumanMessage(content=f"Current Issue Details: {sanitized_query}\nEvidence: {json.dumps(evidence, default=str)}"))

        response = llm.invoke(prompt, config=config)
        answer_text = response.content if hasattr(response, "content") else str(response)

        if not is_response_from_knowledge_base(answer_text, evidence):
            logger.warning("LLM response failed knowledge base grounding check. Triggering handoff.")
            return {"needs_handoff": True, "escalate": True, "status": "escalated", "evidence": evidence}

        return {
            "messages": [response if isinstance(response, AIMessage) else AIMessage(content=answer_text)],
            "evidence": evidence,
            "needs_handoff": False,
            "escalate": False,
            "status": "resolved",
        }
    except Exception as e:
        logger.error(f"Error during LLM invocation in resolve_node: {e}")
        return {"needs_handoff": True, "escalate": True, "status": "escalated", "evidence": evidence}


_LEAK_PATTERNS = [
    r"system prompt\b",
    r"developer instructions\b",
    r"ignore all previous instructions\b",
    r"AKIA[0-9A-Z]{16}",
    r"-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",
    r"\bpassword\s*[:=]\s*['\"][^\s'\"]+['\"]",
    r"\bbearer\s+ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+",
    r"\bghp_[A-Za-z0-9_]{36}\b",
]
_LEAK_RE = re.compile("|".join(_LEAK_PATTERNS), re.IGNORECASE)


def verify_node(state: AgentState, config: RunnableConfig = None):
    """
    Active safety and compliance guardrail.
    Inspects generated response for system prompt disclosures, leaked credentials,
    or policy violations before presenting to the user.
    """
    messages = state.get("messages", []) or []
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            content = msg.content
            if _LEAK_RE.search(content):
                logger.warning("Verification guardrail failed: potential prompt or credential leak detected.")
                return {
                    "status": "escalated",
                    "escalate": True,
                    "needs_handoff": True,
                    "messages": [
                        AIMessage(
                            content="I have flagged this request for review by our engineering team to ensure technical accuracy and security. Escalating now."
                        )
                    ],
                }
            break

    return {"status": state.get("status", "resolved")}