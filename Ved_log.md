## 2026-09-08

- Created the backend Python virtual environment at `backend/venv`.
- Installed dependencies from `backend/requirements.txt`.
- Verified with `pip check`: no broken requirements.
- Verified backend imports: FastAPI, SQLAlchemy, Alembic, LangGraph, LangChain OpenAI, and pytest.
- Python version: 3.12.10.
- PowerShell activation: `./backend/venv/Scripts/Activate.ps1`

## Project Setup and Run

### Wins and completed work

- Confirmed Docker CLI and Docker Compose were installed.
- Started Docker Desktop with `docker desktop start`.
- Verified Docker Engine server `29.7.2` was reachable.
- Built and started the PostgreSQL/pgvector, backend, and frontend containers.
- Fixed Alembic configuration to use the existing `backend/alembic` directory.
- Added the missing Alembic `env.py` runtime configuration.
- Made PostgreSQL enum migrations idempotent and prevented duplicate enum creation.
- Added `asyncpg` for the backend's asynchronous SQLAlchemy engine.
- Normalized the async database URL for synchronous Alembic migrations.
- Fixed backend imports for the Docker `/app/src` layout.
- Added the missing Vite frontend entry files: `index.html`, `src/main.tsx`, and `src/App.tsx`.
- Added the Vite `/api` proxy to the backend service.
- Applied all database migrations successfully.
- Verified the database revision: `pgvector_tickets (head)`.
- Verified the frontend endpoint: HTTP 200 at `http://localhost:5173`.
- Verified the backend API docs endpoint: HTTP 200 at `http://localhost:8000/docs`.
- Verified the backend container starts cleanly and Uvicorn reports application startup complete.

### Commands used

```powershell
docker desktop start
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose ps
docker compose exec backend alembic current
```

### Issues found and current status

- Docker Engine was initially unavailable; resolved by starting Docker Desktop.
- Alembic initially pointed to a nonexistent `migrations` directory; fixed.
- Alembic initially lacked `env.py`; fixed.
- Baseline migrations attempted to create PostgreSQL enums twice; fixed with idempotent enum creation.
- Backend initially imported `backend.src` even though the container exposes `/app/src`; fixed imports.
- Backend initially used an async SQLAlchemy engine with the synchronous `psycopg2` URL; fixed with `asyncpg` and URL normalization.
- Frontend initially returned 404 because `index.html` and the React entry point were missing; fixed.
- Frontend build still needs a `frontend/tsconfig.json`; `npm run build` currently fails at `tsc`.
- Frontend has no stylesheet, so it currently renders with browser-default styling.
- Employee chat uses a hardcoded placeholder conversation UUID.
- Engineer dashboard uses a hardcoded `DUMMY_ENGINEER_TOKEN`.
- Employee and engineer views lack user-facing loading, empty, and error states.
- Vite's Docker proxy target works in Compose but is not suitable for direct host-only Vite execution.
- ESLint reports that the installed TypeScript version `5.9.3` is outside the parser's supported range below `5.6`.

### Current run status

- Docker containers are running.
- Frontend: `http://localhost:5173`
- Backend docs: `http://localhost:8000/docs`
- Database migrations are at head.
- The core Docker runtime is working; frontend polish and production build configuration remain.

## Priority 1 Completion

- Added strict Vite TypeScript configuration in `frontend/tsconfig.json`.
- Pinned TypeScript to `5.5.4` in `frontend/package.json` for compatibility with the configured ESLint TypeScript parser.
- Installed the updated frontend dependency set in the Docker container.
- Verified `docker compose exec frontend npm run build`: passed.
- Verified `docker compose exec frontend npm run lint`: passed with no warnings or errors.
- Marked T001-T004 complete in `Ved_tasks.md`.

## Priority 2 Completion

- Added the shared visual system in `frontend/src/styles.css`.
- Added responsive navigation, typography, chat layout, dashboard layout, buttons, forms, focus states, hover states, disabled states, and reusable loading/error/empty/success state styles.
- Wired the stylesheet through `frontend/src/main.tsx`.
- Added semantic portal headings, navigation state, employee empty-state guidance, and engineer ticket empty-state guidance.
- Verified the production build: passed with CSS output generated.
- Verified frontend lint: passed with no warnings or errors.
- Verified desktop layout at 1440x900: rendered successfully.
- Verified mobile layout at 390x844: no horizontal overflow.
- Marked T005-T008 complete in `Ved_tasks.md`.
- Existing dashboard placeholder API requests still return 404 until Priority 4 replaces the placeholder authentication and ticket workflow.

## AI Agent Command-Line Test

- Investigated an `Internal Server Error` from `POST /conversations`.
- Found that SQLAlchemy had not registered the `users` table before flushing conversation data.
- Found that conversation creation generated a random user foreign key instead of using the authenticated user.
- Updated `backend/src/api/conversations.py` to resolve or create the development user from the JWT and use that user's ID.
- Restarted the backend to clear stale Uvicorn reload state.
- Verified conversation creation succeeded with ID `72d52c34-019b-489d-a262-e3946c0de6b7`.
- Verified a VPN issue message returned HTTP 200.
- Verified the fallback AI workflow executed the mocked `vpn_check` tool through the Tool Gateway.
- Verified the response contained `tool_history: ["vpn_check"]`, `status: "resolved"`, and an AI resolution message.

## Mock AI Flow Test Log

- Tested the AI agent through the Docker backend using PowerShell commands.
- Generated a temporary employee JWT inside the backend container for local testing.
- Created an authenticated conversation successfully.
- Sent the mock request: `My VPN stopped connecting this morning`.
- The fallback workflow ran without an OpenAI API key.
- The Tool Gateway executed the mocked `vpn_check` diagnostic.
- Verified the response returned HTTP 200 with an AI resolution.
- Verified workflow state included `category: "general_support"`.
- Verified workflow state included `tool_history: ["vpn_check"]`.
- Verified workflow state included `status: "resolved"`.
- Initial `Internal Server Error` was traced to conversation model registration and an invalid random user foreign key.
- Fixed `backend/src/api/conversations.py` to resolve or create the authenticated development user before creating the conversation.
- Restarted the backend to clear stale Uvicorn reload state, then reran the complete flow successfully.
- This was a mocked diagnostic test; it did not call OpenAI and did not perform a real privileged system action.

## Ticket History Check

- Queried the `ticket_history` table in the running PostgreSQL database.
- The table exists and its schema is ready for ticket status transitions.
- Current entries: `0 rows`.
- No ticket status changes have been recorded yet because the mock VPN test created a conversation but did not create or transition a ticket.

## Universal LLM Configuration

- Centralized chat and embedding model creation in `backend/src/core/llm.py`.
- Added environment-driven provider selection through `LLM_PROVIDER` and `EMBEDDING_PROVIDER`.
- Added OpenAI support through `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `LLM_MODEL`.
- Added Gemini support through `GOOGLE_API_KEY` and `LLM_MODEL`.
- Added Grok/xAI support through `XAI_API_KEY`, `XAI_BASE_URL`, and `LLM_MODEL`.
- Added generic OpenAI-compatible support for providers such as Ollama and hosted compatible APIs.
- Added `langchain-google-genai` and `langchain-xai` dependencies.
- Wired all provider variables into `docker-compose.yml`.
- Added `.env.example` and updated `setup.md` with provider switching examples.
- Gemini automatically defaults to `gemini-embedding-001` when its embedding model is not specified.
- Rebuilt the backend image successfully.
- Provider smoke tests passed without network calls: Gemini resolved to `ChatGoogleGenerativeAI`; Grok and OpenAI resolved to `ChatOpenAI`.
- Backend Python compilation passed with exit code `0`.

## Gemini Live Model Test

- Reloaded the backend container from the local `.env` configuration.
- Tested Gemini through the application factory in `backend/src/core/llm.py`.
- Provider readiness: passed.
- Model used: `gemini-3.6-flash`.
- Prompt: `Reply with exactly: Gemini connection works`.
- Model response: `Gemini connection works`.
- Gemini connectivity and credentials are working.
- The response uses structured content blocks, so callers should handle `response.content` as either text or a list of content blocks.
- The Gemini client emitted non-blocking warnings about fixed sampling defaults and automatic function calling.
- The API key was not written to this log.

## Full Gemini Agent Run

- Ran the complete authenticated employee conversation flow through the backend API.
- Gemini was invoked from the LangGraph workflow, not only through a standalone model test.
- Conversation creation returned HTTP 200.
- Message processing returned HTTP 200 after the backend restart.
- Gemini classified the VPN issue as requiring human takeover.
- Workflow result: `human_takeover`.
- Tool history was empty because the deterministic escalation boundary stopped processing before diagnostics.
- Fixed an enum persistence error where the API attempted to save `human_takeover` into the database's `conversationstatus` enum.
- Takeover is now represented by the existing `ConversationOwner.HUMAN` field, while `human_takeover` remains an in-memory workflow state.
- Latest backend logs show no new server error for the full Gemini run.

## Frontend Connection Plan: Phase 1 Complete

- Added `backend/src/api/auth.py` with `POST /auth/login`.
- Registered the auth router in `backend/src/main.py`.
- Added OAuth2 form support through `python-multipart`.
- Added controlled development-user bootstrap using `DEV_USER_EMAIL`, `DEV_USER_PASSWORD`, and `DEV_USER_ROLE`.
- Stored bootstrapped development passwords with bcrypt hashing.
- Added Docker environment defaults for the development login.
- Added a legacy-hash repair path limited to the configured development account.
- Pinned `bcrypt<4.0.0` because Passlib 1.7.4 is incompatible with bcrypt 5.x.
- Rebuilt and restarted the backend successfully.
- Live login validation passed: valid credentials returned `token_type: bearer` and role `employee`.
- Live invalid-login validation passed: wrong credentials returned HTTP `401`.
- Phase 2 remains: build the frontend API client and session layer.

## Frontend Connection Plan: Phase 2 Complete

- Added typed frontend API contracts in `frontend/src/api/types.ts`.
- Added authenticated request handling in `frontend/src/api/client.ts`.
- Added session storage helpers in `frontend/src/auth/session.ts`.
- Added the login screen and authentication gate in `frontend/src/App.tsx`.
- Added sign-out behavior and bearer-token injection for API requests.
- Initial browser login returned `404 Not Found` because the Vite proxy preserved `/api` while backend routes do not use that prefix.
- Fixed `frontend/vite.config.ts` to rewrite `/api/auth/login` to `/auth/login` and apply the same mapping to conversation routes.
- Browser login then succeeded and transitioned to the authenticated Employee Portal.
- `docker compose exec frontend npm run build`: passed.
- `docker compose exec frontend npm run lint`: passed with no warnings or errors.
- Phase 3 remains: connect EmployeePortal conversation creation and message sending to the shared client.

## Frontend Connection Plan: Phase 3 Complete

- Replaced the hardcoded conversation UUID in `frontend/src/portals/EmployeePortal.tsx`.
- Employee messages now create a conversation on first send and reuse its returned ID.
- Employee messages now use the authenticated shared API client.
- Added disabled `Working...` state to prevent duplicate sends.
- Added retryable user-facing API error handling.
- Added human-takeover system messaging in the chat UI.
- Added backend `normalize_content` handling for Gemini structured response blocks before storing `Message.content`.
- Frontend build passed.
- Frontend lint passed.
- Initial browser request stalled when Uvicorn reloaded during a source change; the backend was restarted cleanly and the request was retried.
- Final browser validation passed: the portal rendered the user message, AI escalation messages, and engineer takeover notice.
- The tested VPN request ended in `human_takeover`, which is expected safety behavior for the configured escalation workflow.
- Phase 4 remains: role-gate the engineer dashboard and remove `DUMMY_ENGINEER_TOKEN`.

## Sanitized Agent Activity UI

- Added an `Agent activity` panel to the Employee Portal.
- The panel shows safe operational summaries from workflow metadata: classification, tools used, evidence count, escalation, and final status.
- Kept private chain-of-thought, system prompts, provider response signatures, secrets, and raw sensitive evidence out of the UI.
- Added typed `WorkflowState` metadata for the frontend response contract.
- Frontend build passed.
- Frontend lint passed.
- Browser requests reached the backend successfully with HTTP 200; Gemini response latency caused one browser wait to exceed the test timeout.

### Phase 1 troubleshooting record

- The first combined rebuild-and-test command checked `/health` while the backend container was still restarting, so the readiness check failed even though the image build succeeded.
- The first login attempt returned HTTP 500 because an existing development user had the legacy placeholder value `development-user` instead of a recognized password hash.
- Passlib then exposed a dependency incompatibility: `passlib 1.7.4` does not work reliably with `bcrypt 5.x` during bcrypt backend initialization.
- Fixed the dependency issue by pinning `bcrypt<4.0.0` in `backend/requirements.txt` and `backend/pyproject.toml`.
- Added handling for Passlib `UnknownHashError` and a development-only repair path for the configured development account.
- Restarted the backend and reran the login tests after confirming health.
- Final result: valid login returned a bearer token and employee role; invalid credentials returned HTTP `401`.

No—an empty vector DB is not the direct cause.

`AI Error: contents are required.` is raised in [`resolve_node`](C:\Users\VedAtulyaKamat\AI IT support\AI_helpdesk\backend\src\workflow\nodes\resolution.py:92) when calling the LLM with a prompt containing only the system message. The code never adds the user input or retrieval `evidence` to that final prompt.

An empty vector DB merely makes retrieval return `[]` safely ([`retrieval_service.py`](C:\Users\VedAtulyaKamat\AI IT support\AI_helpdesk\backend\src\services\retrieval_service.py:32)). If no tool evidence is produced either, the workflow returns “I cannot resolve…” before that LLM call.

The likely failure path is:

1. Some evidence exists (from a tool or retrieval).
2. `messages` is still empty.
3. Resolution sends only a `SystemMessage`.
4. The LLM provider rejects it because it has no user/content messages.

Also, the resolver currently ignores `evidence` entirely. It should include at least `HumanMessage(content=state["input"])` and ideally a formatted evidence block in its prompt.

## Universal LLM Integration and Startup Fixes

- Replaced legacy hardcoded `get_llm()` functions in `backend/src/workflow/nodes/intake.py`, `backend/src/workflow/nodes/triage.py`, and `backend/src/workflow/nodes/resolution.py` with the centralized `get_chat_model()` from `src.core.llm`.
- Ensured all LangGraph agent nodes dynamically adapt to any configured model/provider in `.env` (Groq, OpenAI, Gemini, Ollama, xAI).
- Fixed `SECRET_KEY` environment variable injection in `docker-compose.yml` for the backend service.
- Added development fallback default for `SECRET_KEY` in `backend/src/auth/security.py` to prevent startup crashes when keys are omitted.
- Added default values for `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` in `docker-compose.yml` to eliminate startup warnings.
- Fixed typo in `backend/src/api/tickets.py` (`from src.core.dclear import get_db` -> `from src.core.db import get_db`).
- Restarted backend container and verified clean Uvicorn startup (`Application startup complete`, HTTP 200 on `/`).

## Engineer Dashboard Authentication and L1 Role Setup

- Replaced the placeholder `DUMMY_ENGINEER_TOKEN` in `frontend/src/portals/EngineerDashboard.tsx` with authenticated API client requests using the session JWT.
- Added typed API helper functions (`getTickets()`, `getSimilarTickets()`, `takeoverConversation()`, `confirmResolution()`) in `frontend/src/api/client.ts` and corresponding types in `frontend/src/api/types.ts`.
- Enhanced `EngineerDashboard.tsx` with loading, empty, and role-permission error states.
- Updated backend RBAC authorization in `backend/src/api/tickets.py` and `backend/src/api/conversations.py` to recognize all support tiers (`engineer`, `l1`, `l2`, `support_lead`, `admin`).
- Configured automatic development bootstrapping for `engineer@example.com` (role: `l1`, password: `dev-password`) and `admin@example.com` (role: `admin`, password: `dev-password`) in `backend/src/api/auth.py`.
- Added quick-login preset buttons for **L1 Engineer**, **Employee**, and **Admin** on the frontend sign-in screen in `frontend/src/App.tsx`, and wired role-aware initial view routing.
- Verified authenticated `POST /auth/login` and `GET /tickets` requests: returned HTTP 200 OK.
- Verified frontend production build (`npm run build`) and lint (`npm run lint`): both passed cleanly with zero errors.

## Clarification Loop Fix and Automatic L1 Ticket Escalation

- Refactored `clarify_node` in `backend/src/workflow/nodes/triage.py` to remove the LLM clarification loop. The node now only requests clarification on trivial/empty greetings (`"hi"`, `"help"`, length < 4) and immediately allows user problem descriptions to proceed to triage and resolution.
- Updated `resolve_node` in `backend/src/workflow/nodes/resolution.py` to gracefully handle an empty vector DB / absence of RAG knowledge articles. It synthesizes helpful initial troubleshooting guidance, explicitly notifies the employee that a ticket has been created, and sets `escalate: True`.
- Updated `escalate_node` in `backend/src/workflow/nodes/handoff.py` to preserve messages generated during the resolution step.
- Updated `backend/src/api/conversations.py` to automatically instantiate a `Ticket` with status `ESCALATED`, create a `TicketHistory` record, and emit a traceable `AuditEvent` when a conversation escalates.
- Verified live end-to-end flow: an employee volume issue query received troubleshooting guidance, flagged escalation, and created ticket `[Audio] I am having a volume issue on my laptop...` with status `ESCALATED`, which immediately populated the L1 Engineer Dashboard (`GET /tickets`).

## Phase 1 Completion: Backend Message History, Support Messaging & Takeover State

- Added `GET /conversations/{conversation_id}/messages` endpoint in `backend/src/api/conversations.py` to retrieve complete ordered message history (`id`, `sender_type`, `content`, `created_at`), with authorization for the conversation owner and support roles (`engineer`, `l1`, `l2`, `support_lead`, `admin`).
- Updated `POST /conversations/{conversation_id}/messages` to support direct human messaging:
  - If sent by a support engineer, messages are saved as `SenderType.SYSTEM` with the `[Engineer]` prefix and returned immediately without calling LangGraph/LLM.
  - If sent by an employee after takeover (`ConversationOwner.HUMAN`), messages are persisted directly for the engineer without triggering AI generation.
- Updated `POST /conversations/{conversation_id}/takeover` to automatically transition the linked `Ticket.status` from `ESCALATED` to `IN_PROGRESS`, recording an audit event and ticket history entry.
- Added `POST /tickets/{ticket_id}/resolve` in `backend/src/api/tickets.py` to allow engineers to transition in-progress tickets to `RESOLVED`.
- Created task roadmap document in `engineer_chat_takeover_plan.md` outlining the 6 phases from backend endpoints to UI live chat consoles.
- Verified Phase 1 live via backend test script:
  - Conversation creation $\rightarrow$ employee escalation $\rightarrow$ engineer transcript retrieval $\rightarrow$ takeover (`IN_PROGRESS`) $\rightarrow$ engineer message injection (`[Engineer] Hello...`) $\rightarrow$ ticket resolution (`RESOLVED`). All operations returned HTTP 200 with expected state transitions.

## Phase 2 Completion: Frontend API Contracts and Client Integration

- Added `ChatMessageRecord` typed interface in `frontend/src/api/types.ts` (`id`, `sender_type`, `content`, `created_at`).
- Implemented `getConversationMessages(conversationId)` in `frontend/src/api/client.ts` to query `/conversations/{id}/messages`.
- Implemented `resolveTicket(ticketId)` in `frontend/src/api/client.ts` to invoke `POST /tickets/{id}/resolve`.
- Verified TypeScript compilation and production build (`npm run build`) in the frontend Docker container with zero errors.
- Marked Phase 2 tasks complete in `engineer_chat_takeover_plan.md`.

## Phase 3, 4 & 5 Completion: Live Chat Console, Two-Way Polling & Styling

- Refactored `frontend/src/portals/EngineerDashboard.tsx` into a responsive 2-column console:
  - **Left Queue Panel**: Real-time ticket list with ticket count, active highlight, title, and color-coded status badges (`ESCALATED`, `IN_PROGRESS`, `RESOLVED`).
  - **Right Live Chat Console**: Active ticket header with ticket/conversation IDs, action buttons (**[Take Over Chat]**, **[Mark Resolved]**), similar incident cards, chronological message transcript, and a live reply input form with Enter-to-send support.
- Configured 3-second live message polling in `EngineerDashboard.tsx` for the selected ticket to stream new employee messages in real-time.
- Updated `frontend/src/portals/EmployeePortal.tsx` to automatically poll the conversation transcript every 3 seconds and render engineer replies with dedicated **Support Engineer** styling and badges.
- Added full visual design system rules in `frontend/src/styles.css` for the split-screen layout, queue cards, chat console header/body/footer, support badges, and responsive viewports.
- Verified frontend build (`npm run build`) and lint (`npm run lint`): passed with zero errors or warnings.
- Marked Phases 3, 4, and 5 complete in `engineer_chat_takeover_plan.md`.

## Engineer Dashboard Access Resolution & Persona Switching

- Identified why the user saw `Access restricted: An engineer or support role is required to view the Engineer Dashboard`:
  - The browser session was logged in as `employee@example.com` (role: `employee`).
  - When switching tabs to "Engineer Dashboard", the backend RBAC on `/tickets` correctly prevented employee access with HTTP 403.
- Resolved by enhancing `frontend/src/App.tsx` and `frontend/src/portals/EngineerDashboard.tsx`:
  - In `App.tsx`: clicking "Engineer Dashboard" while authenticated as an employee now automatically switches to the engineer session (`engineer@example.com`), and a convenient inline session switcher (`Switch to L1` / `Switch to Employee`) is displayed in the navigation topbar.
  - In `EngineerDashboard.tsx`: when an access error (403/401) is encountered, the dashboard displays a clear explanation with a 1-click **[⚡ Switch & Sign in as L1 Engineer]** button that immediately authenticates as `engineer@example.com` and loads the ticket queue and live chat console.
- Verified TypeScript build (`docker compose exec frontend npm run build`): passed with 0 errors.

## Employee Past Chats and Role-Gated Portal Navigation

- **Removed Role-Switch Buttons**:
  - Removed topbar persona switcher buttons (`Switch to L1` / `Switch to Employee`) and automatic account switching from `frontend/src/App.tsx`.
  - Role-gated portal navigation tabs: `employee` role accounts only see the **Employee Portal**, while support accounts (`l1`, `l2`, `engineer`, `support_lead`, `admin`) can navigate between both portals.
  - To switch between user accounts, users simply use the standard **Sign out** action and sign in with their desired demo or custom account.
- **Added Employee Past Chat History**:
  - Backend: Added `GET /conversations` endpoint in `backend/src/api/conversations.py` to list all conversations belonging to the authenticated user, complete with message snippet previews, ticket status (`RESOLVED`, `IN_PROGRESS`, `ESCALATED`), timestamps, and message counts.
  - Frontend Client: Added `ConversationItem` type to `frontend/src/api/types.ts` and `getConversations()` helper in `frontend/src/api/client.ts`.
  - Employee Portal: Retained the focused single-column active chat layout at the top and added a **Past Conversations** history card grid underneath:
    - Dedicated **`+ Start New Chat`** / **`+ New Request`** actions.
    - Grid of interactive past conversation cards showing title, message preview, status badge (`Resolved`, `In Progress`, `Escalated`, `AI Active`), message count, and timestamp.
    - Clicking any past chat seamlessly loads its full transcript and status into the chat window above with smooth scrolling.
- **Verification**:
  - Live backend verification confirmed `GET /conversations` retrieves all 23 historical conversations for `employee@example.com` with full metadata and ticket associations.
  - Frontend production build (`npm run build`) and ESLint (`npm run lint`) passed with 0 warnings/errors.

## End Conversation Feature

- **Backend Support (`POST /conversations/{id}/close`)**:
  - Added closing endpoint in `backend/src/api/conversations.py`.
  - Sets `Conversation.status = ConversationStatus.CLOSED` and transitions any active linked ticket to `CLOSED` / `RESOLVED`, logging ticket history and audit events.
  - Inserts a closing system message into the chat transcript (`"This conversation has been ended."`).
  - Blocks sending new messages to closed conversations (`HTTP 400`).
- **Frontend UI & Integration**:
  - Added `closeConversation()` helper in `frontend/src/api/client.ts`.
  - Added an **`[End Conversation]`** action button in `EmployeePortal.tsx` header for active conversations.
  - When a conversation is ended:
    - Displays confirmation and marks the session as `Closed`.
    - Disables further typing and shows an informative banner with a 1-click **`+ Start New Chat`** button.
    - Updates status badges in both the active view and past conversation cards below.
- **Verification**:
  - Live Python endpoint test verified closing a conversation returns HTTP 200 with `status: CLOSED`.
  - Frontend TypeScript build and ESLint passed with 0 errors.

## Auto-Scroll Jump Fix (Containerized Scrolling)

- **Root Cause Identified**:
  - Polling hooks periodically updated message state every 4 seconds.
  - An uncontrolled `messagesEndRef.current.scrollIntoView({ behavior: 'smooth' })` was firing on every state change, causing the entire browser window/page to jerk and jump to the bottom of the chat window.
  - `.chat-window` lacked its own `overflow-y: auto` boundary and max-height constraints.
- **Solution Implemented**:
  - Bound `.chat-window` to `max-height: 480px; overflow-y: auto;` in `frontend/src/styles.css`.
  - Replaced all window `scrollIntoView()` calls in `EmployeePortal.tsx` and `EngineerDashboard.tsx` with containerized scroll targeting (`container.scrollTop = container.scrollHeight`).
  - Added smart scroll tracking: internal auto-scrolling only engages on initial conversation load or when the user is actively at the bottom of the message feed, eliminating all unwanted page jumping.
- **Verification**:
  - Frontend build and lint passed with 0 errors.

## Employee Dashboard New Chat & Closed Conversation Selection Fix

- **Root Cause**:
  - `loadConversations()` automatically selected `list[0]` (the most recent conversation) whenever `activeConversationId` was `null`.
  - If the employee's last conversation was closed, loading the portal auto-selected that closed conversation, locking the employee in a read-only state.
  - Clicking `+ Start New Chat` set `activeConversationId` to `null` temporarily, but background polling (every 8s) re-triggered `activeConversationId === null` and immediately snapped back to `list[0]`, trapping the employee in the closed conversation.
- **Fix Implemented in `EmployeePortal.tsx`**:
  - Updated state management to support an explicit `'new'` active session state in `sessionStorage`.
  - `loadConversations()` now checks if an existing conversation is open (`status !== 'CLOSED' && ticket_status !== 'CLOSED'`). If all past conversations are closed, it defaults to New Chat mode (`activeConversationId = null`) with `sessionStorage` set to `'new'`.
  - Clicking `+ Start New Chat` or `+ New Request` sets `sessionStorage` to `'new'`, preventing background sync polling from overriding the user's new request session.

