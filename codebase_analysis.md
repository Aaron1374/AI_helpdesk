# AI L1 IT Helpdesk Codebase Analysis

## 1. High-Level Architecture Overview
The Helpdesk system is an event-driven AI application built to automate IT issue resolution. It features a React/Vite frontend and a Python/FastAPI backend. The brain of the system is an autonomous state machine powered by **LangGraph**. The AI processes user inputs, retrieves contextual knowledge via RAG (PostgreSQL + pgvector), securely invokes diagnostic tools, and deterministically escalates complex issues to human engineers.

### Key Components:
- **Backend (FastAPI)**: Exposes REST APIs (`src/api`) to manage conversations, tickets, and user context.
- **LangGraph Workflow**: Found in `src/workflow/`. It defines a `StateGraph` that models the AI's step-by-step reasoning and action process.
- **Database (PostgreSQL + SQLAlchemy)**: Manages structured data (Users, Conversations, Tickets, Messages) and vector embeddings for knowledge retrieval (`src/models/`).
- **Frontend (React)**: Contains portals for Employees (to report issues) and Engineers (to view escalations and takeover).

---

## 2. The LangGraph Workflow Trace (How the AI Works)
The LangGraph state machine (`backend/src/workflow/graph.py`) defines the exact path a user's message takes. Below is the complete trace of what happens when an employee sends a message:

### Step 2.1: API Entry Point (`src/api/conversations.py`)
When a user posts to `/conversations/{id}/messages`, the API verifies authorization and saves the message to the database. If the conversation is currently owned by the `AI`, it initializes the LangGraph workflow with the user's input, context, and previous messages.

### Step 2.2: `intake_node` -> `injection_pre_check_node`
- **Intake**: Normalizes the state and input.
- **Security Pre-Check**: The `injection_pre_check_node` evaluates the input for prompt injection attacks using an LLM prompt and regex matching (e.g., checking for "ignore all previous instructions"). If an attack is detected, the workflow immediately forces an escalation.

### Step 2.3: `clarify_node`
This node acts as a basic filter. If the user's input is extremely short or a simple greeting (e.g., "hi", "help me"), it sets `needs_clarification = True`. The workflow halts here and asks the user to provide more details about the issue.

### Step 2.4: `classify_node`
An LLM analyzes the user's description and determines the category of the IT issue (e.g., "Network", "Hardware", "Access").

### Step 2.5: `retrieve_node` (RAG Pipeline)
The node performs an asynchronous similarity search against the database. It uses `pgvector` to find relevant Knowledge Base (KB) documents or historical incidents. **Crucially**, it uses the user's `department` from their context to filter results, ensuring strict data isolation. The retrieved documents are appended to the state's `evidence`.

### Step 2.6: `diagnose_node`
This is where tool execution happens. The LLM is equipped with diagnostic tools (e.g., `vpn_check`, `device_check`) using LangChain's `.bind_tools()`. 
- The LLM evaluates the issue and the retrieved evidence to decide if it needs more system data.
- If it decides to call a tool, the request is intercepted by the **`ToolGateway`** (`src/tools/gateway.py`).
- The Gateway validates if the requested tool is authorized. If successful, the tool executes (currently mocked server-side), and the results are injected back into the `evidence` array.

### Step 2.7: `resolve_node`
The final decision node evaluates all gathered `evidence`:
- **If Knowledge/Evidence exists**: The LLM attempts to formulate a step-by-step resolution.
- **If No Knowledge is found**: The LLM acknowledges the issue and defaults to escalating it. It sets `escalate = True`.

### Step 2.8: `verify_node` / `escalate_node`
- If the issue was resolved, the `verify_node` marks the status as `resolved`.
- If an escalation was triggered (by the injection check, diagnose node, or resolve node), the `escalate_node` appends a standard system message informing the user that an L1 support engineer will assist them.

---

## 3. Human Handoff and Escalation (What happens next?)
When LangGraph finishes processing, the FastAPI route evaluates the final state. 
If the state returns `escalate=True` or `status == "escalated"`:
1. **Ownership Transfer**: The `ConversationOwner` in the DB is switched from `AI` to `HUMAN`.
2. **Ticket Creation**: A `Ticket` is generated with the status `ESCALATED`, linked to the conversation.
3. **Audit Logging**: An `AuditEvent` and a `TicketHistory` record are created to track the escalation.

From this point forward, LangGraph is completely bypassed. If the employee sends another message, it simply gets appended to the DB. A human engineer can use the frontend dashboard to call the `/takeover` endpoint, shifting the ticket to `IN_PROGRESS`, and respond directly as a `SYSTEM` message (prefixed with `[Engineer]`).

---

## 4. Security & Authorization Design
The codebase implements strong guardrails to prevent AI misalignment and unauthorized access:

1. **The Tool Gateway (`src/tools/gateway.py`)**: The LLM is never allowed to execute arbitrary code. All tool calls are routed through the Gateway, which acts as a strict whitelist enforcing Role-Based Access Control before fulfilling diagnostic requests.
2. **Object-Level Authorization in RAG**: The `retrieve_node` strictly scopes vector queries to the authenticated principal's logical boundary (e.g., their department). This prevents the LLM from inadvertently leaking sensitive IT documents meant for other departments.
3. **API RBAC**: FastAPI endpoints are protected by `RoleChecker` dependencies, ensuring that only users with roles like `engineer` or `admin` can takeover conversations or view global ticket queues.
