# Plan: Connect the AI Agent to the Frontend

**Date:** 2026-09-08

**Goal:** Connect the React employee portal to the authenticated FastAPI conversation API so a user can submit an issue in the browser and see the configured LLM response, including Gemini, in the chat interface.

## Current Gap

- `frontend/src/portals/EmployeePortal.tsx` posts to a hardcoded conversation UUID.
- The frontend sends no bearer token.
- The backend requires `Authorization: Bearer <token>` for conversation creation and messages.
- The backend declares `auth/login` as the OAuth2 token URL, but no login route currently exists.
- The backend AI workflow and Gemini provider have already been tested successfully from PowerShell.

## Target Flow

```text
Browser
  -> frontend API client
  -> POST /auth/login
  -> receive JWT
  -> POST /conversations
  -> receive conversation ID
  -> POST /conversations/{id}/messages
  -> FastAPI
  -> LangGraph
  -> configured LLM, e.g. Gemini
  -> response returned to chat UI
```

## Phase 1: Establish the Authentication Contract

1. Add a backend login endpoint in `backend/src/api/auth.py`.
2. Accept OAuth2-compatible form data or a documented JSON login payload.
3. Validate the development user against the `users` table.
4. Return a JWT containing `sub` and `role`, using the existing `create_access_token` helper.
5. Register the auth router in `backend/src/main.py`.
6. Add a development seed or documented test-user setup so an employee can log in without manually generating a token.
7. Add backend tests for successful login, invalid credentials, and token role claims.

**Done when:** `POST /auth/login` returns a usable employee JWT and invalid credentials return `401`.

**Development credentials:** The Docker defaults are `employee@example.com` / `dev-password`. Override them in `.env` before sharing the environment.

**Phase 1 status:** Complete. `POST /auth/login` now accepts OAuth2 form data, returns a bearer JWT with the user's role, bootstraps the configured development user, and rejects invalid credentials with `401`.

## Phase 2 status: Complete

- Added typed API contracts in `frontend/src/api/types.ts`.
- Added the shared authenticated fetch client in `frontend/src/api/client.ts`.
- Added session storage and token lifecycle helpers in `frontend/src/auth/session.ts`.
- Added the login gate and development login form in `frontend/src/App.tsx`.
- Added sign-out behavior and bearer-token injection.
- Fixed the Vite `/api` proxy to remove the `/api` prefix before forwarding to FastAPI.
- Browser validation passed: login transitioned to the authenticated Employee Portal.
- Frontend build and lint passed.

## Phase 3 status: Complete

- Removed the hardcoded conversation UUID from `frontend/src/portals/EmployeePortal.tsx`.
- Added first-message conversation creation through the shared API client.
- Added conversation ID state and authenticated message submission.
- Added pending, disabled, empty, retryable error, and human-takeover UI states.
- Added Gemini structured-content normalization before database persistence and API response rendering.
- Browser validation passed with a real VPN request and rendered AI/system messages.

## Sanitized Agent Activity

- Added a frontend `Agent activity` panel based on returned workflow metadata.
- Displays classification, diagnostic tool names, evidence count, escalation status, and final workflow status.
- Does not display private chain-of-thought, internal prompts, provider signatures, API keys, or raw sensitive evidence.
- Added structured workflow-state types in `frontend/src/api/types.ts`.
- Frontend build and lint passed after the change.

## Phase 2: Build the Frontend API and Session Layer

1. Create `frontend/src/api/types.ts` with types for:
   - Login response
   - Conversation response
   - Message response
   - Workflow state
   - API errors
2. Create `frontend/src/api/client.ts` with:
   - API base URL handling
   - JSON request helper
   - bearer-token injection
   - non-2xx error conversion
   - safe response parsing
3. Create `frontend/src/auth/session.ts` or `frontend/src/auth/AuthContext.tsx` to:
   - log in an employee
   - store the token in memory or session storage
   - expose the current user and token
   - clear an expired/invalid session
4. Add a small login screen or development login bootstrap in `frontend/src/App.tsx`.
5. Do not place API keys or LLM credentials in frontend code. Gemini credentials remain backend-only.

**Done when:** the frontend can authenticate and all API calls automatically carry the JWT.

## Phase 3: Connect Employee Conversation Lifecycle

1. Update `frontend/src/portals/EmployeePortal.tsx` to remove the hardcoded UUID.
2. On portal initialization or first send, call `POST /conversations`.
3. Store the returned conversation ID in component or session state.
4. Submit messages to `/conversations/{conversationId}/messages`.
5. Render the returned `messages` array in the chat window.
6. Render human-takeover responses as a clear waiting-for-engineer state.
7. Disable the send control while a request is pending.
8. Prevent empty or duplicate submissions.
9. Preserve the local user message when the request succeeds.
10. Show a retryable error when authentication, conversation creation, or message submission fails.

**Done when:** entering a VPN issue in the browser produces a real backend response from the configured Gemini/LangGraph workflow.

## Phase 4: Connect Engineer Dashboard

1. Update `frontend/src/portals/EngineerDashboard.tsx` to use `frontend/src/api/client.ts`.
2. Remove `DUMMY_ENGINEER_TOKEN`.
3. Add engineer authentication and role checking through the shared session layer.
4. Load tickets with the authenticated request.
5. Load similar incidents with the authenticated request.
6. Connect takeover to the backend endpoint.
7. Refresh the ticket/conversation state after takeover.
8. Add unauthorized, loading, empty, error, success, and pending states.

**Done when:** an engineer can see authorized tickets and take over an escalated conversation from the browser.

## Phase 5: Backend Response Normalization

1. Add a helper in `backend/src/core/llm.py` or a response utility to normalize LLM content blocks into displayable text.
2. Ensure Gemini, OpenAI, Grok, and compatible providers produce the same API message shape.
3. Ensure database `Message.content` always receives a string, not a provider-specific list.
4. Preserve workflow metadata such as category, status, evidence, and tool history separately from displayed text.
5. Add tests for plain string content and structured Gemini content blocks.

**Done when:** every supported provider returns a stable frontend-compatible message format.

## Phase 6: Tests and Browser Validation

1. Add `frontend/tests/employee-portal.test.tsx` for:
   - login
   - conversation creation
   - message send
   - assistant response
   - human takeover response
   - failed request
2. Add `frontend/tests/engineer-dashboard.test.tsx` for:
   - authenticated ticket loading
   - unauthorized access
   - takeover success
   - takeover failure
3. Update `frontend/e2e/workflow.spec.ts` to test the browser workflow.
4. Run backend tests with Docker services running.
5. Run frontend lint and build.
6. Run Playwright against `http://localhost:5173`.
7. Manually verify:
   - Employee login
   - VPN question
   - Gemini response or deterministic escalation
   - Engineer dashboard
   - Human takeover state

## Dependency Order

1. Phase 1: backend authentication contract
2. Phase 2: frontend API/session layer
3. Phase 3: employee conversation flow
4. Phase 5: response normalization, in parallel with Phase 4 where possible
5. Phase 4: engineer dashboard workflow
6. Phase 6: complete validation

## Parallel Work

- Backend auth endpoint and frontend API types can begin in parallel after agreeing on the token/response contract.
- Frontend API client and backend response normalization can proceed in parallel.
- Employee portal integration and engineer dashboard integration can proceed in parallel after the session layer exists.
- Unit tests can be written alongside each implementation phase.

## Security Requirements

- Never expose `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `XAI_API_KEY`, or provider base URLs requiring secrets to the browser.
- Keep all LLM calls server-side.
- Validate roles server-side; frontend role checks are only for presentation.
- Store only short-lived user sessions/tokens in the browser.
- Do not use `DUMMY_ENGINEER_TOKEN` in the final implementation.

## Final Verification Commands

```powershell
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec backend pytest tests/
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
cd frontend
npx playwright test
```

## Expected Success Result

A user opens `http://localhost:5173`, authenticates as an employee, enters an IT issue, and sees the configured Gemini agent response in the chat. If the issue triggers deterministic escalation, the UI shows that the conversation has been handed to an engineer rather than displaying a false AI resolution.
