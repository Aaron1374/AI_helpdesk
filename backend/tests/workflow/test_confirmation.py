import pytest
from unittest.mock import patch, MagicMock
from langchain_core.messages import AIMessage, HumanMessage

from src.workflow.constants import CONFIRM_MARKER, CONFIRM_FINAL_MARKER
from src.workflow.nodes.confirmation import (
    present_confirmation_node,
    handle_confirmation_node,
    _wants_escalation,
    _classify_confirmation_reply,
)
from src.workflow.graph import app as graph_app


def test_wants_escalation_detection():
    assert _wants_escalation("Can I please talk to a human?") is True
    assert _wants_escalation("transfer me to an engineer") is True
    assert _wants_escalation("escalate this ticket") is True
    assert _wants_escalation("I want a real person") is True
    assert _wants_escalation("Yes, that fixed it") is False
    assert _wants_escalation("Still not working") is False


def test_classify_confirmation_reply_deterministic():
    # Direct yes
    assert _classify_confirmation_reply("1") == "yes"
    assert _classify_confirmation_reply("Yes, all fixed!") == "yes"
    assert _classify_confirmation_reply("It works now, thanks") == "yes"

    # Direct no
    assert _classify_confirmation_reply("2") == "no"
    assert _classify_confirmation_reply("No, still having the issue") == "no"
    assert _classify_confirmation_reply("didn't work") == "no"

    # Explicit escalation ask
    assert _classify_confirmation_reply("connect me to a representative") == "escalate"


def test_handle_confirmation_resolves_on_yes():
    state = {
        "input": "1 - fixed it!",
        "messages": [AIMessage(content=f"Did that resolve it?\n{CONFIRM_MARKER}")],
    }
    result = handle_confirmation_node(state)
    assert result.get("confirmation_decision") == "resolved"
    assert result.get("status") == "resolved"


def test_handle_confirmation_escalates_on_explicit_ask():
    state = {
        "input": "I need to talk to an engineer right now",
        "messages": [AIMessage(content=f"Did that resolve it?\n{CONFIRM_MARKER}")],
    }
    result = handle_confirmation_node(state)
    assert result.get("confirmation_decision") == "escalate"
    assert result.get("escalate") is True
    assert result.get("needs_handoff") is True
    assert result.get("status") == "escalated"


def test_handle_confirmation_retries_on_first_no():
    state = {
        "input": "2 - still broken",
        "messages": [
            HumanMessage(content="VPN disconnected error 404"),
            AIMessage(content=f"Did that resolve it?\n{CONFIRM_MARKER}"),
        ],
    }
    result = handle_confirmation_node(state)
    assert result.get("confirmation_decision") == "retry"
    assert "VPN disconnected" in result.get("search_query", "")


def test_handle_confirmation_escalates_on_second_no():
    state = {
        "input": "No, still broken",
        "messages": [
            HumanMessage(content="VPN disconnected error 404"),
            AIMessage(content=f"Updated fix.\n{CONFIRM_FINAL_MARKER}"),
        ],
    }
    result = handle_confirmation_node(state)
    assert result.get("confirmation_decision") == "escalate"
    assert result.get("escalate") is True
    assert result.get("needs_handoff") is True
    assert result.get("status") == "escalated"


@pytest.mark.asyncio
async def test_confirmation_graph_retry_preserves_category_priority():
    from unittest.mock import AsyncMock

    initial_retry_state = {
        "input": "No, still having the problem",
        "awaiting_confirmation_reply": True,
        "category": "network",
        "priority": "HIGH",
        "priority_rationale": "Critical network outage for user",
        "messages": [
            HumanMessage(content="My VPN is throwing error 404"),
            AIMessage(content=f"Did that resolve the issue?\n{CONFIRM_MARKER}"),
        ],
        "evidence": [],
        "tool_history": [],
        "retrieval_score": 0.85,
        "status": "awaiting_confirmation",
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(content="Here is the second troubleshooting method for VPN.")

    with patch("src.core.llm.get_chat_model", return_value=mock_llm), \
         patch("src.workflow.nodes.resolution.get_chat_model", return_value=mock_llm), \
         patch("src.workflow.nodes.retrieval.RetrievalService.get_similar_documents", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = ([{"title": "VPN Guide", "content": "Troubleshoot VPN"}], 0.88)
        output = await graph_app.ainvoke(initial_retry_state)

        # Ensure original category and priority were preserved and NOT overwritten
        assert output.get("category") == "network"
        assert output.get("priority") == "HIGH"
        assert output.get("priority_rationale") == "Critical network outage for user"
