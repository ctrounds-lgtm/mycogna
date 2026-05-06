# Plan: Tier-Based Routing for MyCogna Storyteller

**Created:** 2026-05-04
**Status:** Implemented
**Request:** Implement tier-based routing and feature gating across the MyCogna storyteller app, memoir tool, and portal for five user tiers (A–E).

---

## Overview

### What This Plan Accomplishes

Adds tier awareness to every screen a storyteller user touches: the right features unlock at the right tier, and users below a feature's tier see a dismissible upgrade prompt rather than a broken or missing button. Tier E institutional invitees get a clean, managed experience — unlimited recording, no AI features, no upgrade noise — controlled by a `managed` flag.

### Why This Matters

Right now every storyteller user has access to every button regardless of what they've paid for. Before we can charge for tiers B, C, and D, the app needs to enforce those gates. This plan creates the data model, API changes, and frontend logic to make that work end-to-end — without blocking any user from features they've already unlocked.

---

## Current State

### Relevant Existing Structure

- `apps/cogna/static/storyteller.html` — single-page app, screens: Entry, Signup, Login, Reset, Onboarding, PromptSelect, Record, Processing, Done, MyStories. No tier logic anywhere.
- `apps/cogna/static/memoir.html` — AI memoir tool, accessed via direct link from storyteller. No tier gate.
- `apps/cogna/static/index.html` — marketing homepage + companion entry. No auth awareness, static links to `/storyteller` and `/signup`.
- `apps/cogna/static/portal.js` + `portal.html` — guardian portal. Tier E panel generates tier 'B' codes (this will change).
- `apps/cogna/server.py` — FastAPI backend. Storyteller auth endpoints (`/signup`, `/login`, `/me`) return user email, first_name, signup_code, custom_prompts — **no tier, no managed flag**.
- `apps/cogna/supabase_schema.sql` — Supabase schema. `storyteller_users` table has: id, email, first_name, last_name, password_salt, password_hash, signup_code, custom_prompts, created_at — **no tier, no managed column**.
- `apps/cogna/supabase_schema.sql` — `promo_codes` table has: code, tier (A/B/C/D), description, active, created_by, created_at. Tier 'E' is not yet a valid code tier.

### Gaps or Problems Being Addressed

1. `storyteller_users` has no `tier` or `managed` column — tier is not stored per user, only on the promo code.
2. Auth API responses never return tier or managed — frontend cannot make tier decisions.
3. Tier E promo codes are generated as tier 'B' codes — no way to detect a managed invitee at signup.
4. All feature buttons (Go Deeper, My Memoir, Record Another) are always visible regardless of tier.
5. No monthly recording counter exists for tier A limits.
6. Tier D users have no choice screen — they land on the same flow as everyone else.
7. Managed (tier E invitee) accounts would see the same upgrade prompts as free users.

---

## Proposed Changes

### Summary of Changes

- Add `tier` and `managed` columns to `storyteller_users` Supabase table
- Create tier 'E' as a valid promo code tier (generates `E-XXXX` codes) — signals "managed storyteller invitee"
- At signup, derive and store the invitee's tier and managed flag from the promo code
- Update all storyteller auth API responses to include `tier`, `managed`, and `this_month_count`
- Store `st_tier` and `st_managed` in localStorage alongside the existing auth keys
- Add an upgrade modal component to storyteller.html (dismissible, never blocking)
- Add `screenChoice` to storyteller.html for tier D users
- Gate: "Go deeper with AI →" (C+), "My Memoir →" (C+), "Record another" for tier A (1/month), Cogna access (D only)
- Managed accounts: hide AI buttons entirely, never show upgrade prompts
- Update portal panel E to generate tier 'E' codes (not tier 'B')

### New Files to Create

None — all changes are to existing files.

### Files to Modify

| File Path | Changes |
|-----------|---------|
| `apps/cogna/supabase_schema.sql` | Add migration SQL for `tier` and `managed` columns on `storyteller_users`; add tier 'E' note |
| `apps/cogna/server.py` | Update signup/login/me to store and return tier+managed; allow tier 'E' promo codes; add monthly count |
| `apps/cogna/static/storyteller.html` | Add tier/managed to stState + localStorage; add upgrade modal; add screenChoice; gate all tier-dependent buttons |
| `apps/cogna/static/portal.js` | Change panel E code generation from tier 'B' to tier 'E' |

---

## Design Decisions

### Key Decisions Made

1. **Tier E promo codes use a distinct `E` code tier (not `B`).** When an E-admin generates a code, it now creates `E-XXXX` codes. At signup, the server sees a tier-E promo code and sets the invitee's `tier = 'B'` (unlimited recording) and `managed = true`. The `managed` flag is the gate for AI features — not the tier. This separates *what you can do* (tier B recording) from *how you came here* (managed).

2. **Tier is stored on `storyteller_users`, not derived at runtime.** Deriving it at every request requires a join through promo_codes — fragile if codes are deactivated. Storing it at signup is authoritative and fast. A one-time migration query sets existing users' tiers from their signup_code.

3. **Monthly recording count for tier A is computed in `/me`, not stored separately.** A simple `COUNT(*)` query on `story_recordings WHERE storyteller_user_id = ? AND created_at >= first_of_month` is cheap, accurate, and requires no new table.

4. **Upgrade prompts are a dismissible overlay, never a gate.** Following the product spec exactly: users on lower tiers see the prompt but can dismiss it. Tier A users who dismiss the upgrade prompt on "Record Another" simply stay on the Done screen — they've had their one story, but they're not thrown out of the app.

5. **Tier D's choice screen lives in storyteller.html, not index.html.** The companion side is a separate app (`/companion`, `index.html`). The storyteller handles its own routing post-auth. When a tier D user lands on `/storyteller`, the `_showPromptSelect()` routing logic intercepts and shows `screenChoice` instead. "Talk to a Cogna" is just `window.location = '/'` (the companion entry).

6. **Managed users see no upgrade prompts and no AI buttons at all.** Hiding the buttons entirely (rather than showing a disabled state) is cleaner for the managed UX — the institutional context doesn't expect or explain upgrades.

7. **`st_tier` and `st_managed` are stored in localStorage.** Same pattern as existing `st_token`, `st_email`, `st_first_name`. Cleared on logout.

### Alternatives Considered

- **Derive tier from promo code at every request**: Rejected — fragile (deactivated codes), adds a DB join to every auth check, and makes the frontend dependent on always having a signup_code.
- **A single "feature flags" object in the API response instead of tier + managed**: Rejected — too abstract. Tier is a legible business concept; managed is a clear flag. Both are needed separately.
- **Put tier D choice screen at a new `/start` route**: Rejected — adds another page, more routing complexity. Handling it inside storyteller.html's existing screen system is simpler and consistent.
- **Block tier A after 1 story per month at the server level**: Considered but rejected. The spec says prompts are dismissible and never block. Server-side enforcement would return a hard error. Frontend enforcement with an upgrade modal respects the spec.

### Open Questions

None — all design decisions are resolved above. Implementation can proceed directly.

---

## Step-by-Step Tasks

### Step 1: Database Schema Migration

Add `tier` and `managed` columns to the `storyteller_users` table, and set existing users' tiers from their promo codes.

**Actions:**

- Append these SQL statements to `apps/cogna/supabase_schema.sql` under a new migration section:

```sql
-- ─────────────────────────────────────────────
-- Migration: tier-based routing (2026-05-04)
-- ─────────────────────────────────────────────

-- Add tier and managed flag to storyteller user accounts
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'A';
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS managed BOOLEAN NOT NULL DEFAULT false;

-- Back-fill tier from promo_codes for existing users who have a signup_code
UPDATE storyteller_users su
SET tier = CASE
  WHEN pc.tier = 'E' THEN 'B'   -- E-code invitees record at B level
  WHEN pc.tier IN ('B','C','D') THEN pc.tier
  ELSE 'A'
END,
managed = (pc.tier = 'E')
FROM promo_codes pc
WHERE su.signup_code = pc.code
  AND su.signup_code IS NOT NULL;
```

- Run these SQL statements in the Supabase SQL editor before deploying server changes.

**Files affected:**
- `apps/cogna/supabase_schema.sql`

---

### Step 2: Allow Tier 'E' Promo Codes in the Server

Update the `create_promo_code` endpoint and `_generate_story_promo_code` helper to accept and generate tier 'E' codes.

**Actions:**

In `server.py` at line ~1317, change the tier validation from:
```python
tier = payload.tier.upper() if payload.tier in {"A", "B", "C", "D"} else "A"
```
to:
```python
tier = payload.tier.upper() if payload.tier in {"A", "B", "C", "D", "E"} else "A"
```

In `server.py` at line ~1994, change `_generate_story_promo_code`:
```python
prefix = tier.upper() if tier.upper() in {"A", "B", "C", "D"} else "A"
```
to:
```python
prefix = tier.upper() if tier.upper() in {"A", "B", "C", "D", "E"} else "A"
```

Also remove the diagnostic `print()` statements added during debugging (lines ~1318–1339).

**Files affected:**
- `apps/cogna/server.py`

---

### Step 3: Update Storyteller Signup to Derive and Store Tier + Managed

When a new storyteller user signs up, look up the promo code's tier and set the user's `tier` and `managed` accordingly.

**Actions:**

In `server.py`, in `storyteller_signup` (around line 945), after `pc = _get_promo_code(code)`, add tier resolution logic:

```python
# Derive tier and managed flag from promo code
if code and pc:
    code_tier = pc.get("tier", "A").upper()
    if code_tier == "E":
        user_tier = "B"      # unlimited recording
        user_managed = True
    elif code_tier in {"B", "C", "D"}:
        user_tier = code_tier
        user_managed = False
    else:
        user_tier = "A"
        user_managed = False
else:
    user_tier = "A"
    user_managed = False
```

Then add `tier` and `managed` to the user dict being created:
```python
user = {
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
```

Update the return value to include tier and managed:
```python
return {
    "token": token,
    "user": {
        "email": email,
        "first_name": payload.first_name.strip(),
        "last_name": payload.last_name.strip(),
        "signup_code": code or "",
        "tier": user_tier,
        "managed": user_managed,
        "custom_prompts": [],
    },
    "prompts": [{"id": p["id"], "text": p["text"]} for p in prompts],
}
```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 4: Update Login and /me to Return Tier, Managed, and Monthly Count

**Actions:**

Add a helper function `_this_month_recording_count(user_id: str) -> int` near the other helper functions:

```python
def _this_month_recording_count(user_id: str) -> int:
    from datetime import date
    month_start = date.today().replace(day=1).isoformat()
    if supabase:
        r = (supabase.table("story_recordings")
             .select("id", count="exact")
             .eq("storyteller_user_id", user_id)
             .gte("created_at", month_start)
             .execute())
        return r.count or 0
    db = _load_db()
    return sum(
        1 for rec in db["story_recordings"].values()
        if rec.get("storyteller_user_id") == user_id
        and rec.get("created_at", "") >= month_start
    )
```

Update `storyteller_login` (line ~1003) return value:
```python
return {
    "token": token,
    "user": {
        "email": email,
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "signup_code": user.get("signup_code", ""),
        "tier": user.get("tier", "A"),
        "managed": bool(user.get("managed", False)),
        "this_month_count": _this_month_recording_count(user["id"]),
        "custom_prompts": _user_custom_prompts(user),
    },
    "prompts": [{"id": p["id"], "text": p["text"]} for p in prompts],
}
```

Update `storyteller_me` (line ~923) return value with the same `tier`, `managed`, and `this_month_count` fields.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 5: Update Portal Panel E to Generate Tier 'E' Codes

Change the "Generate Code" button in portal panel E to pass `'E'` as the code tier instead of `'B'`.

**Actions:**

In `portal.html`, in `panelE`, change:
```html
<button class="add-btn" onclick="portal.generatePromoCode('B', 'E')">+ Generate Code</button>
```
to:
```html
<button class="add-btn" onclick="portal.generatePromoCode('E', 'E')">+ Generate Code</button>
```

In `portal.js`, the `generatePromoCode` function sends `{ description: desc, tier: t }`. With `t = 'E'`, the server now accepts it and generates `E-XXXX` codes. No other change needed in portal.js.

**Files affected:**
- `apps/cogna/static/portal.html`
- (no change needed in portal.js)

---

### Step 6: Add Tier, Managed, and Monthly Count to stState + localStorage

**Actions:**

In `storyteller.html`, find `const stState = {` (around line 769) and add three new fields:
```javascript
const stState = {
  userCode: '',
  authToken: '',
  tier: 'A',        // 'A' | 'B' | 'C' | 'D'
  managed: false,   // true = institutional invitee, no AI features, no upgrade prompts
  monthlyCount: 0,  // recordings this calendar month (used for tier A limit)
  prompts: [],
  // ...rest unchanged
};
```

In each place that reads from an API response and sets stState (signup, login, and the `load` handler that calls `/me`), add:
```javascript
stState.tier = result.user.tier || 'A';
stState.managed = !!result.user.managed;
stState.monthlyCount = result.user.this_month_count || 0;
localStorage.setItem('st_tier', stState.tier);
localStorage.setItem('st_managed', stState.managed ? '1' : '0');
```

There are three places: inside `st.signup()`, inside `st.login()`, and inside the `window.addEventListener('load', ...)` callback. Update all three.

In the `load` callback, also read from localStorage as a fast-path before the `/me` call:
```javascript
stState.tier = localStorage.getItem('st_tier') || 'A';
stState.managed = localStorage.getItem('st_managed') === '1';
```
(These get overwritten when `/me` responds, keeping them accurate.)

In the logout handler (inside `load` callback where tokens are cleared), also clear:
```javascript
localStorage.removeItem('st_tier');
localStorage.removeItem('st_managed');
```

Add `'screenChoice'` to the `ALL_SCREENS` array.

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 7: Add the Upgrade Modal HTML and CSS

The upgrade modal is a full-screen dismissible overlay. It shows a message explaining the tier gate and a CTA button. Dismissing it just closes the modal — the user stays where they are and their current features remain fully accessible.

**Actions:**

Add this HTML just before the closing `</body>` tag (before the `<script>` block):

```html
<!-- ── Upgrade Modal ── -->
<div id="upgradeModal" class="upgrade-modal hidden" onclick="if(event.target===this) st.dismissUpgrade()">
  <div class="upgrade-card">
    <button class="upgrade-close" onclick="st.dismissUpgrade()">✕</button>
    <div class="upgrade-icon" id="upgradeIcon">✦</div>
    <h2 class="upgrade-title" id="upgradeTitle">Unlock this feature</h2>
    <p class="upgrade-body" id="upgradeBody">Upgrade your plan to access this.</p>
    <a href="/portal/signup" class="btn-primary upgrade-cta" id="upgradeCta">See plans</a>
    <button class="btn-secondary" style="margin-top:10px" onclick="st.dismissUpgrade()">Maybe later</button>
  </div>
</div>
```

Add these CSS rules in the `<style>` block:

```css
.upgrade-modal {
  position: fixed; inset: 0; background: rgba(28,26,23,0.55);
  z-index: 200; display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.upgrade-modal.hidden { display: none; }
.upgrade-card {
  background: var(--cream); border-radius: 18px; padding: 40px 32px 32px;
  max-width: 380px; width: 100%; text-align: center; position: relative;
  box-shadow: 0 8px 40px rgba(0,0,0,0.18);
}
.upgrade-close {
  position: absolute; top: 14px; right: 16px; background: none; border: none;
  font-size: 18px; color: var(--ink-muted); cursor: pointer; padding: 4px 8px;
}
.upgrade-icon { font-size: 32px; color: var(--gold); margin-bottom: 14px; }
.upgrade-title { font-family: 'Cormorant Garamond', serif; font-size: 26px; font-weight: 400; margin-bottom: 10px; }
.upgrade-body { color: var(--ink-muted); font-size: 15px; line-height: 1.6; margin-bottom: 24px; }
.upgrade-cta { display: block; text-decoration: none; }
```

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 8: Add the Upgrade Modal JS Functions

**Actions:**

Add these functions to the `st` object:

```javascript
showUpgrade(title, body, ctaText, ctaHref) {
  document.getElementById('upgradeTitle').textContent = title;
  document.getElementById('upgradeBody').textContent = body;
  const cta = document.getElementById('upgradeCta');
  cta.textContent = ctaText || 'See plans';
  if (ctaHref) cta.href = ctaHref;
  document.getElementById('upgradeModal').classList.remove('hidden');
},

dismissUpgrade() {
  document.getElementById('upgradeModal').classList.add('hidden');
},
```

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 9: Add the Tier D Choice Screen HTML

**Actions:**

Insert this new screen after `screenOnboarding` (around line 670), before `screenPromptSelect`:

```html
<!-- ── SCREEN: Tier D choice ── -->
<div class="screen hidden" id="screenChoice">
  <div class="inner" style="max-width:480px;text-align:center">
    <div class="eyebrow">MyCogna</div>
    <h2 class="headline" style="font-size:clamp(26px,5vw,38px)">What would you<br><em>like to do?</em></h2>
    <p class="sub" style="margin-top:16px">You have full access. Choose where to begin.</p>

    <button class="btn-primary" style="margin-top:40px" onclick="st._proceedToStories()">
      Tell my stories →
    </button>
    <button class="btn-secondary" style="margin-top:14px" onclick="window.location='/'">
      Talk to a Cogna →
    </button>
  </div>
</div>
```

Add `'screenChoice'` to the `ALL_SCREENS` array (already noted in Step 6).

Add `_proceedToStories()` method to the `st` object:
```javascript
_proceedToStories() {
  if (!localStorage.getItem('st_onboarded')) {
    showScreen('screenOnboarding');
  } else {
    showScreen('screenPromptSelect');
  }
},
```

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 10: Update `_showPromptSelect()` to Route Tier D

**Actions:**

In `_showPromptSelect()` (around line 1268), at the top of the function before the onboarding check, add:

```javascript
// Tier D sees a choice screen first (unless they're already in the "tell stories" flow)
if (stState.tier === 'D' && !stState._choosingStories) {
  showScreen('screenChoice');
  return;
}
stState._choosingStories = false; // reset for next time
```

The `_choosingStories` flag is set to `true` by `_proceedToStories()` before calling `_showPromptSelect()`. Update `_proceedToStories()`:

```javascript
_proceedToStories() {
  stState._choosingStories = true;
  if (!localStorage.getItem('st_onboarded')) {
    showScreen('screenOnboarding');
  } else {
    st._showPromptSelect();
  }
},
```

And update `finishOnboarding()` so it also bypasses the screenChoice check:
```javascript
finishOnboarding() {
  localStorage.setItem('st_onboarded', '1');
  stState._choosingStories = true; // onboarding always leads to stories
  st._showPromptSelect();
},
```

Add `_choosingStories: false` to `stState`.

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 11: Gate "Go Deeper with AI →" on screenDone

The "Go deeper with AI →" button currently always links to `/memoir`. Gate it by tier and managed flag.

**Actions:**

Change the `screenDone` button from a direct `window.location` call to a function call:

Current HTML:
```html
<button class="btn-secondary" onclick="window.location='/memoir'">Go deeper with AI →</button>
```

New HTML:
```html
<button class="btn-secondary" id="goDeeperBtn" onclick="st.goDeeperClick()">Go deeper with AI →</button>
```

Add `goDeeperClick()` to the `st` object:
```javascript
goDeeperClick() {
  if (stState.managed) return; // managed users: button is hidden, shouldn't reach here
  if (stState.tier === 'C' || stState.tier === 'D') {
    window.location = '/memoir';
  } else {
    st.showUpgrade(
      'Unlock AI-assisted memoir',
      'The Storyteller+AI plan lets you go deeper with Claude — follow-up questions, memoir assembly, and chapter editing.',
      'Upgrade to Storyteller+AI',
      '/portal/signup'
    );
  }
},
```

Hide the button for managed users. In `_showPromptSelect()` and anywhere the Done screen is shown, call a helper `st._applyTierUI()`. Alternatively, apply visibility in `showScreen()`:

After the `showScreen` function definition, add a call to `st._applyTierUI()` when showing any screen:

```javascript
function showScreen(id) {
  ALL_SCREENS.forEach(s => document.getElementById(s)?.classList.add('hidden'));
  document.getElementById(id)?.classList.remove('hidden');
  if (typeof st !== 'undefined') st._applyTierUI();
}
```

Add `_applyTierUI()` to the `st` object — this is the single place that reads tier/managed and shows/hides buttons:

```javascript
_applyTierUI() {
  const tier = stState.tier;
  const managed = stState.managed;

  // "Go deeper with AI" — hide for managed, show for all others
  const goDeeperBtn = document.getElementById('goDeeperBtn');
  if (goDeeperBtn) goDeeperBtn.style.display = managed ? 'none' : '';

  // "My Memoir →" — hide for managed, show for all others
  const memoirBtn = document.getElementById('memoirBtn');
  if (memoirBtn) memoirBtn.style.display = managed ? 'none' : '';

  // Update button label to hint at gate for tiers A and B
  if (!managed) {
    if (goDeeperBtn) goDeeperBtn.textContent =
      (tier === 'C' || tier === 'D') ? 'Go deeper with AI →' : 'Go deeper with AI ✦';
    if (memoirBtn) memoirBtn.textContent =
      (tier === 'C' || tier === 'D') ? 'My Memoir →' : 'My Memoir ✦';
  }
},
```

The `✦` symbol is a subtle visual signal that something premium is behind the button, without being alarming.

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 12: Gate "My Memoir →" on screenPromptSelect

**Actions:**

Change the button in `screenPromptSelect`:

Current:
```html
<button class="btn-secondary" style="margin-top:10px" onclick="window.location='/memoir'">My Memoir →</button>
```

New:
```html
<button class="btn-secondary" id="memoirBtn" style="margin-top:10px" onclick="st.memoirClick()">My Memoir →</button>
```

Add `memoirClick()` to the `st` object:
```javascript
memoirClick() {
  if (stState.managed) return;
  if (stState.tier === 'C' || stState.tier === 'D') {
    window.location = '/memoir';
  } else {
    st.showUpgrade(
      'Unlock AI memoir writing',
      'The Storyteller+AI plan lets you build a memoir from your recordings — with Claude helping you deepen, assemble, and edit your chapters.',
      'Upgrade to Storyteller+AI',
      '/portal/signup'
    );
  }
},
```

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 13: Gate "Record Another" for Tier A (Monthly Limit)

Tier A users get 1 recording per calendar month. When they try to record again after using their monthly slot, show a dismissible upgrade prompt. They can dismiss it and stay on the Done screen.

**Actions:**

Update `stState` to also track `monthlyCount` (already added in Step 6). After each successful recording submission in `_submitRecording()`, increment `stState.monthlyCount`.

In `_submitRecording()`, after `stState.transcripts.push(...)`, add:
```javascript
stState.monthlyCount++;
```

Update `recordAnother()` (around line 1166):

```javascript
async recordAnother() {
  // Tier A: only 1 recording per month
  if (stState.tier === 'A' && !stState.managed && stState.monthlyCount >= 1) {
    st.showUpgrade(
      'You\'ve shared your story for this month',
      'The Storyteller plan gives you unlimited recordings. Upgrade to keep sharing whenever inspiration strikes.',
      'Upgrade to Storyteller',
      '/portal/signup'
    );
    return;
  }
  stState.prompts = [...stState.allPrompts];
  stState.currentPromptIndex = 0;
  stState.transcripts = [];
  // ...rest of existing recordAnother() code
},
```

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 14: Remove Diagnostic Print Statements from Server

Clean up the `[promo]` print statements added during debugging in Step 2.

**Actions:**

In `create_promo_code` (server.py), remove:
```python
print(f"[promo] user={user.get('email')} tier={tier} desc={payload.description!r}")
```
and:
```python
print(f"[promo] generated code={code}")
```
and:
```python
print(f"[promo] inserted ok")
```
and the try/except wrappers around the generate and insert calls (revert to simpler form), keeping only the HTTPException raises if needed. The diagnostic wrappers are no longer needed once tier E is validated.

Actually — keep the try/except wrappers but remove the print statements. The error wrapping is useful in production.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 15: Validation and Smoke Test

**Actions:**

1. Run the Supabase migration SQL from Step 1 in the SQL editor
2. Push all code changes; wait for Railway + Vercel to deploy (~2–3 min each)
3. Test as a fresh tier A user (no code): go to `/storyteller`, sign up, record one story, verify "Go deeper" shows the upgrade modal, try "Record Another" and verify the monthly limit modal
4. Test as a tier B user: sign in, verify unlimited recording, verify "Go deeper" shows upgrade modal, verify "My Memoir →" shows upgrade modal
5. Test as a tier C user: verify Go Deeper and My Memoir both work directly
6. Test as a tier D user: verify choice screen appears, "Tell my stories" leads to prompt select, "Talk to a Cogna" goes to `/`
7. Test as a managed (tier E invitee): sign up with an E-code, verify "Go deeper" and "My Memoir" are hidden entirely, verify no upgrade prompts appear, verify unlimited recording works
8. In portal: log in as tier E admin, go to Legacy Collection tab, generate a code, verify the code starts with `E-`

---

## Connections & Dependencies

### Files That Reference This Area

- `apps/cogna/static/memoir.html` — linked from storyteller; does not need changes (the gate is before navigation)
- `apps/cogna/static/portal-signup.html` — the upgrade CTA links here; no changes needed
- `apps/cogna/supabase_schema.sql` — source of truth for DB schema

### Updates Needed for Consistency

- `CLAUDE.md` — update the MyCogna app section to document the `managed` flag and the tier routing rules, since this is a new architectural concept

### Impact on Existing Workflows

- Existing users: the migration backfill in Step 1 sets their tier from their existing promo codes. Users with no promo code default to tier A — they'll see the monthly limit and upgrade prompts.
- Portal admins: tier E admin accounts are unaffected. Their panel E now generates `E-XXXX` codes instead of `B-XXXX`.
- Storyteller users who already have accounts: will get their tier set in the migration. No re-login required — their `st_tier` will be populated from localStorage next time `/me` is called (on next page load).

---

## Validation Checklist

- [ ] Supabase `storyteller_users` table has `tier` and `managed` columns
- [ ] SQL backfill ran without errors; existing users have correct tiers
- [ ] Portal panel E generates codes starting with `E-` (not `B-`)
- [ ] New tier E invitee account has `managed = true` and `tier = 'B'` in Supabase
- [ ] `/api/storyteller/login` response includes `tier`, `managed`, `this_month_count`
- [ ] Tier D user sees `screenChoice` on login; can navigate to both paths
- [ ] Tier A user sees upgrade modal on second recording attempt in same month
- [ ] Tier A, B user sees upgrade modal when clicking "Go deeper" or "My Memoir"
- [ ] Managed user never sees upgrade modal; "Go deeper" and "My Memoir" buttons are hidden
- [ ] Tier C and D users navigate directly to memoir without modal
- [ ] Dismissing any upgrade modal leaves the user on their current screen with no disruption
- [ ] `CLAUDE.md` updated with managed flag and tier routing documentation

---

## Success Criteria

The implementation is complete when:

1. Every tier gate matches the product spec exactly: A gets 1/month + upgrade prompts on AI features; B gets unlimited recording + upgrade prompts on AI; C gets full memoir access; D sees choice screen + full access; managed accounts see no AI buttons and no upgrade prompts.
2. No upgrade prompt ever blocks a user from a feature they're entitled to — every modal has a working dismiss path.
3. Tier E admin generates `E-XXXX` codes, and users who sign up with those codes become managed tier-B storytellers in Supabase.

---

## Notes

- **Stripe integration is out of scope here.** The upgrade CTA links to `/portal/signup` (existing self-serve signup). Payment processing is a separate phase.
- **`this_month_count` in the `/me` response only matters for tier A.** For higher tiers, the frontend ignores it. It's cheap to compute and keeps the API consistent across tiers.
- **Future: email sending for generated codes.** The portal panel E generates codes but no automated email. A future phase can add a "Send code via email" flow using SendGrid or Resend — the code is already in the DB, just needs a mailer wired up.
- **Future: tier upgrade within the app.** When Stripe is integrated, the upgrade CTA can go to a Stripe Checkout session instead of `/portal/signup`.
- **Companion gating for tiers A/B/C**: The companion app (`/`) already requires a child access code (`COGNA-XXXX`). Individual storyteller users (tiers A–C) don't have that code — they simply can't access it. This plan doesn't need to add an explicit gate there; the existing access code requirement is the gate.

---

## Implementation Notes

**Implemented:** 2026-05-04

### Summary

All 14 code steps executed in full. Changes deployed to Railway (backend) and Vercel (frontend) via git push.

### Deviations from Plan

- **Step 1 backfill SQL omitted** per user instruction — existing test accounts don't need migration. The ALTER TABLE statements for `tier` and `managed` columns were kept (required for new signups to work).
- `_applyTierUI()` is called from inside `showScreen()` using a `typeof st !== 'undefined'` guard to avoid errors before the `st` object is defined.

### Issues Encountered

None — all edits applied cleanly.
