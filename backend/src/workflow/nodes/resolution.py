import json
import logging
from typing import Dict, Any

from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from src.workflow.state import AgentState
from src.tools.gateway import ToolGateway
from src.core.llm import get_chat_model
from src.workflow.constants import SIMILARITY_THRESHOLD, LLM_TEMPERATURE, LLM_SEED
from src.workflow.utils.guardrails import select_mock_tool, is_response_from_knowledge_base

logger = logging.getLogger(__name__)

gateway = ToolGateway({"vpn_check", "device_check"})

# 1. Define tools using LangChain interface
@tool
def vpn_check(target_id: str) -> str:
    """Check the VPN status for a given target ID."""
    pass # Implementation will be intercepted

@tool
def device_check(target_id: str) -> str:
    """Check the device compliance status for a given target ID."""
    pass # Implementation will be intercepted

tools = [vpn_check, device_check]

def diagnose_node(state: AgentState):
    evidence = list(state.get("evidence", []))
    tool_history = list(state.get("tool_history", []))
    user_context = state.get("user_context", {}) or {}
    messages = list(state.get("messages", []))
    sanitized_query = state.get("sanitized_query") or state.get("input", "")
    
    # Check if a tool should be executed based on query keyword matching
    tool_name = select_mock_tool(sanitized_query)
    if tool_name and tool_name not in tool_history:
        try:
            res = gateway.execute(user_context, tool_name, target_id="mock123")
            evidence.append({"source": "diagnostic_tool", "tool": tool_name, "result": res})
            tool_history.append(tool_name)
            logger.info(f"Diagnose node executed mock tool: {tool_name}")
        except Exception as e:
            logger.warning(f"Failed to execute mock tool {tool_name}: {e}")
            evidence.append({"error": str(e)})

    llm = get_chat_model(temperature=LLM_TEMPERATURE, seed=LLM_SEED)
    if llm:
        llm_with_tools = llm.bind_tools(tools)
        prompt = [
            SystemMessage(content="You are an IT diagnostic agent. You MUST use tools to gather evidence before resolving issues."),
            HumanMessage(content=sanitized_query)
        ]
        prompt.extend(messages)
        
        try:
            response = llm_with_tools.invoke(prompt)
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    t_name = tool_call["name"]
                    t_args = tool_call["args"]
                    t_id = tool_call["id"]
                    
                    try:
                        res = gateway.execute(user_context, t_name, **t_args)
                        evidence.append({"source": "diagnostic_tool", "tool": t_name, "result": res})
                        tool_history.append(t_name)
                        tool_msg = ToolMessage(content=json.dumps(res), tool_call_id=t_id)
                        messages.append(response)
                        messages.append(tool_msg)
                    except Exception as e:
                        evidence.append({"error": str(e)})
                        tool_msg = ToolMessage(content=str(e), tool_call_id=t_id)
                        messages.append(response)
                        messages.append(tool_msg)
                        
            return {"evidence": evidence, "tool_history": tool_history, "messages": messages}
        except Exception as e:
            evidence.append({"error": str(e)})
            return {"evidence": evidence, "tool_history": tool_history}

    return {"evidence": evidence, "tool_history": tool_history}


def resolve_node(state: AgentState):
    evidence = list(state.get("evidence", []))
    sanitized_query = state.get("sanitized_query") or state.get("input", "")
    retrieval_score = float(state.get("retrieval_score", 0.0))
    user_context = state.get("user_context", {}) or {}
    tool_history = list(state.get("tool_history", []))

    logger.info(f"Resolve node processing query: '{sanitized_query}', similarity score: {retrieval_score}")

    # 1. Similarity Threshold Enforcement (Cutoff = 0.72)
    if retrieval_score < SIMILARITY_THRESHOLD:
        logger.info(f"Retrieval score {retrieval_score} below threshold {SIMILARITY_THRESHOLD}. Requesting handoff.")
        return {
            "needs_handoff": True,
            "escalate": True,
            "status": "escalated"
        }

    # 2. Dynamic Tool Check if not executed in diagnose node
    tool_name = select_mock_tool(sanitized_query)
    if tool_name and tool_name not in tool_history:
        try:
            res = gateway.execute(user_context, tool_name, target_id="mock123")
            evidence.append({"source": "diagnostic_tool", "tool": tool_name, "result": res})
            tool_history.append(tool_name)
            logger.info(f"Resolve node executed mock tool: {tool_name}")
        except Exception as e:
            logger.warning(f"Error executing tool {tool_name} in resolve_node: {e}")
            evidence.append({"error": str(e)})

    # 3. Deterministic LLM Invocation
    llm = get_chat_model(temperature=LLM_TEMPERATURE, seed=LLM_SEED)
    if not llm:
        logger.warning("LLM model not available in resolve_node. Triggering handoff.")
        return {
            "needs_handoff": True,
            "escalate": True,
            "status": "escalated"
        }

    try:
        system_msg = (
            "You are an AI IT Helpdesk Assistant. Use ONLY the provided knowledge-base documents and any mock tool results. "
            "Do NOT fabricate information or rely on internal model knowledge."
        )
        user_msg = f"Issue: {sanitized_query}\nEvidence: {json.dumps(evidence, default=str)}"
        prompt = [SystemMessage(content=system_msg), HumanMessage(content=user_msg)]

        response = llm.invoke(prompt)
        answer_text = response.content if hasattr(response, "content") else str(response)

        # 4. Guardrail Grounding Check
        if not is_response_from_knowledge_base(answer_text, evidence):
            logger.warning("LLM response failed knowledge base grounding check. Triggering handoff.")
            return {
                "needs_handoff": True,
                "escalate": True,
                "status": "escalated",
                "evidence": evidence
            }

        logger.info("Resolved issue successfully with grounded RAG answer.")
        return {
            "messages": [response if isinstance(response, AIMessage) else AIMessage(content=answer_text)],
            "evidence": evidence,
            "needs_handoff": False,
            "escalate": False,
            "status": "resolved"
        }
    except Exception as e:
        logger.error(f"Error during LLM invocation in resolve_node: {e}")
        return {
            "needs_handoff": True,
            "escalate": True,
            "status": "escalated",
            "evidence": evidence
        }


def verify_node(state: AgentState):
    return {"status": state.get("status", "resolved")}
