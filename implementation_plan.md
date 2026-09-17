# Comprehensive Workflow & UX Optimization Plan

## Problem Statement & Objective
Auditing the end-to-end helpdesk flow revealed several high-impact UX flaws and state consistency gaps:
1. **Context Amnesia in Multi-Turn Troubleshooting:** `resolve_node` only accepts the single current query and evidence, ignoring conversation history. When a user provides feedback on a failed step, the LLM cannot see what it suggested previously and may repeat identical steps.
2. **Silent Escalation Bug ("The Ghost Bot"):** In `handoff_node`, the code checks `has_ai_response = any(isinstance(m, AIMessage) and m.content for m in msgs)`. In any conversation past Turn 1, `msgs` already has an older `AIMessage`. As a result, no escalation message is appended, and the assistant sends zero messages back, appearing frozen or dead.
3. **State Loss Across HTTP Requests:** Every incoming message initializes `initial_state` in `conversations.py` with `"category": ""`. Any classification established in Turn 1 is forgotten in Turn 2, causing tickets escalated downstream to lose their category and priority.
4. **Missing Ticket Reference Transparency:** Users who are escalated are never given a ticket ID to reference.
5. **Guardrail Overhead & PII Leaks:** `injection_pre_check_node` calls Gemini on every user message, adding latency and consuming rate-limited quota, while `verify_node` lacks sensitive credential pattern detection (e.g. `password=`, `bearer tokens`).

---

## Phase Breakdown

### Phase 1: UX Polish & Multi-Turn Context Hygiene
* **Fix Multi-Turn Context in [`resolve_node`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/resolution.py):**
  * Pass bounded conversation history (`messages`) to `resolve_node` prompt so the LLM understands prior troubleshooting steps and user feedback.
* **Eliminate Silent Drop in [`handoff_node`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/handoff.py):**
  * Remove the broken `has_ai_response` check; ensure that whenever `handoff_node` executes, an explicit, user-friendly escalation message is appended to `messages` for that turn.
* **Ticket ID Transparency in [`conversations.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/api/conversations.py):**
  * When an escalated ticket is created or updated, inject the ticket reference number (e.g. `Ticket #<uuid[:8]>`) into the handoff message so the user has an immediate tracking reference.

---

### Phase 2: State Persistence & Metadata Retention Across HTTP Turns
* **Category & Priority Retention in [`conversations.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/api/conversations.py):**
  * Retrieve previously established `category`, `priority`, and `priority_rationale` from existing tickets or the previous turn's state before initializing `initial_state`.
  * Ensure confirmation retry turns do not wipe out existing ticket classification metadata.
* **Consistent State Flow in [`confirmation.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/confirmation.py):**
  * Ensure retry queries properly carry forward the original technical problem while attaching user-provided retry feedback.

---

### Phase 3: Guardrail Hardening & Latency Optimization
* **Deterministic Fast Pre-Filter in [`intake.py`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/intake.py):**
  * Add instant regex checks for blatant prompt injection patterns (`ignore all previous instructions`, `system prompt`, `dan mode`, `developer mode`) to escalate immediately without waiting for an LLM call.
  * For standard, benign helpdesk requests, allow fast, secure progression while falling back to the LLM classifier for ambiguous inputs.
* **Expanded Leak & Credential Detection in [`verify_node`](file:///c:/Users/AaronNeilRebello/Desktop/Evaluation/helpdesk/backend/src/workflow/nodes/resolution.py):**
  * Expand `_LEAK_PATTERNS` to detect plaintext passwords (`password=`, `passwd:`), private keys (`BEGIN PRIVATE KEY`), and bearer tokens in generated solutions, sanitizing or escalating if found.
* **Helpful Knowledge Gap Escalation:**
  * When grounding fails in `resolve_node`, provide an empathetic explanation informing the user that verified steps aren't in the knowledge base, rather than an abrupt refusal.

---

## User Review Required

> [!NOTE]
> All changes are backward-compatible with existing API contracts and UI expectations. No database schema migrations are required.

---

## Verification Plan

### Automated Tests
1. **Multi-Turn Context Test:** Verify `resolve_node` correctly receives history messages and doesn't repeat already attempted steps.
2. **Handoff Message Guarantee Test:** Verify `handoff_node` always appends an `AIMessage` even when history already contains prior assistant responses.
3. **Category Persistence Test:** Verify `conversations.py` maintains category/priority across 2+ turns without degradation to `"General Support"`.
4. **Guardrail Tests:** Verify injection regex catches blatant attacks instantly, and `verify_node` catches simulated password or token leaks.
5. **Full Regression Test:** Run all 29 existing tests inside Docker (`docker exec -e PYTHONPATH=/app helpdesk-backend-1 pytest tests/ -v`) to ensure zero regressions.
