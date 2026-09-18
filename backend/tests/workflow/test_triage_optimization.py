import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage
from src.workflow.nodes.triage import preprocess_node, classify_node


def test_preprocess_node_unified_extraction():
    """Verify preprocess_node extracts category, priority, and rationale in a single structured prompt."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content='{"sufficient": true, "question": "", "category": "network", "priority": "high", "rationale": "VPN outage blocking access"}'
    )

    state = {
        "input": "My VPN connects but fails to route any traffic to internal servers",
        "messages": [],
    }

    with patch("src.workflow.nodes.triage.get_chat_model", return_value=mock_llm), \
         patch("src.workflow.nodes.triage.is_it_support_query", return_value=True):
        res = preprocess_node(state)

        assert res.get("needs_clarification") is False
        assert res.get("out_of_scope") is False
        assert res.get("category") == "network"
        assert res.get("priority") == "HIGH"
        assert res.get("priority_rationale") == "VPN outage blocking access"
        assert res.get("search_query") is not None


def test_classify_node_fast_path_skips_redundant_llm():
    """Verify classify_node immediately reuses category/priority without calling the LLM."""
    state = {
        "category": "network",
        "priority": "HIGH",
        "priority_rationale": "VPN outage blocking access",
        "search_query": "My VPN connects but fails",
    }

    with patch("src.workflow.nodes.triage.get_chat_model") as mock_get_llm:
        res = classify_node(state)

        # Fast path should return immediately without obtaining or invoking chat model
        mock_get_llm.assert_not_called()
        assert res["category"] == "network"
        assert res["priority"] == "HIGH"
        assert res["priority_rationale"] == "VPN outage blocking access"


def test_classify_node_fallback_when_category_missing():
    """Verify classify_node falls back to LLM or keyword fallback when category is not pre-populated."""
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = MagicMock(
        content='{"category": "software", "priority": "medium", "rationale": "App crash"}'
    )

    state = {
        "category": None,
        "priority": None,
        "input": "Slack keeps crashing on startup",
    }

    with patch("src.workflow.nodes.triage.get_chat_model", return_value=mock_llm):
        res = classify_node(state)

        mock_llm.invoke.assert_called_once()
        assert res["category"] == "software"
        assert res["priority"] == "MEDIUM"


def test_is_gibberish_detection():
    """Verify is_gibberish accurately flags random keyboard mashing and nonsense."""
    from src.workflow.utils.guardrails import is_gibberish

    # Gibberish examples from user prompts
    assert is_gibberish("sibdbaskd") is True
    assert is_gibberish("hs dhwqud") is True
    assert is_gibberish("w efh whfdde") is True
    assert is_gibberish("ehfbwhe fuew few") is True
    assert is_gibberish("ewhf hew f ewf") is True
    assert is_gibberish("asdfghjkl") is True
    assert is_gibberish("qwertyuiop") is True

    # Legitimate queries
    assert is_gibberish("hey am facing wifi issues") is False
    assert is_gibberish("My VPN is disconnected error 800") is False
    assert is_gibberish("Password reset not working") is False
    assert is_gibberish("Dell laptop screen is flickering") is False


def test_gibberish_first_time_prompts_user():
    """Verify single gibberish turn prompts user for clear input without polluting search query."""
    state = {
        "input": "sibdbaskd",
        "messages": [
            HumanMessage(content="hey am facing wifi issues"),
            AIMessage(content="Can you describe what specifically is happening with your Wi-Fi?"),
        ],
    }
    res = preprocess_node(state)
    assert res.get("needs_clarification") is True
    assert res.get("sanitized_query") == ""
    assert res.get("search_query") == ""
    assert "didn't quite understand" in res["messages"][0].content


def test_consecutive_gibberish_terminates_cleanly_without_escalation():
    """Verify 2 consecutive gibberish inputs terminate cleanly without escalation or retrieval."""
    state = {
        "input": "hs dhwqud",
        "messages": [
            HumanMessage(content="hey am facing wifi issues"),
            AIMessage(content="Can you describe what specifically is happening with your Wi-Fi?"),
            HumanMessage(content="sibdbaskd"),
            AIMessage(content="I didn't quite understand that. Could you please provide a clear description?"),
        ],
    }
    res = preprocess_node(state)
    assert res.get("out_of_scope") is True
    assert res.get("needs_clarification") is False
    assert res.get("status") == "resolved"
    assert res.get("escalate") is False
    assert res.get("needs_handoff") is False
    assert "closing this session" in res["messages"][0].content

