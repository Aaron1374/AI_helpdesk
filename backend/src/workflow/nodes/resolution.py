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
    messages = state.get("messages", [])
    
    if not evidence:
        return {"messages": [AIMessage(content="I cannot resolve this issue without diagnostic evidence.")], "escalate": True}
        
    llm = get_chat_model()
    if llm:
        try:
            prompt = [
                SystemMessage(content="You are an IT helpdesk agent. Use the evidence provided to propose a resolution."),
                HumanMessage(content=state.get("input", "") or "Please review the diagnostic evidence and propose a resolution.")
            ]
            prompt.extend(messages)
            
            response = llm.invoke(prompt)
            return {"messages": [response], "escalate": False}
        except Exception as e:
            return {"messages": [AIMessage(content=f"AI Error: {str(e)}")], "escalate": True}
    
    return {"messages": [AIMessage(content=f"Based on evidence {evidence}, I have resolved your issue.")], "escalate": False}

def verify_node(state: AgentState):
    return {"status": "resolved"}
