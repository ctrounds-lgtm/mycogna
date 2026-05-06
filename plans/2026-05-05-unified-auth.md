# Plan: Unified Auth System

**Created:** 2026-05-05
**Status:** Implemented
**Request:** Merge two separate auth systems (portal `users` table + `storyteller_users` table) into a single auth system with a `role` column; one login screen with role-based routing.

---

## Overview

### What This Plan Accomplishes

A single `users` table handles all authentication for both the guardian portal and the storyteller app. A unified `/api/auth/login` endpoint returns a `role` field (`storyteller`, `portal_admin`, or `both`) and the login page routes accordingly — with a choice screen for users who belong to both systems. Password reset consolidates to one flow.

### Why This Matters

Users who sign up with the same email in both systems currently create two completely separate accounts with independently-stored passwords, causing confusing "incorrect password" errors. This fix ensures one email = one credential, regardless of which part of MyCogna the user accesses.

---

## Current State

### Relevant Existing Structure

| File | Role |
|------|------|
| `apps/cogna/server.py` | FastAPI backend — two separate session dicts, two sets of auth helpers |
| `apps/cogna/static/login.html` | Login page — currently calls `/api/storyteller/login` only |
| `apps/cogna/static/portal.js` | Portal JS — calls `/api/auth/login` and `/api/auth/register` |
| `apps/cogna/static/portal-signup.html` | Portal signup — calls `/api/auth/register` |
| `apps/cogna/static/storyteller.html` | Storyteller SPA — calls `/api/storyteller/login`, `/api/storyteller/signup`, `/api/storyteller/request-reset`, `/api/storyteller/reset-password` |
| `apps/cogna/supabase_schema.sql` | Schema — `users` and `storyteller_users` tables, separately defined |

**Two separate session stores in server.py:**
- `SESSIONS: Dict[str, str]` — portal tokens → email
- `STORY_SESSIONS: Dict[str, str]` — storyteller tokens → email

**`users` table columns:** `email, name, password_salt, password_hash, setup_type, tier, child_access_code, password_reset_token, password_reset_expires, created_at`

**`storyteller_users` table columns:** `id, email, first_name, last_name, password_salt, password_hash, signup_code, tier, managed, custom_prompts, password_reset_token, password_reset_expires, created_at`

### Gaps or Problems Being Addressed

- Same email in both tables creates two independent accounts with separate passwords
- Logging in via the wrong entry point gives an "incorrect password" error even with a correct password
- Two password reset flows with separate emails (`/portal?reset_token=...` vs `/login?reset_token=...`)
- No way for a user to reach both their portal and their storyteller account from a single login

---

## Proposed Changes

### Summary of Changes

- Add `role`, `first_name`, `last_name` columns to `users` table; make `child_access_code` nullable
- Migrate existing `storyteller_users` auth credentials into `users` (email conflict → upgrade to `role='both'`)
- Merge `STORY_SESSIONS` into `SESSIONS` in server.py (single in-memory token store)
- `POST /api/auth/login` returns `role` in its response; handles all users regardless of which system they came from
- `POST /api/auth/register` sets `role='portal_admin'`; if email already exists as storyteller, upgrades to `'both'`
- `POST /api/storyteller/signup` creates `users` record with `role='storyteller'` (+ `storyteller_users` record for app data); if email already in `users` as portal_admin, upgrades to `'both'`
- `POST /api/storyteller/login`, `/api/storyteller/request-reset`, `/api/storyteller/reset-password` become thin wrappers delegating to unified logic — storyteller.html needs no changes
- `login.html` updated to call `/api/auth/login`, detect role, and route — plus a new `panelChoice` screen for `role='both'`
- `portal.js` login handler adds a guard: if returned role is `'storyteller'` only, redirect to `/storyteller`
- `storyteller_users` table is preserved intact (FK anchor for recordings, memoir sessions, chapters); its `password_salt`, `password_hash`, etc. columns become unused but are not dropped (safe rollback)

### New Files to Create

None — all changes are to existing files.

### Files to Modify

| File | Changes |
|------|---------|
| `apps/cogna/supabase_schema.sql` | Migration SQL: add role/first_name/last_name to users, make child_access_code nullable, migrate storyteller_users credentials |
| `apps/cogna/server.py` | Merge session stores; update auth helpers, login, register, storyteller signup/login, reset endpoints; update `_public_user()` |
| `apps/cogna/static/login.html` | Call `/api/auth/login`; add `panelChoice`; role-based routing; unified reset endpoints |
| `apps/cogna/static/portal.js` | Add role guard in login handler — redirect storyteller-only users |

### Files to Delete (if any)

None.

---

## Design Decisions

### Key Decisions Made

1. **Keep `storyteller_users` table intact**: Its `id` column is the FK for `story_recordings`, `memoir_sessions`, `book_bibles`, and `chapters`. Merging those FKs into `users.email` would require cascading migrations across all story tables. The cleaner and safer approach is to keep `storyteller_users` for app data and use `users` for auth only.

2. **Merge STORY_SESSIONS into SESSIONS**: A single dict is simpler and eliminates the token namespace collision. The role field on the returned user tells the app which interface to render — not which dict the token lives in.

3. **Thin wrappers for storyteller-specific endpoints**: `/api/storyteller/login`, `/api/storyteller/request-reset`, and `/api/storyteller/reset-password` continue to exist but delegate to unified logic. This means storyteller.html requires zero changes for auth, reducing risk.

4. **Don't drop auth columns from storyteller_users**: After migration, `password_salt`, `password_hash`, `password_reset_token`, `password_reset_expires` on `storyteller_users` become unused but are not removed. This preserves a rollback path and avoids running a destructive migration.

5. **child_access_code becomes nullable**: Storyteller-only users have no portal and no child_access_code. Making it nullable is the correct schema change; existing portal admin rows are unaffected.

6. **Signup conflict resolution (both directions)**:
   - Storyteller signup with email already in `users` as `portal_admin` → create `storyteller_users` record, set `users.role = 'both'`
   - Portal register with email already in `users` as `storyteller` → update role to `'both'`, update password hash (new password wins)
   - Either direction produces one clean unified account

7. **`login.html` becomes the single login entry point**: The existing page already handles storyteller login. We extend it to handle portal login and the 'both' choice screen in the same card with three panels.

### Alternatives Considered

- **Full table merge (one table for everything)**: Would require rewriting all FK references across story tables. High risk, high migration complexity, rejected.
- **Supabase Auth**: The right long-term play but requires replacing all custom password hashing, reset flows, and session management. Deferred.
- **Keep two login pages**: Doesn't solve the root problem (same email, different passwords, different systems).

### Open Questions (if any)

None — all design decisions are resolved.

---

## Step-by-Step Tasks

### Step 1: Update `supabase_schema.sql` with migration SQL

Add a new migration section at the bottom of the file with SQL to run in Supabase. This SQL must be idempotent (safe to run again if needed).

**Actions:**

- Append a migration block titled `-- Migration: unified auth (2026-05-05)`
- Add `role`, `first_name`, `last_name` columns to `users`
- Make `child_access_code` nullable
- Migrate storyteller_users credentials into users with `ON CONFLICT` handling

**SQL to add:**

```sql
-- ─────────────────────────────────────────────
-- Migration: unified auth (2026-05-05)
-- Run once in Supabase SQL editor.
-- ─────────────────────────────────────────────

-- Add unified fields to the users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'portal_admin';
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT NOT NULL DEFAULT '';

-- child_access_code is only for portal admins; storyteller-only users won't have one
ALTER TABLE users ALTER COLUMN child_access_code DROP NOT NULL;

-- Migrate storyteller_users credentials into users.
-- If the email already exists (portal admin who also signed up as storyteller),
-- upgrade their role to 'both'. Otherwise insert as role='storyteller'.
INSERT INTO users (
  email,
  name,
  first_name,
  last_name,
  password_salt,
  password_hash,
  password_reset_token,
  password_reset_expires,
  role,
  child_access_code,
  created_at
)
SELECT
  su.email,
  TRIM(COALESCE(NULLIF(su.first_name, ''), '') || ' ' || COALESCE(NULLIF(su.last_name, ''), '')),
  su.first_name,
  su.last_name,
  su.password_salt,
  su.password_hash,
  su.password_reset_token,
  su.password_reset_expires,
  'storyteller',
  NULL,
  su.created_at
FROM storyteller_users su
ON CONFLICT (email) DO UPDATE SET
  role = 'both',
  first_name = EXCLUDED.first_name,
  last_name = EXCLUDED.last_name;
-- Note: existing portal admin password is preserved on conflict (we don't overwrite password_hash)
```

**Files affected:**
- `apps/cogna/supabase_schema.sql`

---

### Step 2: Merge session stores in server.py

Remove `STORY_SESSIONS` and update all storyteller auth helpers to use the unified `SESSIONS` dict.

**Actions:**

- Remove line: `STORY_SESSIONS: Dict[str, str] = {}  # storyteller token → email`
- Update `_create_story_session()`: write to `SESSIONS` instead of `STORY_SESSIONS`
  ```python
  def _create_story_session(email: str) -> str:
      token = secrets.token_urlsafe(32)
      SESSIONS[token] = email
      return token
  ```
- Update `_auth_storyteller_user()`: look up token in `SESSIONS` instead of `STORY_SESSIONS`, then load from `storyteller_users` by email:
  ```python
  def _auth_storyteller_user(authorization: Optional[str]) -> Dict[str, Any]:
      if not authorization or not authorization.startswith("Bearer "):
          raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")
      token = authorization.split(" ", 1)[1].strip()
      email = SESSIONS.get(token)
      if not email:
          raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
      user = _get_storyteller_user(email)
      if not user:
          raise HTTPException(status_code=401, detail="User not found")
      return user
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 3: Update Pydantic models for unified auth

Update `FamilyRegisterRequest` to accept an optional `role` override (rarely used, but allows server to set it). No new models needed.

**Actions:**

- No model changes required; role is derived server-side, not from client input.

---

### Step 4: Update `_public_user()` and `_get_user()` helpers

`_public_user()` must now return `role`, `first_name`, `last_name` so the frontend can route correctly.

**Actions:**

- Update `_public_user()` in server.py:
  ```python
  def _public_user(user: Dict[str, Any]) -> Dict[str, Any]:
      return {
          "email": user["email"],
          "name": user.get("name", ""),
          "first_name": user.get("first_name", ""),
          "last_name": user.get("last_name", ""),
          "setup_type": user.get("setup_type", "guardian"),
          "tier": user.get("tier", "A"),
          "child_access_code": user.get("child_access_code") or "",
          "role": user.get("role", "portal_admin"),
      }
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 5: Update `POST /api/auth/login` — unified login endpoint

The unified login now works for both portal admins and storytellers. It returns `role` in the response so the frontend can route appropriately.

**Actions:**

- The endpoint logic itself is unchanged (email lookup, password check, token creation)
- Ensure it returns `_public_user(user)` which now includes `role`
- No other changes needed to the login endpoint body — it already calls `_get_user(email)` which queries the `users` table

The response will now look like:
```json
{
  "token": "...",
  "user": {
    "email": "...",
    "name": "...",
    "first_name": "...",
    "last_name": "...",
    "role": "storyteller",   ← new field
    "tier": "A",
    "child_access_code": ""
  }
}
```

**Files affected:**
- `apps/cogna/server.py` (via `_public_user()` already updated in Step 4)

---

### Step 6: Update `POST /api/auth/register` — portal admin signup

Add `role='portal_admin'` to new accounts. Handle the conflict case where a storyteller-only user is registering for the portal.

**Actions:**

- In `auth_register()`, change the logic:
  ```python
  @app.post("/api/auth/register")
  def auth_register(payload: FamilyRegisterRequest):
      email = payload.email.strip().lower()
      existing = _get_user(email)
  
      setup_type = payload.setup_type if payload.setup_type in {"guardian", "self"} else "guardian"
      tier = payload.tier if payload.tier in {"A", "B", "C", "D", "E"} else "A"
  
      if existing:
          if existing.get("role") in ("portal_admin", "both"):
              raise HTTPException(status_code=400, detail="Account already exists")
          # Existing storyteller upgrading to 'both' — update role, update password
          salt = secrets.token_hex(8)
          password_hash = _hash_password(payload.password, salt)
          access_code = _generate_child_access_code(tier)
          _update_user(email, {
              "role": "both",
              "name": payload.name.strip(),
              "setup_type": setup_type,
              "tier": tier,
              "child_access_code": access_code,
              "password_salt": salt,
              "password_hash": password_hash,
          })
          user = _get_user(email)
          token = _create_session(email)
          return {"token": token, "user": _public_user(user)}
  
      salt = secrets.token_hex(8)
      password_hash = _hash_password(payload.password, salt)
      user = {
          "email": email,
          "name": payload.name.strip(),
          "first_name": "",
          "last_name": "",
          "password_salt": salt,
          "password_hash": password_hash,
          "setup_type": setup_type,
          "tier": tier,
          "role": "portal_admin",
          "child_access_code": _generate_child_access_code(tier),
          "created_at": _utc_now(),
      }
      _create_user(user)
      token = _create_session(email)
      return {"token": token, "user": _public_user(user)}
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 7: Update `POST /api/storyteller/signup` — storyteller signup

Handle the case where the email already exists in `users` as a portal_admin — upgrade to 'both' and create the `storyteller_users` record. If already a storyteller, raise 400 as before.

**Actions:**

- After the existing `existing = _get_storyteller_user(email)` check, add a check against `users`:
  ```python
  @app.post("/api/storyteller/signup")
  def storyteller_signup(payload: StorySignupRequest):
      # ... existing promo code validation ...
  
      email = payload.email.strip().lower()
      # ... existing email format + password length checks ...
  
      # Check storyteller_users first (existing storyteller account)
      existing_st = _get_storyteller_user(email)
      if existing_st:
          raise HTTPException(status_code=400, detail="An account with this email already exists. Please sign in instead.")
  
      # Check users table (existing portal admin upgrading to 'both')
      existing_u = _get_user(email)
  
      # ... existing tier/managed derivation from promo code ...
  
      user_id = "stuser_" + secrets.token_hex(8)
      salt = secrets.token_hex(8)
      pw_hash = _hash_password(payload.password, salt)
      st_user = {
          "id": user_id,
          "email": email,
          "first_name": payload.first_name.strip(),
          "last_name": payload.last_name.strip(),
          "password_salt": salt,
          "password_hash": pw_hash,
          "signup_code": code,
          "tier": user_tier,
          "managed": user_managed,
          "created_at": _utc_now(),
      }
      _create_storyteller_user(st_user)
  
      if existing_u:
          # Portal admin adding storyteller access — upgrade role
          _update_user(email, {
              "role": "both",
              "first_name": payload.first_name.strip(),
              "last_name": payload.last_name.strip(),
          })
      else:
          # New storyteller-only account — create users row for auth
          auth_user = {
              "email": email,
              "name": (payload.first_name.strip() + " " + payload.last_name.strip()).strip(),
              "first_name": payload.first_name.strip(),
              "last_name": payload.last_name.strip(),
              "password_salt": salt,
              "password_hash": pw_hash,
              "role": "storyteller",
              "child_access_code": None,
              "created_at": _utc_now(),
          }
          _create_user(auth_user)
  
      # ... existing recording transfer logic ...
  
      prompts = _get_active_prompts()
      token = _create_story_session(email)   # writes to unified SESSIONS
      return { ... }  # unchanged response format
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 8: Update storyteller auth endpoints as thin wrappers

`POST /api/storyteller/login` should now authenticate against the unified `users` table (not `storyteller_users`). `request-reset` and `reset-password` delegate to the unified flow.

**Actions:**

- Update `storyteller_login()` to check `users` table for credentials:
  ```python
  @app.post("/api/storyteller/login")
  def storyteller_login(payload: StoryLoginRequest):
      email = payload.email.strip().lower()
      # Authenticate against unified users table
      user = _get_user(email)
      if not user:
          raise HTTPException(status_code=401, detail="Invalid email or password")
      expected = _hash_password(payload.password, user["password_salt"])
      if expected != user["password_hash"]:
          raise HTTPException(status_code=401, detail="Invalid email or password")
  
      # Load storyteller-specific data (tier, managed, custom_prompts)
      st_user = _get_storyteller_user(email)
      if not st_user:
          raise HTTPException(status_code=403, detail="No storyteller account found for this email.")
  
      prompts = _get_active_prompts()
      token = _create_story_session(email)
      return {
          "token": token,
          "user": {
              "email": email,
              "first_name": st_user.get("first_name", user.get("first_name", "")),
              "last_name": st_user.get("last_name", user.get("last_name", "")),
              "signup_code": st_user.get("signup_code", ""),
              "tier": st_user.get("tier", "A"),
              "managed": bool(st_user.get("managed", False)),
              "this_month_count": _this_month_recording_count(st_user["id"]),
              "custom_prompts": _user_custom_prompts(st_user),
          },
          "prompts": [{"id": p["id"], "text": p["text"]} for p in prompts],
      }
  ```

- Update `storyteller_request_reset()` to delegate to unified `users` table:
  - Change `_get_storyteller_user(email)` → `_get_user(email)`
  - Change `_update_storyteller_user(email, {...})` → `_update_user(email, {...})`
  - Reset URL stays `/login?reset_token=...` (already correct)

- Update `storyteller_reset_password()` to use `users` table:
  - Change Supabase query from `storyteller_users` → `users`
  - Change `_update_storyteller_user()` → `_update_user()`

**Files affected:**
- `apps/cogna/server.py`

---

### Step 9: Update `_auth_storyteller_user()` fallback path

The helper currently loads `storyteller_users` by email. After the merge, tokens for storyteller users live in `SESSIONS` (done in Step 2). But the helper also validates the user exists in `storyteller_users` — this is still correct since storytellers do have a `storyteller_users` row.

**Actions:**

- Confirm the updated `_auth_storyteller_user()` from Step 2 is correct:
  1. Token in `SESSIONS` → email
  2. `_get_storyteller_user(email)` → verify the user still has a storyteller record
  3. Return the storyteller_users row (which has tier, managed, custom_prompts, id for FKs)
- No further change needed.

**Files affected:**
- `apps/cogna/server.py` (already done in Step 2)

---

### Step 10: Update `login.html` — role-based routing + choice screen

`login.html` is the single login entry point. Update it to:
1. Call `/api/auth/login` (unified)
2. Route by role after login
3. Add `panelChoice` for `role='both'` users
4. Call unified reset endpoints

**Actions:**

- Change the auto-redirect check at page load:
  ```js
  // Check for existing portal session
  const portalToken = localStorage.getItem('portalToken');
  if (portalToken && !resetToken) {
    fetch('/api/auth/me', { headers: { Authorization: 'Bearer ' + portalToken } })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) routeByRole(data.user, portalToken); })
      .catch(() => {});
  }
  // Check for existing storyteller session
  const stToken = localStorage.getItem('st_token');
  if (stToken && !resetToken && !portalToken) {
    fetch('/api/auth/me', { headers: { Authorization: 'Bearer ' + stToken } })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) routeByRole(data.user, stToken); })
      .catch(() => {});
  }
  ```

- Add `routeByRole(user, token)` helper:
  ```js
  function routeByRole(user, token) {
    const role = user.role || 'storyteller';
    if (role === 'both') {
      // Store token in both slots so either app works after choice
      localStorage.setItem('portalToken', token);
      localStorage.setItem('st_token', token);
      localStorage.setItem('st_email', user.email);
      localStorage.setItem('st_first_name', user.first_name || '');
      showPanel('panelChoice');
    } else if (role === 'portal_admin') {
      localStorage.setItem('portalToken', token);
      window.location.href = '/portal';
    } else {
      localStorage.setItem('st_token', token);
      localStorage.setItem('st_email', user.email);
      localStorage.setItem('st_first_name', user.first_name || '');
      window.location.href = '/storyteller';
    }
  }
  ```

- Update `handleLogin()` to call `/api/auth/login` and use `routeByRole`:
  ```js
  async function handleLogin(e) {
    e.preventDefault();
    // ...existing error clear + field read...
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) { /* show error */ return; }
      routeByRole(data.user, data.token);
    } catch (err) { /* show error */ }
  }
  ```

- Update `handleReset()` to call `/api/auth/request-reset`
- Update `handleNewPassword()` to call `/api/auth/reset-password`

- Add `panelChoice` HTML panel after `panelNewPassword`:
  ```html
  <!-- Choice panel (for users with both portal and storyteller access) -->
  <div id="panelChoice" class="panel">
    <div class="card-title">Welcome back</div>
    <div class="card-sub">Where would you like to go?</div>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:8px">
      <button class="btn-primary" onclick="window.location.href='/storyteller'">
        Go to my stories →
      </button>
      <button class="btn-primary" style="background:transparent;color:var(--ink);border:1.5px solid var(--border)"
              onclick="window.location.href='/portal'">
        Go to my portal →
      </button>
    </div>
  </div>
  ```

**Files affected:**
- `apps/cogna/static/login.html`

---

### Step 11: Update `portal.js` login handler — add role guard

If a storyteller-only user somehow reaches the portal login, redirect them gracefully.

**Actions:**

- In the `loginForm` submit handler in `portal.js`, after receiving the response:
  ```js
  const result = await req(`${api}/auth/login`, { ... });
  if (result.user && result.user.role === 'storyteller') {
    // Storyteller account — redirect to storyteller app
    localStorage.setItem('st_token', result.token);
    localStorage.setItem('st_email', result.user.email);
    localStorage.setItem('st_first_name', result.user.first_name || '');
    window.location.href = '/storyteller';
    return;
  }
  state.token = result.token;
  localStorage.setItem('portalToken', result.token);
  await loadDashboard();
  ```

**Files affected:**
- `apps/cogna/static/portal.js`

---

### Step 12: Run Supabase migration SQL

**Actions (user must perform this step in Supabase SQL editor):**

1. Open Supabase → SQL editor
2. Run the migration block added in Step 1:
   - `ALTER TABLE users ADD COLUMN IF NOT EXISTS role ...`
   - `ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name ...`
   - `ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name ...`
   - `ALTER TABLE users ALTER COLUMN child_access_code DROP NOT NULL`
   - `INSERT INTO users ... FROM storyteller_users ... ON CONFLICT ...`
3. Verify row counts: `SELECT role, COUNT(*) FROM users GROUP BY role`
4. Confirm no existing portal admin rows were accidentally modified

---

### Step 13: Verify existing accounts still work

**Actions (user manually tests):**

1. Log in with the Duluth Sister Cities email via `/login` — should route to storyteller (or choice screen if it has a portal account too)
2. Log in with personal email via `/login` — should route to correct destination
3. Log in via `/portal` → portal login tab — should work for portal_admin accounts
4. Test password reset: request reset for a storyteller account → confirm email arrives → set new password → confirm login works
5. Test new storyteller signup with an email that already has a portal account → should upgrade to 'both'

---

### Step 14: Update `supabase_schema.sql` documentation header

Add a note at the top of the file clarifying the current architecture.

**Actions:**

- Update the comment block at the top to note that `users` is the unified auth table and `storyteller_users` is the storyteller app-data table (auth columns on `storyteller_users` are deprecated as of 2026-05-05).

**Files affected:**
- `apps/cogna/supabase_schema.sql`

---

## Connections & Dependencies

### Files That Reference This Area

- `apps/cogna/static/signup.html` — calls `/api/auth/register`; this file is for a flow that may be unused or deprecated; review to confirm it doesn't conflict
- `apps/cogna/static/portal-signup.html` — calls `/api/auth/register`; no change needed (register endpoint updated in Step 6)
- `apps/cogna/static/storyteller.html` — calls `/api/storyteller/login`, `/api/storyteller/request-reset`, `/api/storyteller/reset-password`; no change needed (endpoints updated in Step 8 as wrappers)

### Updates Needed for Consistency

- CLAUDE.md: update MyCogna auth section to describe unified auth
- `supabase_schema.sql` documentation header

### Impact on Existing Workflows

- Existing portal sessions (tokens in `SESSIONS` dict) will be lost on server restart — this is the existing behavior (in-memory tokens), not a regression
- Existing storyteller sessions (tokens in `STORY_SESSIONS` dict) will also be lost on restart — same as above. Users will need to log in once after deploy.
- All existing stored passwords remain valid — we're migrating credentials, not rehashing them

---

## Validation Checklist

- [ ] Supabase migration SQL runs without error
- [ ] `SELECT role, COUNT(*) FROM users GROUP BY role` shows expected counts
- [ ] Storyteller login via `/login` works for a storyteller-only account → routes to `/storyteller`
- [ ] Portal login via `/portal` works for a portal-admin account → loads dashboard
- [ ] Portal login via `/portal` with storyteller-only email → redirects to `/storyteller`
- [ ] Login via `/login` with `role='both'` account → shows choice screen
- [ ] Choice screen "Go to my stories" → navigates to `/storyteller`
- [ ] Choice screen "Go to my portal" → navigates to `/portal`
- [ ] Password reset from `/login` → email arrives → new password works
- [ ] Storyteller signup with new email creates `users` row with `role='storyteller'` AND `storyteller_users` row
- [ ] Storyteller signup with email that's already a portal admin → upgrades to `role='both'`, both apps accessible
- [ ] Portal register with email that's already a storyteller → upgrades to `role='both'`
- [ ] No regression: recording, memoir, Cogna features all work after login

---

## Success Criteria

The implementation is complete when:

1. A single email address can be used to access both the portal and the storyteller app, with one password
2. Logging in via `/login` routes users to the correct destination without error
3. Users with access to both systems see a choice screen after login
4. Password reset works for all account types from a single reset flow
5. All existing test accounts continue to function

---

## Notes

- The local JSON fallback (used when `SUPABASE_URL` is unset) also has a `users` dict and a `storyteller_users` dict. The server.py changes must handle both paths. The migration SQL in Step 1 only applies to Supabase; for local JSON, accounts created after this deploy will be correct by default, but any existing local-only test data will not be migrated automatically.
- Future consideration: once this is stable, the auth columns (`password_salt`, `password_hash`, etc.) can be dropped from `storyteller_users` in a follow-up migration. Don't rush this — verify everything works first.
- The in-memory `SESSIONS` dict means sessions are lost on server restart. This is the same behavior as before. Future work: persist sessions to Supabase if Railway restarts become frequent.

---

## Implementation Notes

**Implemented:** 2026-05-05

### Summary

All 14 steps executed. Four files modified: supabase_schema.sql (migration SQL + header comment), server.py (merged session stores, updated register/signup/login/reset endpoints, updated _public_user), login.html (unified login call, routeByRole helper, panelChoice screen, unified reset endpoints), portal.js (role guard in login handler).

### Deviations from Plan

- Step 3 confirmed no-op as specified (no Pydantic model changes needed).
- Step 9 confirmed no-op as specified (already handled in Step 2).
- Step 12 is a user action (run SQL in Supabase) — not automated.
- Step 13 is a user action (manual testing) — not automated.

### Issues Encountered

None — all changes applied cleanly.
