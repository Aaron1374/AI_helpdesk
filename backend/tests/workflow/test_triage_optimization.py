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
