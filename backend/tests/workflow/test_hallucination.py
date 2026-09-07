import pytest
from backend.src.workflow.nodes.resolution import resolve_node

def test_ai_does_not_invent_system_state():
    # Test without evidence
    state_no_evidence = {"evidence": []}
    result = resolve_node(state_no_evidence)
    
    assert result.get("escalate") is True
    assert "cannot resolve this issue without diagnostic evidence" in result["messages"][0].content
    
    # Test with evidence
    state_with_evidence = {"evidence": [{"tool": "vpn_check", "status": "executed"}]}
    result_valid = resolve_node(state_with_evidence)
    
    assert result_valid.get("escalate") is not True
    assert "resolved" in result_valid["messages"][0].content.lower()
