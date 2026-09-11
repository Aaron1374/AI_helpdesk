# Unit tests for workflow guardrails utilities

import pytest
from src.workflow.utils.guardrails import sanitize_input, is_response_from_knowledge_base, select_mock_tool


def test_sanitize_input_removes_brackets_and_truncates():
    # Input with double curly braces and extra characters
    raw = "Please reset my {{password}} and also include a very long text " + "x" * 2000
    sanitized = sanitize_input(raw)
    # Ensure brackets are removed
    assert "{{" not in sanitized and "}}" not in sanitized
    # Token count (approx) should be <= 512 tokens; we approximate by length
    assert len(sanitized.split()) <= 512


def test_is_response_from_knowledge_base_detects_id():
    answer = "The device status is ok. Document ID: doc12345"
    docs = [{"id": "doc12345", "content": "..."}]
    assert is_response_from_knowledge_base(answer, docs) is True
    # Negative case
    answer2 = "No relevant document referenced."
    assert is_response_from_knowledge_base(answer2, docs) is False


def test_select_mock_tool_returns_correct_tool():
    assert select_mock_tool("I need a vpn check for my office") == "vpn_check"
    assert select_mock_tool("My device is not working") == "device_check"
    assert select_mock_tool("Just a general query") is None
