import json
import pytest
from unittest.mock import MagicMock, patch

# Import the resolve_node function and AgentState
from src.workflow.nodes.resolution import resolve_node

# Helper: a dummy state class resembling the project's AgentState structure
class DummyState(dict):
    """Simple dict subclass to mimic AgentState for tests."""
    pass

# Mock LLM that returns a deterministic response with a .content attribute
class MockLLM:
    def __init__(self, response_content="Resolved answer with citation"):
        self.response_content = response_content
        self.temperature = None
        self.seed = None
    def bind_tools(self, tools):
        return self
    def invoke(self, prompt):
        mock_resp = MagicMock()
        mock_resp.content = self.response_content
        return mock_resp

@pytest.fixture
def base_state():
    """Create a minimal state expected by resolve_node."""
    return DummyState({
        "sanitized_query": "User cannot connect to VPN",
        "retrieval_score": 0.8,
        "evidence": [],
        "user_context": {},
        "needs_handoff": False,
    })

def test_resolution_successful(base_state):
    """When retrieval score is above the threshold and guard passes, node resolves."""
    with patch("src.workflow.nodes.resolution.select_mock_tool", return_value=None), \
         patch("src.workflow.nodes.resolution.is_response_from_knowledge_base", return_value=True), \
         patch("src.workflow.nodes.resolution.get_chat_model", return_value=MockLLM()):
        result = resolve_node(base_state)
        assert result["status"] == "resolved"
        assert not result["escalate"]
        assert "answer" in result
        assert base_state["needs_handoff"] is False

def test_resolution_score_below_threshold(base_state):
    """Score below similarity threshold should trigger escalation."""
    base_state["retrieval_score"] = 0.5  # below typical 0.72
    with patch("src.workflow.nodes.resolution.get_chat_model", return_value=MockLLM()):
        result = resolve_node(base_state)
        assert result["status"] == "escalated"
        assert result["escalate"]
        assert base_state["needs_handoff"] is True

def test_resolution_guard_failure(base_state):
    """Guard returning False forces escalation even if score is high."""
    with patch("src.workflow.nodes.resolution.select_mock_tool", return_value=None), \
         patch("src.workflow.nodes.resolution.is_response_from_knowledge_base", return_value=False), \
         patch("src.workflow.nodes.resolution.get_chat_model", return_value=MockLLM()):
        result = resolve_node(base_state)
        assert result["status"] == "escalated"
        assert result["escalate"]
        assert base_state["needs_handoff"] is True

def test_resolution_tool_execution(base_state):
    """When a mock tool is selected, its result should be added to evidence."""
    mock_tool_result = {"status": "online", "mocked": True, "detail": "VPN is operational"}
    mock_gateway = MagicMock()
    mock_gateway.execute.return_value = mock_tool_result
    with patch("src.workflow.nodes.resolution.select_mock_tool", return_value="vpn_check"), \
         patch("src.workflow.nodes.resolution.gateway", mock_gateway), \
         patch("src.workflow.nodes.resolution.is_response_from_knowledge_base", return_value=True), \
         patch("src.workflow.nodes.resolution.get_chat_model", return_value=MockLLM()):
        result = resolve_node(base_state)
        # Evidence should contain the mocked tool result
        assert any(item == mock_tool_result for item in result["evidence"])
        assert result["status"] == "resolved"
        assert not result["escalate"]
