from src.workflow.state import AgentState
from src.tools.gateway import ToolGateway
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
import json
from src.core.llm import get_chat_model

gateway = ToolGateway({"vpn_check", "device_check"})

# 1. Define tools using LangChain interface
@tool
def vpn_check(target_id: str) -> str:
    """Check the VPN status for a given target ID."""
    import json
    # Hardcoded mock response for VPN status
    return json.dumps({"status": "online", "mocked": True, "detail": "VPN is operational"})

@tool
def device_check(target_id: str) -> str:
    """Check the device compliance status for a given target ID."""
    import json
    # Hardcoded mock response for device compliance
    return json.dumps({"status": "compliant", "mocked": True, "detail": "Device meets compliance"})

tools = [vpn_check, device_check]

def diagnose_node(state: AgentState):
    evidence = list(state.get("evidence", []))
    tool_history = list(state.get("tool_history", []))
    user_context = state.get("user_context", {})
    messages = list(state.get("messages", []))
    user_input = (state.get("input", "") or "").lower()
    
    # Deterministic diagnostic tool execution based on keywords in query/context
    if any(kw in user_input for kw in ["vpn", "connect", "network", "remote", "wifi", "internet"]):
        try:
            res = gateway.execute(user_context, "vpn_check", target_id=user_context.get("user_id", "user_1"))
            if "vpn_check" not in tool_history:
                evidence.append({"tool": "vpn_check", "result": res})
                tool_history.append("vpn_check")
        except Exception as e:
            evidence.append({"tool": "vpn_check", "error": str(e)})

    if any(kw in user_input for kw in ["device", "laptop", "pc", "mac", "compliance", "os", "system", "install", "update"]):
        try:
            res = gateway.execute(user_context, "device_check", target_id=user_context.get("user_id", "user_1"))
            if "device_check" not in tool_history:
                evidence.append({"tool": "device_check", "result": res})
                tool_history.append("device_check")
        except Exception as e:
            evidence.append({"tool": "device_check", "error": str(e)})

    # Also invoke LLM with tools if available
    llm = get_chat_model()
    if llm:
        try:
            llm_with_tools = llm.bind_tools(tools)
            prompt = [
                SystemMessage(content="You are an IT diagnostic agent. Gather diagnostic evidence using tools when necessary."),
            ]
            prompt.extend(messages)
            prompt.append(HumanMessage(content=state.get('input', '')))
            
            response = llm_with_tools.invoke(prompt)
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    args = tool_call["args"]
                    tool_id = tool_call["id"]
                    if tool_name not in tool_history:
                        try:
                            res = gateway.execute(user_context, tool_name, **args)
                            evidence.append({"tool": tool_name, "result": res})
                            tool_history.append(tool_name)
                            tool_msg = ToolMessage(content=json.dumps(res), tool_call_id=tool_id)
                            messages.append(response)
                            messages.append(tool_msg)
                        except Exception as e:
                            evidence.append({"tool": tool_name, "error": str(e)})
        except Exception:
            pass

    return {"evidence": evidence, "tool_history": tool_history, "messages": messages}

# Minimum cosine-similarity score required to answer from the knowledge base.
RAG_SCORE_THRESHOLD = 0.72

def resolve_node(state: AgentState):
    evidence = state.get("evidence", [])
    messages = list(state.get("messages", []))
    user_input = (state.get("input", "") or "").strip()
    user_input_lower = user_input.lower()
    retrieval_score = state.get("retrieval_score", 0.0)

    # 1. Check if user is reporting failure of a previous resolution step
    failure_signals = ["didn't work", "did not work", "still not working", "still failing", "failed", "error persists", "didn't fix", "did not fix", "not working", "same error", "issue persists"]
    is_reporting_failure = any(sig in user_input_lower for sig in failure_signals)

    if is_reporting_failure and messages:
        # User indicates prior resolution failed -> analyze and escalate to engineer
        return {
            "messages": [
                AIMessage(
                    content=(
                        "I understand that the previous troubleshooting steps did not resolve your issue. "
                        "Based on the diagnostic checks and evidence analysis, I am creating a support ticket "
                        "and escalating this to an L1 Support Engineer for manual assistance."
                    )
                )
            ],
            "escalate": True,
            "needs_handoff": True,
            "status": "escalated",
        }

    # 2. Check if user is confirming resolution success
    success_signals = ["it worked", "fixed", "resolved", "working now", "thanks", "thank you", "all good", "solved"]
    is_reporting_success = any(sig in user_input_lower for sig in success_signals) and len(user_input.split()) < 8
    if is_reporting_success:
        return {
            "messages": [
                AIMessage(content="Great! I'm glad the resolution worked for you. Please reach out if you encounter any other issues!")
            ],
            "escalate": False,
            "needs_handoff": False,
            "status": "resolved",
        }

    # --- Threshold gate ---------------------------------------------------
    # If the RAG cosine score is below the threshold we have no reliable
    # knowledge-base coverage for this query.  Force escalation immediately.
    if retrieval_score < RAG_SCORE_THRESHOLD:
        return {
            "messages": [
                AIMessage(
                    content=(
                        f"I wasn't able to find a confident answer in the knowledge base "
                        f"for your query (confidence score: {retrieval_score:.2f}, "
                        f"threshold: {RAG_SCORE_THRESHOLD}). "
                        "I have created a support ticket and escalated this to an "
                        "L1 Support Engineer who will follow up with you shortly."
                    )
                )
            ],
            "escalate": True,
            "needs_handoff": True,
            "status": "escalated",
        }
    # ----------------------------------------------------------------------

    # Score is above threshold — collect knowledge docs & diagnostic results from evidence
    kb_docs = [
        ev for ev in evidence
        if isinstance(ev, dict)
        and (ev.get("type") in ("knowledge", "ticket") or "content" in ev or "documents" in ev or "title" in ev)
    ]
    has_kb = bool(kb_docs) or bool(evidence)

    llm = get_chat_model()

    if llm:
        try:
            evidence_summary = json.dumps(evidence, default=str)
            if has_kb:
                system_prompt = (
                    "You are an interactive AI IT Support Agent. "
                    "Answer ONLY using the retrieved knowledge base evidence and live diagnostic results below. "
                    "Do NOT use your own training knowledge. "
                    "Format your answer with clear step-by-step instructions. "
                    "At the end of your response, ALWAYS ask the user to verify if the suggested steps resolved their issue "
                    "(e.g., 'Please try these steps and let me know if this resolves your issue or if you need further assistance.')."
                )
                should_escalate = False
            else:
                system_prompt = (
                    "You are an AI IT Helpdesk Assistant. "
                    "Acknowledge the user's issue and inform them that a support ticket has been "
                    "created and escalated to an L1 Support Engineer who will review and assist shortly. "
                    "Do NOT attempt to answer or troubleshoot from your own training knowledge."
                )
                should_escalate = True

            prompt = [SystemMessage(content=system_prompt)]
            prompt.extend(messages)
            prompt.append(HumanMessage(content=f"Issue: {user_input}\nEvidence: {evidence_summary}"))
            response = llm.invoke(prompt)
            return {
                "messages": [response],
                "escalate": should_escalate,
                "needs_handoff": should_escalate,
                "status": "escalated" if should_escalate else "resolved",
            }
        except Exception:
            return {
                "messages": [AIMessage(content="I have recorded your issue and created an escalated support ticket for an L1 Support Engineer to assist you.")],
                "escalate": True,
                "needs_handoff": True,
                "status": "escalated",
            }

    return {
        "messages": [AIMessage(content="I have recorded your issue and forwarded a ticket to our L1 Support Engineer team for assistance.")],
        "escalate": True,
        "needs_handoff": True,
        "status": "escalated",
    }

def verify_node(state: AgentState):
    return {"status": state.get("status", "resolved")}
