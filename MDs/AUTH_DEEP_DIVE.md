# Authentication Deep Dive

> Last reviewed: 2026-09-21 · Branch: `ved`

Complete overview of how authentication, authorization, password handling, and session management work in the AI L1 IT Helpdesk app.

---

## 1. TL;DR

| Aspect | What we use |
|---|---|
| Framework | FastAPI (Python, async) |
| Password hashing | **bcrypt** via `passlib` (`CryptContext(schemes=["bcrypt"], deprecated="auto")`) |
| bcrypt version pin | `bcrypt<4.0.0` (compatibility pin for passlib 1.7.x) |
| Token type | **JWT (Bearer token)** |
| JWT algorithm | **HS256** (symmetric HMAC-SHA256) |
| JWT library | `python-jose` (`jose.jwt`) — `python-jose[cryptography]>=3.3.0` |
| Secret | `SECRET_KEY` env var, with dev fallback `"change-this-development-secret"` |
| Token lifetime | **24 hours** (`ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24`) |
| Token transport | `Authorization: Bearer <token>` header |
| Frontend storage | `sessionStorage` (cleared when the browser tab closes) |
| Login endpoint | `POST /auth/login` (OAuth2 password form, `x-www-form-urlencoded`) |
| Signup endpoint | `POST /auth/signup` (JSON, heavily validated, employee-only) |
| Authorization | Role-based access control (RBAC) via `RoleChecker` dependency |
| Core file | `backend/src/auth/security.py` |

---

## 2. Backend Architecture

### 2.1 File map

```
backend/src/auth/security.py      ← Core: hashing, JWT, get_current_user, RoleChecker
backend/src/api/auth.py           ← Routes: /auth/login, /auth/signup, /auth/me
backend/src/models/user.py        ← User model + UserRole enum
backend/src/core/seed.py          ← Default account seeding on startup
backend/tests/core/test_auth.py   ← Unit tests for all of the above
frontend/src/auth/session.ts      ← Token persistence (sessionStorage)
frontend/src/api/client.ts        ← Attaches Authorization header to every request
```

### 2.2 The `User` model (`backend/src/models/user.py`)

```python
class UserRole(str, enum.Enum):
    employee = "employee"
    l1 = "l1"               # L1 support engineer
    l2 = "l2"               # L2 support engineer
    support_lead = "support_lead"
    admin = "admin"

class User(Base):
    __tablename__ = "users"
    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name            = Column(String, nullable=False)
    email           = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)   # bcrypt hash, NEVER plaintext
    role            = Column(Enum(UserRole), default=UserRole.employee, nullable=False)
    department      = Column(String, nullable=True)
```

- Emails are stored **lowercased** everywhere (`email.strip().lower()` before any lookup).
- The user's email is the identity key in JWTs (`sub` claim).

---

## 3. Password Hashing — the details

### 3.1 Algorithm: bcrypt

```python
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
```

- **Hash:** bcrypt (adaptive, salted, intentionally slow).
- **Salt:** generated automatically per-hash by passlib and embedded in the hash string — no manual salt management.
- **Format:** standard Modular Crypt Format, e.g.
  `$2b$12$<22-char-salt><31-char-checksum>`
  - `$2b$` = bcrypt version
  - `12` = cost factor (passlib default of 12 rounds, 2^12 iterations)
- `deprecated="auto"` means: if a stored hash used a deprecated scheme, passlib flags it for upgrade on next successful verify. (We only have one scheme, so this is future-proofing.)

### 3.2 API

| Function | Purpose |
|---|---|
| `get_password_hash(plain) -> str` | Hash a plaintext password with bcrypt (called on signup + seeding) |
| `verify_password(plain, hashed) -> bool` | Constant-ish-time bcrypt verification (called on login + seeding) |

Notes:
- bcrypt truncates input at **72 bytes**; the signup validator caps passwords at 128 chars, which is fine.
- Login wraps `verify_password` in a `try/except (ValueError, UnknownHashError)` so a corrupted or legacy hash in the DB returns a clean `401` instead of a 500.

### 3.3 Dependency pins (why `bcrypt<4.0.0`)

`requirements.txt`:
```
passlib[bcrypt]>=1.7.4
bcrypt<4.0.0
```
passlib 1.7.4 breaks with bcrypt ≥ 4.1 (it probes a private attribute that was removed, logging `error reading bcrypt version` and, in some paths, failing). The pin keeps the stable passlib+bcrypt combo. Long-term fix would be migrating off passlib to `bcrypt` directly or `pwdlib`.

---

## 4. JWT Tokens — the details

### 4.1 Configuration

```python
SECRET_KEY = os.getenv("SECRET_KEY", "change-this-development-secret")
ALGORITHM  = "HS256"                       # HMAC-SHA256, symmetric
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24      # 24 hours
```

- **HS256 = symmetric**: the same `SECRET_KEY` both signs and verifies. Keep it server-side only; never ship it to the frontend.
- The fallback dev secret is a placeholder — **production must set `SECRET_KEY`** or anyone can forge tokens.
- Expiry is set via the standard `exp` claim (`datetime.utcnow() + delta`).

### 4.2 Token creation (`create_access_token`)

Issued at both login and signup with these claims:

```python
{
  "sub": user.email,                 # subject = email (used by get_current_user)
  "user_id": str(user.id),           # UUID as string
  "role": "employee" | "l1" | ... ,  # role value
  "department": user.department or "general",
  "exp": <utcnow + 24h>,             # expiry
}
```

⚠️ Note: `role`/`department` in the payload are **informational**. `get_current_user` does **not** trust them — it re-loads the user from the DB on every request (see 4.3), so role changes take effect immediately without waiting for token expiry.

### 4.3 Token verification (`get_current_user`)

Every protected endpoint depends on this:

```python
async def get_current_user(token = Depends(oauth2_scheme), db = Depends(get_db)) -> dict
```

Flow:
1. `OAuth2PasswordBearer(tokenUrl="auth/login")` extracts the `Authorization: Bearer` header (401 if missing).
2. `jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])` — verifies signature **and** `exp`. Any `JWTError` → `401 Could not validate credentials` with `WWW-Authenticate: Bearer`.
3. Reads `sub` (email) from the payload; missing → 401.
4. **Looks the user up in the DB** (`email == sub.strip().lower()`); missing → 401. This means: deleted/disabled users lose access instantly even with a valid token.
5. Returns a plain dict used downstream as the "current user" context:

```python
{
  "id": str(user.id),
  "username": user.email,     # note: username == email in this codebase
  "email": user.email,
  "name": user.name,
  "role": role_val,           # string, e.g. "employee"
  "department": user.department or "general",
}
```

### 4.4 Endpoints (`backend/src/api/auth.py`)

**`POST /auth/login`** — OAuth2 password flow
- Accepts `OAuth2PasswordRequestForm` (`application/x-www-form-urlencoded`, fields `username` + `password`; the frontend passes the email as `username`).
- Looks up by lowercased email. Unknown user **or** wrong password → identical `401 "Incorrect email or password"` (no user-enumeration signal).
- On success returns:
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": { "id", "name", "email", "role", "department" }
}
```

**`POST /auth/signup`** — JSON, with the strictest validation in the app (see §5)
- Duplicate email → `409`.
- Role escalation guard: only `role="employee"` is accepted via public signup. Anything else → `400 "Public signup is restricted to employee accounts only. Engineer and admin accounts must be provisioned by an administrator."`
- Also returns an access token immediately (auto-login).

**`GET /auth/me`** — returns the current user dict from `get_current_user`. Used by the frontend to hydrate a session after page reload.

### 4.5 Startup seeding (`backend/src/core/seed.py`)

`seed_default_users` runs in the FastAPI lifespan on every boot and is **idempotent**:

| Account | Role | Password |
|---|---|---|
| `employee@example.com` (or `DEV_USER_EMAIL`) | employee | `dev-password` (or `DEV_USER_PASSWORD`) |
| `engineer@example.com` | l1 | `dev-password` |
| `l1@example.com` | l1 | `dev-password` |
| `admin@example.com` | admin | `dev-password` |

- If the user doesn't exist → created with a fresh bcrypt hash.
- If the user exists but the password hash no longer matches the seed password → **re-hashed and updated** (also roles/departments are reconciled). This guarantees seed accounts always work with the seed password.
- All wrapped in try/except with rollback so a seeding failure can't crash the app.

---

## 5. Signup Validation Rules

`SignupRequest` (Pydantic v2) enforces, in order:

**Field validators**
- `name`: 1–100 chars, letters only (`^[a-zA-Z]+$`) — no spaces, digits, or symbols.
- `email`: 3–255 chars, must contain `@` and a dot in the domain; lowercased.
- `password`: 8–128 chars.

**Password model validator**
| Rule | Rejection message (abridged) |
|---|---|
| ≥ 8 chars | "must be at least 8 characters long" |
| ≥ 1 uppercase | "must include at least 1 uppercase letter" |
| ≥ 1 lowercase | "must include at least 1 lowercase letter" |
| ≥ 1 number | "must include at least 1 number" |
| ≥ 1 of `!@#$%^&*` | "must include at least 1 special character" |
| must not contain the user's name | "must not contain your name" |
| must not contain the email / email prefix | "must not contain your email..." |
| not in a hard-coded common-password blocklist (`password123!`, `qwertyuiop`, ...) | "must not use common passwords" |
| must not contain a year pattern `19xx` / `20xx` | "birthday or year" |
| must not contain company/helpdesk/role terms (`company`, `helpdesk`, `admin`, `support`, ...) | "company or role names" |
| must not contain the department name (≥ 3 chars) | "department name" |

All validation errors surface as a single friendly `422` message thanks to the custom `RequestValidationError` handler in `main.py`.

---

## 6. Authorization (RBAC)

### 6.1 `RoleChecker` dependency

```python
RoleChecker(["engineer", "l1", ...])(user) -> dict  # or raises 403
```

- Constructor normalizes roles to strings.
- **`engineer` ⇄ `l1` aliasing:** if either is in the allowed set, both are accepted (historical naming inconsistency; `UserRole` only has `l1`).
- Applied per-endpoint (or router-wide) via FastAPI `Depends`.
- Deny → `403 "Operation not permitted"`; the user dict passes through on success.

### 6.2 Where it's applied

| Route(s) | Protection |
|---|---|
| `/diagnostics/*` | Router-level `RoleChecker(["employee", "l1", "l2"])` |
| `/tickets` (list), `/tickets/{id}/resolve`, `/tickets/{id}/similar` | `RoleChecker(["engineer", "l1", "l2", "support_lead", "admin"])` (support staff only) |
| `/tickets/{id}/confirm-resolution` | `get_current_user` + **ownership check**: `ticket.user_id == user.id`, else `403` |
| `/conversations` (list/create), messages read/post, close | `get_current_user` + ownership check (owner or support-staff role) |
| `/conversations/{id}/takeover` | `RoleChecker` support roles only (human takeover of AI conversation) |

Pattern used for object-level authz (conversations/tickets):
```python
is_support = user.get("role") in {"engineer", "l1", "l2", "support_lead", "admin"}
if not is_support and str(conversation.user_id) != user_id_str:
    raise HTTPException(403, "Not authorized ...")
```

---

## 7. Frontend Session Handling

`frontend/src/auth/session.ts`:

- Token + user object are stored in **`sessionStorage`** under:
  - `helpdesk_access_token`
  - `helpdesk_user` (JSON)
- `sessionStorage` scope: per-tab, cleared when the tab closes. More XSS-resilient in lifetime than `localStorage` (token doesn't survive closing the tab), but still readable by JS — XSS remains a threat vector (see §9).
- `frontend/src/api/client.ts` → the `request()` helper attaches `Authorization: Bearer <token>` to **every** API call and raises typed `ApiError` from error responses.
- Login/signup responses call `saveSession(...)` in `App.tsx`; there is no refresh token — when the 24h token expires the user simply logs in again.

---

## 8. Test Coverage

`backend/tests/core/test_auth.py` covers:
- bcrypt hash/verify round-trip (correct + wrong password).
- JWT creation round-trip.
- `RoleChecker` allow/deny + `engineer`/`l1` aliasing (403 checks).
- `get_current_user` resolving a user from a mock DB via `sub`.
- Login with invalid creds → 401; valid creds → token + user payload.
- Signup: new user creation, 409 on duplicate email, **privilege-role rejection** (engineer/admin/l1 → 400).
- Signup name and password validation rules (each rejection path).

---

## 9. Known Weaknesses / Production TODOs

1. **`SECRET_KEY` fallback** — the hardcoded `"change-this-development-secret"` means a deployment that forgets the env var silently uses a publicly-known key → token forgery. Consider failing fast in prod (e.g., raise at startup if unset when `ENV=production`).
2. **No refresh tokens / revocation** — a stolen 24h token is valid until expiry; no logout invalidation server-side (frontend logout only clears `sessionStorage`). A short-lived access token + refresh token, or a denylist, would tighten this.
3. **No rate limiting / lockout on `/auth/login`** — brute-force attempts are unthrottled. Consider `slowapi`/nginx rate limits or account lockout.
4. **Token in `sessionStorage`** — still XSS-readable; `httpOnly`, `Secure`, `SameSite` cookies are the hardened alternative.
5. **JWT payloads include role/department** — currently unused for decisions (good), but beware anyone relying on them later; always trust the DB like `get_current_user` does.
6. **Seeded default accounts with known passwords** (`dev-password`) — fine for dev; ensure they're disabled or re-passworded before any real deployment.
7. **passlib is unmaintained** — the `bcrypt<4.0.0` pin is a compatibility shim; plan a migration to `bcrypt` directly (or `pwdlib`).
8. **`datetime.utcnow()`** is deprecated in Python 3.12+ (naive datetime); switch to `datetime.now(timezone.utc)` when convenient.

---

## 10. Quick Reference

**Login:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=employee@example.com&password=dev-password"
```

**Authenticated call:**
```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer <access_token>"
```

**Swagger UI** (`/docs`) uses the OAuth2 password flow against `auth/login`, so you can authenticate interactively there too.
