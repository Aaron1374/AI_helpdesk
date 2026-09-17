# Walkthrough: LangGraph Flow Remediation & Optimization

We have completed the architectural overhaul of the LangGraph workflow across all three planned phases. All 22 automated unit and integration tests are passing in the live environment.

---

## What Changed Across the Phases

### Phase 1: Security Invariants, Retrieval Quality & Context Hygiene
* **Closed Injection Bypass in Confirmation Flow:**
  Updated [`graph.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/graph.py) so that `injection_pre_check` executes on **every single user message** before branching to `handle_confirmation`. An attacker can no longer bypass prompt injection defenses by sending malicious commands in response to confirmation prompts.
* **Separated Vector Search Query from Conversation History:**
  Added `search_query: str` to `AgentState` in [`state.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/state.py). In [`triage.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/triage.py), `_extract_search_query()` distills the core technical problem rather than concatenating the entire multi-turn conversation transcript into the vector search query.
* **Vector Evidence Deduplication:**
  Updated [`retrieval.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/retrieval.py) to query using `search_query` and deduplicate knowledge document chunks so retries do not accumulate redundant evidence.
* **Context Deduplication in Diagnostics:**
  Fixed [`resolution.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/resolution.py) to avoid duplicating all messages twice in `diagnose_node`.
* **Eliminated Redundant Mock Tool Call:**
  Removed the duplicate invocation of `select_mock_tool` in `resolve_node` since `diagnose_node` already runs tools prior to resolution.
* **Protected Zero-Width Confirmation Tokens:**
  Updated `sanitize_input()` in [`guardrails.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/utils/guardrails.py) to preserve `CONFIRM_MARKER` and `CONFIRM_FINAL_MARKER`.

---

### Phase 2: State Machine Resilience, Retry Routing & Active Verification
* **Resilient Confirmation Retry Routing:**
  Updated `check_confirmation_reply()` in [`graph.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/graph.py) and [`confirmation.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/confirmation.py). When a user replies *"No, still broken"*, the flow now routes directly into retrieval/diagnosis with the user's updated diagnostic context rather than wiping out the ticket's category and priority.
* **Activated `verify_node` Output Guardrail:**
  Replaced the dead no-op `verify_node` in [`resolution.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/resolution.py) with an active safety check that scans generated solutions for prompt leakage (e.g. system instruction disclosures) and secret/key leaks. Added conditional routing in [`graph.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/graph.py) to route to `escalate` if flagged.

---

### Phase 3: Latency & Cost Optimization (Triage Consolidation)
* **Consolidated Triage & Classification:**
  Updated `preprocess_node` in [`triage.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/triage.py) to evaluate sufficiency, category, priority, and rationale in a **single structured LLM call**.
  Added a fast-path bypass in `classify_node` that reuses the triage assessment without triggering a redundant second LLM call, reducing token consumption and latency per turn.

---

## Verification & Test Results

The full test suite was executed inside the live container environment:
```powershell
docker exec -e PYTHONPATH=/app helpdesk-backend-1 pytest tests/ -v
```

### Results Summary
```
============================= test session starts ==============================
collected 22 items

tests/core/test_audit.py::test_audit_events_capture_trace_id PASSED      [  4%]
tests/test_basic.py::test_health_endpoint PASSED                         [  9%]
tests/test_chunker.py::test_chunk_short_article PASSED                   [ 13%]
tests/test_chunker.py::test_chunk_validation_empty_title PASSED          [ 18%]
tests/test_chunker.py::test_chunk_validation_empty_content PASSED        [ 22%]
tests/test_chunker.py::test_chunking_representative_kb_articles PASSED   [ 27%]
tests/tools/test_gateway.py::test_tool_gateway_rejects_unauthorized PASSED [ 31%]
tests/workflow/test_escalation.py::test_deterministic_escalation PASSED  [ 36%]
tests/workflow/test_hallucination.py::test_ai_does_not_invent_system_state PASSED [ 40%]
tests/workflow/test_injection.py::test_prompt_injection_defense PASSED   [ 45%]
tests/workflow/test_injection.py::test_injection_blocked_even_during_confirmation_state PASSED [ 50%]
tests/workflow/test_rag_pipeline.py::test_sanitize_input PASSED          [ 54%]
tests/workflow/test_rag_pipeline.py::test_select_mock_tool PASSED        [ 59%]
tests/workflow/test_rag_pipeline.py::test_is_response_from_knowledge_base PASSED [ 63%]
tests/workflow/test_rag_pipeline.py::test_resolve_node_below_threshold PASSED [ 68%]
tests/workflow/test_rag_pipeline.py::test_resolve_node_above_threshold PASSED [ 72%]
tests/workflow/test_rag_pipeline.py::test_out_of_scope_query_rejection PASSED [ 77%]
tests/workflow/test_rag_pipeline.py::test_verify_node_catches_prompt_leak PASSED [ 81%]
tests/workflow/test_rag_pipeline.py::test_verify_node_passes_clean_response PASSED [ 86%]
tests/workflow/test_retrieval.py::test_retrieval_respects_rbac PASSED    [ 90%]
tests/workflow/test_retrieval.py::test_similarity_is_evidence_not_fact PASSED [ 95%]
tests/workflow/test_takeover.py::test_human_takeover_prevents_ai PASSED  [100%]

======================= 22 passed, 6 warnings in 13.01s ========================
```

Key validations:
1. `test_injection_blocked_even_during_confirmation_state`: Verified prompt injections sent during confirmation prompt are blocked and escalated.
2. `test_verify_node_catches_prompt_leak`: Verified system prompt disclosures or credential leaks in AI answers are intercepted before delivery.
3. `test_verify_node_passes_clean_response`: Verified clean troubleshooting answers proceed without friction.
4. Existing RBAC, chunking, hallucination, and escalation tests continue to pass 100%.
