import unittest
from src.workflow.utils.guardrails import sanitize_input, is_response_from_knowledge_base, select_mock_tool

class TestGuardrails(unittest.TestCase):
    def test_sanitize_removes_template_and_dangerous(self):
        raw = "Hello {{user}}; DROP TABLE -- \n new line"
        cleaned = sanitize_input(raw)
        self.assertNotIn("{{", cleaned)
        self.assertNotIn("}}", cleaned)
        self.assertNotIn(";", cleaned)
        self.assertNotIn("--", cleaned)
        self.assertNotIn("\n", cleaned)
        self.assertTrue(len(cleaned.split()) <= 512)

    def test_is_response_from_knowledge_base_positive(self):
        answer = "The issue is described in document 12345 and resolved."
        evidence = [{"id": "12345", "content": "..."}]
        self.assertTrue(is_response_from_knowledge_base(answer, evidence))

    def test_is_response_from_knowledge_base_negative(self):
        answer = "No relevant docs."
        evidence = [{"id": "abc", "content": "..."}]
        self.assertFalse(is_response_from_knowledge_base(answer, evidence))

    def test_select_mock_tool_vpn(self):
        self.assertEqual(select_mock_tool("My vpn is down"), "vpn_check")

    def test_select_mock_tool_device(self):
        self.assertEqual(select_mock_tool("Device not responding"), "device_check")

    def test_select_mock_tool_none(self):
        self.assertIsNone(select_mock_tool("Something else"))

if __name__ == '__main__':
    unittest.main()
