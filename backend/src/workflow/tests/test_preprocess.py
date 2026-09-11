import pytest
from src.workflow.nodes.preprocess import preprocess_node
from src.workflow.state import AgentState
from src.workflow.utils.guardrails import sanitize_input


def test_preprocess_node_short_greeting_returns_clarification():
    # Prepare a minimal state with a short greeting
    state: AgentState = {
        "messages": [],
        "input": "hi",
        "needs_clarification": False,
        "escalate": False,
        "category": "",
        "evidence": [],
        "tool_history": [],
        "status": "",
        "user_context": {},
        "sanitized_query": "",
        "retrieval_score": 0.0,
        "needs_handoff": False,
    }
    result = preprocess_node(state)
    # Should ask for clarification
    assert result["needs_clarification"] is True
    assert isinstance(result["messages"][0].content, str)
    assert "Helpdesk Assistant" in result["messages"][0].content


def test_preprocess_node_normal_input_sanitizes_and_stores():
    raw_input = "Please reset my {{password}} now"
    state: AgentState = {
        "messages": [],
        "input": raw_input,
        "needs_clarification": False,
        "escalate": False,
        "category": "",
        "evidence": [],
        "tool_history": [],
        "status": "",
        "user_context": {},
        "sanitized_query": "",
        "retrieval_score": 0.0,
        "needs_handoff": False,
    }
    result = preprocess_node(state)
    # Should not request clarification
    assert result["needs_clarification"] is False
    # The sanitized query should be stored in the state
    assert state["sanitized_query"] == sanitize_input(raw_input)
    # The sanitized version should have brackets removed
    assert "{{" not in state["sanitized_query"] and "}}" not in state["sanitized_query"]
