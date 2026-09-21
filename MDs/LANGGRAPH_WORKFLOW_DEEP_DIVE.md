# LangGraph AI Workflow — Deep Dive

> Last reviewed: 2026-09-21 · Branch: `ved`

How the AI L1 helpdesk conversation engine works: how a user message travels node-by-node through the LangGraph state machine, what each node does, and how information flows from one node to the next.

---

## 1. TL;DR

- **One graph, one message turn.** Every employee chat message triggers **one full graph invocation** (`graph_app.ainvoke(...)` in `conversations.py`). The graph is a state machine, not a long-lived agent.
- **Shared state object.** All nodes read/write a single `AgentState` dict. A node returns a **partial dict of updates**; LangGraph merges it into the state and passes the merged state to the next node. That merge is *the* mechanism of node-to-node information flow.
- **Conditional edges are the routers.** Plain edges (`classify → retrieve`) are unconditional. `add_conditional_edges` attach a Python function to a node that inspects the state and returns the name of the next node (or `END`).
- **Escalation is centralized.** `EscalationPolicy.should_escalate(state)` is consulted by multiple routers — any node can set `escalate`/`needs_handoff` flags, and the *next router* diverts to `escalate → human → END`.
- **Cross-turn memory lives outside the graph.** The graph is stateless between invocations. Continuation (the "did that fix it?" loop) works because the API layer persists messages in Postgres and re-feeds them as `messages` on the next invocation, plus a persisted `awaiting_confirmation_reply` flag.

```
intake → injection_pre_check → preprocess → classify → retrieve → diagnose
       → resolve → verify → present_confirmation → END
                        (any router can divert → escalate → human → END)
       (next turn, if awaiting confirmation → handle_confirmation → retry/escalate/END)
```

---

## 2. The State — `AgentState` (`state.py`)

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]   # ← REDUCER
    input: str                      # raw user message for this turn
    sanitized_query: str            # cleaned transcript-aware query
    search_query: str               # focused query for vector retrieval
    needs_clarification: bool       # preprocess asked a follow-up question
    escalate: bool                  # AI/router decided to escalate
    needs_handoff: bool             # resolution failed / grounding failed
    out_of_scope: bool              # non-IT topic
    retrieval_score: float          # best similarity score from pgvector
    category: str                   # access/network/hardware/...
    priority: str                   # CRITICAL/HIGH/MEDIUM/LOW
    priority_rationale: str
    evidence: List[dict]            # retrieved docs + tool results + errors
    tool_history: List[str]         # diagnostic tools already run (dedup)
    status: str                     # resolved / escalated / human_takeover / awaiting_confirmation
    user_context: Dict[str, Any]    # {id, email, role, department} from JWT auth
    confirmation_decision: str      # "" | "retry" | "escalate" | "resolved"
    awaiting_confirmation_reply: bool
```

### 2.1 How state actually moves between nodes

1. The API layer builds the **initial state** (see §8) and calls `graph_app.ainvoke(initial_state, config)`.
2. The entry node (`intake`) receives the whole state.
3. Each node function returns a dict like `{"needs_clarification": True, "messages": [AIMessage(...)]}` — **only the keys it wants to change**.
4. LangGraph merges each key into the state:
   - Plain keys → **last write wins** (whole value replaced).
   - `messages` → uses the **`add_messages` reducer**: returned messages are **appended** to the existing list (and deduplicated by message ID), never replaced. This is why nodes can just `return {"messages": [AIMessage(...)]}` to "say something."
5. The next node (chosen by edge or router) receives the merged state.

This is the core answer to "how does information go from one node to the other": **via the shared, merging state object — not via function arguments or return values chained between nodes.**

---

## 3. Graph Topology (`graph.py`)

### 3.1 Nodes

| Node | Function | File |
|---|---|---|
| `intake` | `intake_node` — pass-through | `nodes/intake.py` |
| `injection_pre_check` | `injection_pre_check_node` — prompt-injection filter | `nodes/intake.py` |
| `preprocess` | `preprocess_node` — sanitize/gibberish/scope/clarify | `nodes/triage.py` |
| `classify` | `classify_node` — category + priority | `nodes/triage.py` |
| `retrieve` | `retrieve_node` — pgvector RAG | `nodes/retrieval.py` |
| `diagnose` | `diagnose_node` — tool-calling diagnostics | `nodes/resolution.py` |
| `resolve` | `resolve_node` — grounded answer generation | `nodes/resolution.py` |
| `verify` | `verify_node` — leak/credential guardrail | `nodes/resolution.py` |
| `present_confirmation` | asks "did that fix it?" | `nodes/confirmation.py` |
| `handle_confirmation` | classifies the user's yes/no/unsure reply | `nodes/confirmation.py` |
| `escalate` | `escalate_node` (= `handoff_node`) — ticket handoff summary | `nodes/handoff.py` |
| `human` | `human_node` — marks `human_takeover`, then END | `nodes/handoff.py` |

### 3.2 Edges and routers

```
ENTRY ──▶ intake
intake ──(check_takeover)──▶ human            if status == "human_takeover"
       └────────────────────▶ injection_pre_check

injection_pre_check ──(check_injection)──▶ escalate               if should_escalate()
                    ├────────────────────────▶ handle_confirmation if awaiting_confirmation_reply
                    └────────────────────────▶ preprocess

preprocess ──(check_clarification)──▶ END        if needs_clarification or out_of_scope
           └────────────────────────▶ classify

classify ──▶ retrieve        (unconditional)
retrieve ──▶ diagnose        (unconditional)

diagnose ──(check_diagnose)──▶ escalate        if should_escalate()
         └────────────────────▶ resolve

resolve ──(check_resolution)──▶ escalate       if should_escalate() or needs_handoff
        └─────────────────────▶ verify

verify ──(check_verification)──▶ escalate      if should_escalate() or needs_handoff
       └──────────────────────▶ present_confirmation

present_confirmation ──▶ END   (unconditional)

handle_confirmation ──(check_confirmation_reply)──▶ retrieve   if decision == "retry"
                                                 ├────────────▶ escalate if decision == "escalate"
                                                 └────────────▶ END     otherwise

escalate ──▶ human ──▶ END    (unconditional)
```

### 3.3 The central router predicate — `EscalationPolicy.should_escalate(state)`

Returns `True` if **any** of:
1. `state["escalate"] is True` or `state["needs_handoff"] is True` — set by injection filter, resolve failures, grounding failure, verify leak detection, or user request.
2. `state["category"]` is a **hard-escalation category**: `security_incident`, `hardware_failure`, `datacenter_outage`.
3. `evidence` contains **≥ 2 error entries** (diagnostic tooling failing repeatedly).

Because this check runs at the `injection_pre_check`, `diagnose`, `resolve`, and `verify` routers, escalation can short-circuit the happy path from almost any stage.

---

## 4. Node-by-Node Walkthrough

### 4.1 `intake` — pass-through entry

Returns `{"input": state.get("input", "")}`. Functionally a no-op anchor for the entry point. Its router `check_takeover` is the first decision: if the conversation was already taken over by a human engineer (`status == "human_takeover"` persisted from the DB), the graph skips **everything** and goes straight to `human → END`. The AI never touches taken-over conversations.

### 4.2 `injection_pre_check` — security gate

Three-layer prompt-injection defense:

1. **Deterministic regex-style substring filter** (0 ms): phrases like `"ignore all previous instructions"`, `"reveal your system prompt"`, `"dan mode"`, `"jailbreak"`. On hit → `escalate=True`, `status="escalated"`, `category="security_incident"`, `priority="CRITICAL"`, and an AIMessage "Security alert: The request was flagged for security review."
2. **Benign bypasses** so legit requests don't burn LLM quota: escalation-hunting keywords ("talk to an engineer"), and short replies ("1", "yes", "ok", "hi").
3. **LLM security classifier**: a dedicated system prompt returns exactly `INJECTION` or `SAFE`. `INJECTION` → same escalation payload as layer 1. If the LLM call itself fails, a second deterministic pattern list acts as fallback.

**Information out:** `escalate`, `status`, `category`, `priority`, `priority_rationale`, `messages`. The next router (`check_injection`) reads `escalate`/`awaiting_confirmation_reply`.

### 4.3 `preprocess` — triage brain (the busiest node)

Input: `input` + `messages` (bounded history). Ordered decision ladder:

1. **Gibberish detection** (`is_gibberish` heuristic — consonant clusters, vowel ratios, keyboard-mash patterns; error-message-shaped text fast-passed as legit):
   - **First gibberish message** → `needs_clarification=True` + a polite "please describe your issue" AIMessage. Router sends to `END` (turn over, user replies).
   - **≥ 2 consecutive gibberish messages** → session termination: `out_of_scope=True`, `status="resolved"`, empty `sanitized_query`/`search_query` (the API layer recognizes this exact signature and **closes the conversation**).
2. **Cold open (first AI turn):**
   - Empty/greeting-only input (`"hi"`, `"test"`, < 4 chars) → ask for a description, `needs_clarification=True`.
   - Sanitize (`sanitize_input`: strips zero-width/bidi unicode, template markers, HTML tags; caps at 2048 chars / 512 words — while preserving the invisible confirm markers).
   - **Scope check** (`is_it_support_query`): LLM gatekeeper (`IN_SCOPE`/`OUT_OF_SCOPE`) with keyword-heuristic fallback. Out of scope → `out_of_scope=True` + friendly rejection → router sends to `END`.
3. **Subsequent turns — topic continuity:**
   - **Hard pivot regex** (pizza, uber, jokes, weather...) or **LLM transcript check** (`CONTINUE`/`ABANDONED`, fail-open to CONTINUE) → if abandoned: `out_of_scope=True`, turn ends.
   - **New-issue detection** (`_NEW_ISSUE_RE`: "another issue", "separate problem"...) → `needs_clarification=True`, and crucially `search_query=""` so the **old topic's search query doesn't bleed into retrieval** for the new issue.
4. **Sufficiency check (LLM, JSON-out):** "Is there enough detail to troubleshoot?" If not → one single clarifying question, `needs_clarification=True` → `END`. If yes → extracts early `category`/`priority`/`rationale` in the same call (classify can then skip its LLM call).
5. **Hard cap:** after `MAX_CLARIFICATION_ROUNDS` (default 5) prior AI turns, stops asking and lets the query through.

**Information out:** `sanitized_query` (transcript-aware), `search_query` (focused: first problem statement + current detail, minus boilerplate), `needs_clarification`, `out_of_scope`, early `category`/`priority`.

### 4.4 `classify` — category & priority

- **Fast path:** if preprocess already filled a valid `category` + `priority` → returns them unchanged with rationale `"Classified during triage."` (saves an LLM call).
- **Slow path:** LLM JSON classification (Access/Network/Hardware/Software/Email/Security/Application + CRITICAL/HIGH/MEDIUM/LOW with rules like "CRITICAL = security incident or multi-user stoppage"). Invalid values ignored; defaults `general_support`/`medium`.
- **LLM-down fallback:** keyword heuristics (malware/phishing → critical, "locked out"/bsod → high, "how do i" → low).

### 4.5 `retrieve` — pgvector RAG

- Query priority: `search_query` → `sanitized_query` → `input`.
- Opens its **own DB session** (`AsyncSessionLocal`) — nodes don't inherit the request's session — and calls `RetrievalService.get_similar_documents(session, query, user_department)`. Department scoping means employees see knowledge relevant to their org unit.
- **Evidence dedup:** old `knowledge_and_incidents` evidence blocks are stripped from state before appending fresh ones — so a retry turn doesn't accumulate stale document copies.
- Records best `retrieval_score` (used by resolve's threshold gate) and appends `{"source": "knowledge_and_incidents", "documents": [...]}` to `evidence`.

### 4.6 `diagnose` — tool-calling node

Two tool mechanisms:

1. **Deterministic pre-selection:** `select_mock_tool(query)` maps "vpn" → `vpn_check`, "device"/"laptop" → `device_check`; executed once via the permission-gated `ToolGateway` (allowed set `{"vpn_check", "device_check"}`), guarded by `tool_history` so a tool never runs twice in one invocation.
2. **LLM tool-calling:** `llm.bind_tools(tools)` with a "You MUST use tools" system prompt. Any returned `tool_calls` are executed through the gateway; each result is appended to `evidence` as `{"source": "diagnostic_tool", ...}` and a matching `ToolMessage` (plus the AIMessage carrying the calls) is **appended to `messages`** via the reducer — so the full tool exchange becomes part of conversation context downstream.

Tool failures append `{"error": ...}` to `evidence`; **two or more error entries trip `EscalationPolicy`** at the next router.

### 4.7 `resolve` — grounded answer generation (the quality gate)

Three failure paths, all funneling to escalation:

1. **`retrieval_score < SIMILARITY_THRESHOLD` (default 0.62)** → escalate immediately. Comment captures the design intent: a low score is a *knowledge-base gap*, not proof the topic is out of scope (scope was already decided in preprocess), so don't try to distinguish.
2. **LLM unavailable** → escalate.
3. **Grounding check fails** → escalate. `resolve` builds a prompt of [system ("only provide solutions supported by the retrieved knowledge base")] + history + "Current Issue Details + Evidence JSON", generates the answer, then `is_response_from_knowledge_base(answer, evidence)` verifies the answer actually references the evidence: doc titles appearing verbatim, ≥1 meaningful title word, ≥2 meaningful content words, or tool name/result terms. Refusal phrases ("cannot answer", "insufficient evidence") count as *not* grounded. **Answer length alone never passes.**

On success: `messages=[AIMessage(answer)]`, `needs_handoff=False`, `escalate=False`, `status="resolved"`.

### 4.8 `verify` — output guardrail (last line of defense)

Scans the latest AIMessage against `_LEAK_RE`:
- prompt/system-prompt disclosure phrases,
- AWS keys (`AKIA…`), private key blocks, `password: "..."`, bearer JWTs, GitHub tokens (`ghp_…`).

Leak found → **replaces** the message with a neutral escalation note and sets `escalate`/`needs_handoff`/`status="escalated"` (router diverts to `escalate`). Otherwise passes state through unchanged.

### 4.9 `present_confirmation` — the "did that fix it?" prompt

- **First time:** menu — `1` yes / `2` no / `3` not sure — plus an invisible **`CONFIRM_MARKER`** (zero-width Unicode chars `\u200b\u200b\u200c\u200b`) appended to the message.
- **Already presented before (re-answer case):** shorter "updated my answer" variant with **`CONFIRM_FINAL_MARKER`**.
- Sets `status="awaiting_confirmation"`, then the graph ends.

**Why invisible markers?** The marker lives inside the persisted AI message in Postgres. On the *next* turn, the API layer scans the last persisted AI message for a marker and sets `awaiting_confirmation_reply=True` in the initial state — which makes `check_injection` route straight to `handle_confirmation` instead of the normal pipeline. Zero-width chars are used instead of HTML comments because they're invisible in any renderer without relying on markdown raw-HTML parsing. `sanitize_input` knows to preserve these markers through cleaning.

### 4.10 `handle_confirmation` — classifying the reply

Decision ladder (deterministic first, LLM last):

1. **Follow-up question mid-confirmation** ("how do I check the firewall?", anything with `?` or question-phrases) → LLM answers it directly (grounded in the last AI answer, capped at 1500 chars), re-appends the confirm marker, stays in the loop (`confirmation_decision=""`, `awaiting_confirmation_reply=True`).
2. **Escalation request regex** (`_ESCALATE_REQUEST_RE`) — checked *first and unconditionally*: "talk to a human", "get me an engineer" etc. → `confirmation_decision="escalate"`, "Understood — connecting you with an engineer now."
3. **Hardcoded phrase tables** → `yes` / `no` / `unsure` / `ack` ("ok got it", "will try", "thanks" — user intends to try the steps; loop stays open).
4. **Regex classifiers** (`_YES` vs `_NO`), then **LLM fallback** classifier (YES/NO/ACK/ESCALATE/UNSURE), defaulting `unsure`.
5. **Verdict routing:**
   - `yes` → `confirmation_decision="resolved"` (API layer closes conversation/ticket — see §8).
   - `no` → `confirmation_decision="retry"` + rebuilds `search_query`/`sanitized_query` from the **original problem** (first human message) merged with any new detail → the router sends the graph **back to `retrieve`** for one more RAG cycle.
   - `ack` → stay in loop, re-ask.
   - `unsure` → if the *final* confirmation was already sent (i.e. this is the second round of ambiguity) → escalate; else escalate too ("I don't want to guess") — the only path difference is messaging.

### 4.11 `escalate` (= `handoff_node`) and `human`

- `escalate` builds a machine-readable handoff summary into `evidence` (`{"source": "handoff_summary", "payload": {query, summary, evidence_count, retrieval_score}}`), and adds a user-facing escalation AIMessage **only if the last message isn't already an escalation notice** (dedup guard on keywords like "escalat", "engineer", "security alert").
- `human` just sets `status="human_takeover"` and the graph ends. The API layer then flips `Conversation.owner_type=HUMAN`, creates/updates the Ticket (ESCALATED status), writes `TicketHistory` + `AuditEvent` rows, and appends a "**Ticket Reference:** `#XXXXXXXX`" note to the last AI message.

---

## 5. Cross-Turn Mechanics (how the loop persists)

The graph itself is stateless. Here's the full loop across HTTP requests:

```
Turn N:   add_message() → history loaded from DB (bounded/summarized) →
          graph invoke → ... → verify → present_confirmation → END
          AI message (with invisible CONFIRM_MARKER) persisted in Postgres

Turn N+1: add_message() → API scans last persisted AI message →
          finds CONFIRM_MARKER → sets awaiting_confirmation_reply=True in initial state →
          intake (not taken over) → injection_pre_check
          → check_injection routes to handle_confirmation (skips the whole pipeline!)
          → verdict: resolved → END (API closes conv/ticket)
                     retry    → retrieve → ... (one more RAG cycle)
                     escalate → escalate → human → END
```

Supporting persistence pieces:
- **History bounding** (`history_utils.py`): the API loads prior USER/AI messages; if more than `RECENT_HISTORY_KEEP` (10), older ones are LLM-summarized into a single leading SystemMessage ("Summary of earlier conversation: ..."), degrading to 500-char truncation if the LLM is down. SYSTEM messages (engineer notes, closure notices) are excluded from LLM context.
- **Classification persistence:** before invoking, the API checks for an existing Ticket on the conversation and re-feeds its `category`/`priority`/`priority_rationale` into the initial state — so classification survives across turns (and `classify`'s fast path picks it up).
- **Gibberish session close:** the API detects preprocess's signature (`out_of_scope=True`, `escalate=False`, empty `sanitized_query`, `status="resolved"`) and closes the conversation so the termination message can't loop forever.

---

## 6. The Happy Path, End to End (annotated trace)

Example: user sends "My VPN keeps disconnecting every few minutes."

| Step | Node | Reads from state | Writes to state | Router outcome |
|---|---|---|---|---|
| 1 | `intake` | `input` | (no-op) | status ≠ takeover → `injection_pre_check` |
| 2 | `injection_pre_check` | `input` | — | benign keywords ("vpn" not escalation-y; LLM says SAFE) → `escalate=False` → `preprocess` |
| 3 | `preprocess` | `input`, `messages` | `sanitized_query`, `search_query="VPN keeps disconnecting..."` | sufficient detail, in-scope, turn 0 → `classify` |
| 4 | `classify` | `search_query` (or triage result) | `category="network"`, `priority="high"`, rationale | — → `retrieve` |
| 5 | `retrieve` | `search_query`, `user_context.department` | `evidence+=[docs]`, `retrieval_score=0.81` | — → `diagnose` |
| 6 | `diagnose` | `sanitized_query` ("vpn" → tool), `messages` | `evidence+=[vpn_check result]`, `tool_history=["vpn_check"]`, tool `AIMessage`+`ToolMessage` | no errors → `resolve` |
| 7 | `resolve` | `retrieval_score ≥ 0.62`, `evidence`, `messages` | `messages+=[AIMessage(answer)]`, `status="resolved"` | grounded ✓ → `verify` |
| 8 | `verify` | last AIMessage | — | no leaks → `present_confirmation` |
| 9 | `present_confirmation` | — | `messages+=[confirm menu + marker]`, `status="awaiting_confirmation"` | → `END` |
| 10 | API | `final_state` | persists AI messages, returns responses | — |

---

## 7. Design Patterns Worth Knowing

- **Fail-open for usability, fail-closed for safety.** Ambiguous UX checks default to *continuing* (topic-continuity → CONTINUE, LLM classifier errors → heuristics/proceed), while anything security- or grounding-related defaults to *escalation* (injection filter errors → deterministic filter; grounding failure → handoff; unsure confirmation → engineer).
- **Deterministic-first, LLM-second.** Every LLM decision is fronted by a cheap deterministic check (injection patterns, gibberish heuristics, confirmation phrase tables, topic-pivot regex) to save latency and quota — with a deterministic fallback if the LLM itself errors.
- **Routers read flags, nodes set flags.** Nodes never decide the next node themselves; they set state flags (`escalate`, `needs_handoff`, `needs_clarification`, `confirmation_decision`, `awaiting_confirmation_reply`) and router functions translate flags into edges. This keeps the graph topology in `graph.py` and the logic in the nodes.
- **`messages` is append-only by reducer** — nodes that "say" something just return new AIMessages; the full transcript (including tool exchanges) accumulates for downstream prompts and is persisted by the API layer afterwards.
- **JSON-out prompting with manual cleanup.** Classify/preprocess strip ```json fences by hand and validate against allowed value sets, ignoring invalid LLM output rather than crashing.

---

## 8. Where the API Meets the Graph

`POST /conversations/{id}/messages` (employee path) in `conversations.py`:

1. **Support-staff shortcut:** engineer messages are stored as SYSTEM `[Engineer] ...` messages and **bypass the graph entirely**.
2. Loads bounded history (`_load_history` → `build_bounded_history`).
3. Scans the last persisted AI message for `CONFIRM_MARKER`/`CONFIRM_FINAL_MARKER` → computes `awaiting_confirmation_reply`.
4. Builds `initial_state`: `input`, `messages` (bounded history), `user_context` (the authenticated user dict from JWT), persisted `status` (`human_takeover` if owner is human), prior classification from any existing ticket, and the confirmation flag.
5. `final_state = await graph_app.ainvoke(initial_state, config=lf_config)` — `lf_config` carries Langfuse observability metadata (conversation id, user email, role, department).
6. Reads everything it needs **out of the final state**:
   - new `AIMessage`s appended after invocation (`final_state["messages"][history_len:]`) → persisted as AI rows,
   - `confirmation_decision == "resolved"` → close conversation + resolve/close ticket (creating one from the *original* issue text if none exists),
   - escalation flags → human takeover + ticket escalation + audit trail,
   - gibberish signature → close conversation,
   - plain new classification → create a NEW ticket with category/priority if none exists.
7. Commits and returns `{"messages": responses, "state": final_state}`.

So the contract is clean: **the graph owns reasoning; the API owns persistence, ticketing, and side effects.**

---

## 9. Environment Knobs (`workflow/constants.py`)

| Variable | Default | Meaning |
|---|---|---|
| `SIMILARITY_THRESHOLD` | `0.62` | Retrieval score below this → escalate at `resolve` |
| `MIN_DOC_SCORE` | `0.55` | Docs below this never reach evidence |
| `LLM_TEMPERATURE` | `0.0` | Deterministic generations for resolve/diagnose |
| `LLM_SEED` | `42` | Seed for reproducibility where supported |
| `MAX_CLARIFICATION_ROUNDS` | `5` | Clarify-loop cap before preprocess lets queries through |
| `RECENT_HISTORY_KEEP` | `10` | Verbatim recent messages; older ones get LLM-summarized |

---

## 10. Related Files

```
backend/src/workflow/graph.py            ← topology + routers
backend/src/workflow/state.py            ← AgentState + add_messages reducer
backend/src/workflow/constants.py        ← tunables + invisible confirm markers
backend/src/workflow/escalation.py       ← EscalationPolicy (central router predicate)
backend/src/workflow/nodes/intake.py     ← intake, injection_pre_check
backend/src/workflow/nodes/triage.py     ← preprocess, classify
backend/src/workflow/nodes/retrieval.py  ← retrieve (pgvector)
backend/src/workflow/nodes/resolution.py ← diagnose (tools), resolve (grounded gen), verify (leak guard)
backend/src/workflow/nodes/confirmation.py ← present/handle confirmation loop
backend/src/workflow/nodes/handoff.py    ← escalate (=handoff), human
backend/src/workflow/utils/guardrails.py ← sanitize_input, is_gibberish, is_it_support_query, grounding check
backend/src/workflow/utils/history_utils.py ← build_bounded_history (summarize old turns)
backend/src/api/conversations.py         ← invokes the graph, persists results, cross-turn flags
```
