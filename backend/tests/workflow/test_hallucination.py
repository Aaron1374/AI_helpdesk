
# pyrefly: ignore [missing-import]
import pytest
from unittest.mock import patch, MagicMock
# pyrefly: ignore [missing-import]
from src.workflow.nodes.resolution import resolve_node

def test_ai_does_not_invent_system_state():
    # Test without evidence or score below threshold -> escalate / handoff
    state_no_evidence = {"retrieval_score": 0.20, "evidence": []}
    result = resolve_node(state_no_evidence)
    
    assert result.get("escalate") is True
    assert result.get("needs_handoff") is True
    assert result.get("status") == "escalated"
    
    # Test with valid evidence and high score -> resolved
    state_with_evidence = {
        "input": "VPN status check",
        "sanitized_query": "VPN status check",
        "retrieval_score": 0.85,
        "evidence": [{"source": "diagnostic_tool", "tool": "vpn_check", "result": {"status": "connected"}}]
    }
    
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="VPN diagnostic result: connected. Resolved.")
    
    with patch("src.workflow.nodes.resolution.get_chat_model", return_value=mock_llm):
        result_valid = resolve_node(state_with_evidence)
        assert result_valid.get("escalate") is not True
        assert result_valid.get("needs_handoff") is False
        assert result_valid.get("status") == "resolved"
