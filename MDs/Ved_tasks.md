# Ved Tasks: AI Helpdesk Remediation

**Date:** 2026-09-08  
**Current state:** Docker stack runs; frontend needs build, UX, authentication, and test completion.

## Priority 1: Make the frontend buildable

- [x] **T001** Create `frontend/tsconfig.json` with strict React/Vite settings and include all TypeScript source files.
- [x] **T002** Run `docker compose exec frontend npm run build` and fix all TypeScript or Vite build errors.
- [x] **T003** Align TypeScript and `@typescript-eslint` versions in `frontend/package.json` so lint uses supported versions.
- [x] **T004** Run `docker compose exec frontend npm run lint` and resolve all warnings and errors.

## Priority 2: Improve the frontend appearance

- [x] **T005** Create `frontend/src/styles.css` with the application layout, typography, colors, spacing, forms, buttons, chat messages, dashboard rows, and responsive behavior.
- [x] **T006** Import the stylesheet from `frontend/src/main.tsx`.
- [x] **T007** Add visible focus, hover, disabled, loading, error, empty, and success states for interactive controls.
- [x] **T008** Verify the employee portal and engineer dashboard at desktop and mobile viewport sizes.

## Priority 3: Fix employee chat workflow

- [ ] **T009** Create a typed API client in `frontend/src/api/client.ts` for JSON requests, API errors, and authentication headers.
- [ ] **T010** Replace the hardcoded conversation UUID in `frontend/src/portals/EmployeePortal.tsx` with conversation creation or resume behavior.
- [ ] **T011** Store the active conversation ID and use it for subsequent messages.
- [ ] **T012** Add sending, disabled, retry, request error, empty conversation, and assistant response states.
- [ ] **T013** Ensure Enter submits the form without allowing accidental duplicate submissions.

## Priority 4: Fix engineer dashboard security and workflow

- [ ] **T014** Define the frontend authentication/session contract in `frontend/src/auth/` based on the backend login and RBAC API.
- [ ] **T015** Remove `DUMMY_ENGINEER_TOKEN` from `frontend/src/portals/EngineerDashboard.tsx`.
- [ ] **T016** Load tickets through the shared authenticated API client.
- [ ] **T017** Add unauthorized, loading, request-error, empty-ticket, and similar-incident states.
- [ ] **T018** Add takeover pending, success, failure, and refresh behavior.
- [ ] **T019** Prevent duplicate takeover submissions while a request is active.

## Priority 5: Retrieval and API integration

- [ ] **T020** Define shared response types for tickets and similar incidents in `frontend/src/api/types.ts`.
- [ ] **T021** Render related incidents only from authenticated API responses.
- [ ] **T022** Add a clear empty state when no similar incidents are returned.
- [ ] **T023** Confirm the Vite API proxy works in Docker and configure host-local development through `frontend/.env.example`.

## Priority 6: Tests

- [ ] **T024** Add `frontend/tests/employee-portal.test.tsx` for conversation creation, message submission, assistant response, and failed requests.
- [ ] **T025** Add `frontend/tests/engineer-dashboard.test.tsx` for authenticated loading, unauthorized access, takeover success, and takeover failure.
- [ ] **T026** Add `frontend/tests/retrieval-results.test.tsx` for similar-incident rendering and empty results.
- [ ] **T027** Update `frontend/e2e/workflow.spec.ts` with employee portal and engineer dashboard smoke coverage.
- [ ] **T028** Run backend tests with the Docker database available.
- [ ] **T029** Run frontend lint, build, unit tests, and Playwright tests.

## Priority 7: Runtime and documentation cleanup

- [ ] **T030** Remove the obsolete `version` field from `docker-compose.yml`.
- [ ] **T031** Add `.env.example` documenting database, security, and optional OpenAI settings without committing secrets.
- [ ] **T032** Update `setup.md` with the corrected Docker startup, migration, and frontend verification commands.
- [ ] **T033** Update `Ved_log.md` with final test results and unresolved issues.

## Dependency Order

1. Complete T001-T004 before relying on frontend build or lint results.
2. Complete T005-T008 before visual review.
3. Complete T009 before T010-T023.
4. Complete T014-T019 before engineer dashboard integration tests.
5. Complete T024-T029 after the corresponding portal workflows are implemented.
6. Complete T030-T033 after the runtime and test results are known.

## MVP Definition

The MVP is complete when T001-T019 are finished, the Docker stack is running, the employee portal can create and continue a conversation, engineer requests use real authentication, and both portals display clear loading and failure states.

## Final Verification Commands

```powershell
docker compose up --build -d
docker compose exec backend alembic upgrade head
docker compose exec frontend npm run lint
docker compose exec frontend npm run build
docker compose ps
```
