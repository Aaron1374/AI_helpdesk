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
    pass # Implementation will be intercepted

@tool
def device_check(target_id: str) -> str:
    """Check the device compliance status for a given target ID."""
    pass # Implementation will be intercepted

tools = [vpn_check, device_check]

def diagnose_node(state: AgentState):
    evidence = state.get("evidence", [])
    tool_history = state.get("tool_history", [])
    user_context = state.get("user_context", {})
    messages = state.get("messages", [])
    
    llm = get_chat_model()
    if llm:
        llm_with_tools = llm.bind_tools(tools)
        
        prompt = [
            SystemMessage(content="You are an IT diagnostic agent. You MUST use tools to gather evidence before resolving issues."),
            HumanMessage(content=state.get('input', ''))
        ]
        # Include past tool messages if any
        prompt.extend(messages)
        
        try:
            response = llm_with_tools.invoke(prompt)
            # Route tool calls through Gateway
            if hasattr(response, "tool_calls") and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_name = tool_call["name"]
                    args = tool_call["args"]
                    tool_id = tool_call["id"]
                    
                    try:
                        res = gateway.execute(user_context, tool_name, **args)
                        evidence.append(res)
                        tool_history.append(tool_name)
                        tool_msg = ToolMessage(content=json.dumps(res), tool_call_id=tool_id)
                        messages.append(response) # Add AI message that called the tool
                        messages.append(tool_msg) # Add tool response
                    except Exception as e:
                        evidence.append({"error": str(e)})
                        tool_msg = ToolMessage(content=str(e), tool_call_id=tool_id)
                        messages.append(response)
                        messages.append(tool_msg)
                        
            return {"evidence": evidence, "tool_history": tool_history, "messages": messages}
        except Exception as e:
            evidence.append({"error": str(e)})
            return {"evidence": evidence}
    
    # Fallback mock logic if no API key
    try:
        res = gateway.execute(user_context, "vpn_check", target_id="mock123")
        evidence.append(res)
        tool_history.append("vpn_check")
    except Exception as e:
        evidence.append({"error": str(e)})

    return {"evidence": evidence, "tool_history": tool_history}

def resolve_node(state: AgentState):
    evidence = state.get("evidence", [])
    messages = list(state.get("messages", []))
    user_input = state.get("input", "")
    
    # Check if we have knowledge documents in evidence
    kb_docs = []
    for ev in evidence:
        if isinstance(ev, dict) and "documents" in ev:
            kb_docs.extend(ev["documents"])
            
    has_kb = len(kb_docs) > 0
    llm = get_chat_model()
    
    if llm:
        try:
            evidence_summary = json.dumps(evidence, default=str)
            if has_kb:
                system_prompt = (
                    "You are an AI IT Helpdesk Assistant. "
                    "Use the retrieved knowledge base evidence and diagnostic results to provide a clear, step-by-step resolution."
                )
                should_escalate = False
            else:
                system_prompt = (
                    "You are an AI IT Helpdesk Assistant. "
                    "Acknowledge the user's issue and provide initial basic troubleshooting advice if known. "
                    "Explicitly inform the user that a support ticket has been created and escalated to an L1 Support Engineer who will review and assist shortly."
                )
                should_escalate = True

            prompt = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Issue: {user_input}\nEvidence: {evidence_summary}")
            ]
            response = llm.invoke(prompt)
            return {"messages": [response], "escalate": should_escalate, "status": "escalated" if should_escalate else "resolved"}
        except Exception as e:
            return {
                "messages": [AIMessage(content="I have recorded your issue and created an escalated support ticket for an L1 Support Engineer to assist you.")],
                "escalate": True,
                "status": "escalated"
            }
    
    return {
        "messages": [AIMessage(content="I have recorded your issue and forwarded a ticket to our L1 Support Engineer team for assistance.")],
        "escalate": True,
        "status": "escalated"
    }

def verify_node(state: AgentState):
    return {"status": state.get("status", "resolved")}
