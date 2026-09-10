import pytest
from unittest.mock import patch, MagicMock
from src.workflow.utils.guardrails import sanitize_input, is_response_from_knowledge_base, select_mock_tool
from src.workflow.nodes.resolution import resolve_node
from src.workflow.nodes.triage import preprocess_node
from src.workflow.constants import SIMILARITY_THRESHOLD

def test_sanitize_input():
    # Test Jinja template stripping
    raw_jinja = "My issue is {{ user.password }} when logging in"
    sanitized = sanitize_input(raw_jinja)
    assert "{{ user.password }}" not in sanitized
    assert "My issue is" in sanitized

    # Test SQL injection character stripping
    raw_sql = "My issue is VPN not working; DROP TABLE users; --"
    sanitized_sql = sanitize_input(raw_sql)
    assert ";" not in sanitized_sql
    assert "--" not in sanitized_sql
    assert "VPN not working" in sanitized_sql

    # Test truncation
    long_text = "word " * 600
    sanitized_long = sanitize_input(long_text)
    assert len(sanitized_long.split()) <= 512


def test_select_mock_tool():
    assert select_mock_tool("VPN connection error") == "vpn_check"
    assert select_mock_tool("My network connection is failing") == "vpn_check"
    assert select_mock_tool("Laptop compliance issue") == "device_check"
    assert select_mock_tool("Device status check") == "device_check"
    assert select_mock_tool("Password reset request") is None


def test_is_response_from_knowledge_base():
    evidence = [
        {"type": "knowledge", "title": "VPN Troubleshooting Guide", "content": "Restart Cisco AnyConnect"}
    ]
    # Cited response
    valid_answer = "Based on the VPN Troubleshooting Guide, restart Cisco AnyConnect."
    assert is_response_from_knowledge_base(valid_answer, evidence) is True

    # Refusal response
    refusal_answer = "I don't know how to solve this issue based on the provided documents."
    assert is_response_from_knowledge_base(refusal_answer, evidence) is False

    # Empty evidence
    assert is_response_from_knowledge_base(valid_answer, []) is False


def test_resolve_node_below_threshold():
    state = {
        "input": "Obscure error code 9999",
        "sanitized_query": "Obscure error code 9999",
        "retrieval_score": 0.50, # Below 0.72 threshold
        "evidence": []
    }
    result = resolve_node(state)
    assert result.get("needs_handoff") is True
    assert result.get("escalate") is True
    assert result.get("status") == "escalated"


def test_resolve_node_above_threshold():
    state = {
        "input": "How to connect VPN?",
        "sanitized_query": "How to connect VPN?",
        "retrieval_score": 0.88,
        "evidence": [
            {
                "source": "knowledge_and_incidents",
                "documents": [
                    {"type": "knowledge", "title": "VPN Setup", "content": "Use Cisco AnyConnect software."}
                ]
            }
        ]
    }
    
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Follow the VPN Setup guide using Cisco AnyConnect software.")
    
    with patch("src.workflow.nodes.resolution.get_chat_model", return_value=mock_llm):
        result = resolve_node(state)
        assert result.get("needs_handoff") is False
        assert result.get("escalate") is False
        assert result.get("status") == "resolved"
        assert len(result.get("messages")) == 1


def test_out_of_scope_query_rejection():
    state = {
        "input": "My zomato delivery isn't delivered yet",
    }
    result = preprocess_node(state)
    assert result.get("out_of_scope") is True
    assert result.get("status") == "resolved"
    assert len(result.get("messages")) == 1
    assert "IT support" in result["messages"][0].content

