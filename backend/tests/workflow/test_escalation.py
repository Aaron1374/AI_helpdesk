import pytest
from src.workflow.escalation import EscalationPolicy

def test_deterministic_escalation():
    # Test that certain categories or flags immediately return escalate=True
    policy = EscalationPolicy()
    
    assert policy.should_escalate({"category": "hardware_failure"}) is True
    assert policy.should_escalate({"category": "general_support", "escalate": True}) is True
    assert policy.should_escalate({"category": "general_support"}) is False
