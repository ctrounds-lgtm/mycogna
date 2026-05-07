# Plan: Legacy Collection + Book Builder (F-Tier)

**Created:** 2026-05-07
**Status:** Implemented
**Request:** Add tier F (Legacy Collection + Book Builder) — same as E but with AI deepening for invitees and portal admin book assembly — displayed as an upgrade within the Legacy Collection tab and pricing card.

---

## Overview

### What This Plan Accomplishes

A new tier F gives institutional portal admins (historical societies, community organizations, Duluth Sister Cities) everything in Legacy Collection (E) plus AI-assisted deepening for invitees and a portal-admin-controlled book assembly workflow. F-tier invitees can record and go deeper with AI; the portal admin assembles a "Book" (Collection of Explicit Knowledge) using the same backend infrastructure already built for C-tier memoir. Both E and F invitees appear in the same Legacy Collection portal tab; F appears as an upgrade option on the Legacy Collection pricing card rather than a standalone card.

### Why This Matters

The C-tier memoir workflow was built for individual storytellers whose portal admin curates their memoir. F-tier applies the exact same logic to institutional knowledge capture: a historical society or civic organization collects oral history from members, uses AI to deepen the conversations, then compiles the result into a publishable book. Duluth Sister Cities is the first intended use case.

---

## Current State

### Relevant Existing Structure

- `apps/cogna/server.py` — tier validation in three places (lines 343, 1466, 2431) hard-codes `{"A","B","C","D","E"}`. E-code invitees receive `user_tier="B"`, `user_managed=True`. Six portal-invitee memoir endpoints already exist (built for C-tier) and are tier-agnostic — they work for any `storyteller_user_id`.
- `apps/cogna/static/portal.js` — `tierOrder` in two places (lines 104 and 513) lists `['B','C','D','E']` and `['A','B','C','D','E']`. `switchDashTab` iterates `['B','C','D','E']`. E-tab calls `loadStoryPanel('E','B')`.
- `apps/cogna/static/portal.html` — `panelE` has E-code generation, a prompts note, and a Recordings section. No invitee list.
- `apps/cogna/static/portal-signup.html` — `planE` card exists. `PLAN_LABELS` has `E: 'Legacy Collection ($25/mo)'`. No F card or label.
- `apps/cogna/static/index.html` — Public pricing section shows B/C/D cards. E is represented in a separate "Institutional Legacy" features section (line 934) but has no pricing card. Plan: add F as an upgrade row inside that section.
- `apps/cogna/static/storyteller.html` — `hideUpgrade = managed || (signupCode && (tier === 'A' || tier === 'B'))`. F-invitees will have `tier='C'` and `signupCode` set — this currently does NOT hide the upgrade button for C-tier signupCode users. Needs fix.
- `apps/cogna/static/portal-memoir.html` — Labels "Memoir" throughout. Reads `portal_token` + `?id=` param. No `?type=` param yet.

### Gaps or Problems Being Addressed

- No tier F exists anywhere in the codebase.
- E-tab has no invitee list or book workspace path for F invitees.
- `GET /api/portal/invitees` is hard-coded to `tier="C"` — not reusable for F.
- `GET /api/portal/invitee/{id}/data` does not return the invitee's code tier — portal-memoir.html has no way to know whether to say "Memoir" or "Book".
- `hideUpgrade` logic in storyteller.html doesn't suppress the upgrade button for C-tier invitees who arrived via a portal code (F-tier storytellers will land here as tier C with a signupCode).
- F has no signup card on portal-signup.html.
- F has no upgrade representation on index.html pricing section.

---

## Proposed Changes

### Summary of Changes

- `server.py`: Add `"F"` to all three tier validation sets; add F-code logic in `storyteller_signup` (F-code → `user_tier="C"`, `user_managed=False`); add `tier` query param to `GET /api/portal/invitees`; include signup_code tier in `portal_invitee_data` response
- `storyteller.html`: Fix `hideUpgrade` to suppress upgrade button for any invitee who arrived via a portal code regardless of tier
- `portal.html`: Add F-code generate button and F invitee list (`id="inviteeListF"`) to `panelE`; add `F` to tab iteration lists and `labels` map
- `portal.js`: Add `F` to both `tierOrder` arrays; add `F` to `switchDashTab` labels and iteration; update E-tab activation to call `portal.loadLegacyPanel()`; add `loadLegacyPanel()` that loads E codes, F codes, combined recordings, and F invitees; add `loadLegacyInvitees()`; update `openMemoirWorkspace` to accept a `type` param
- `portal-signup.html`: Add `planF` card; add `F` to `PLAN_LABELS`
- `index.html`: Add "Legacy Collection + Book Builder" upgrade row inside the Institutional Legacy section
- `portal-memoir.html`: Read `?type=` URL param; swap "Memoir"/"Memoir Workspace"/"Assemble Memoir"/"Book Bible" labels to "Book"/"Book Workspace"/"Assemble Book"/"Book Outline" when `type=book`

### New Files to Create

None — all changes are to existing files.

### Files to Modify

| File Path | Changes |
|-----------|---------|
| `apps/cogna/server.py` | Add F to tier sets (3 places); F-code signup logic; tier param on invitees endpoint; code tier in invitee data response |
| `apps/cogna/static/storyteller.html` | Fix hideUpgrade to cover all signupCode users regardless of tier |
| `apps/cogna/static/portal.html` | Add F-code generate button + F invitee list to panelE; add F to tab lists |
| `apps/cogna/static/portal.js` | Add F to tierOrder; loadLegacyPanel; loadLegacyInvitees; openMemoirWorkspace type param |
| `apps/cogna/static/portal-signup.html` | Add planF card and PLAN_LABELS entry |
| `apps/cogna/static/index.html` | Add F upgrade row in Institutional Legacy section |
| `apps/cogna/static/portal-memoir.html` | Read ?type= param; swap Memoir→Book labels when type=book |

---

## Design Decisions

### Key Decisions Made

1. **F-code invitees get `user_tier="C"`, `user_managed=False`**: C is the deepening-capable tier. `managed=False` is correct because F invitees are not institutionally managed in the same way as E (they actively participate with AI). The `signupCode` field (set to the F-code) is what restricts upgrade prompts and My Memoir access.

2. **Fix hideUpgrade to `managed || !!signupCode`**: The current guard `(signupCode && (tier === 'A' || tier === 'B'))` was designed when C was the only portal-code tier with deepening. F invitees arrive as tier C with a signupCode — they should not see an upgrade button. The simplest correct rule: any portal-invited user (signupCode set) cannot self-upgrade.

3. **`GET /api/portal/invitees` gets a `tier` query param**: The existing endpoint already works for C; adding `?tier=C` as default and `?tier=F` for Legacy panel reuses the same logic without a new endpoint. The C-tab call (`loadInvitees`) passes `?tier=C`; the new `loadLegacyInvitees` passes `?tier=F`.

4. **`portal_invitee_data` returns `code_tier` in the invitee object**: The endpoint already fetches the storyteller's `signup_code`. A single additional lookup against `promo_codes` gives us the tier letter. Frontend then passes `type=book` (for F) or `type=memoir` (for C) in the workspace URL.

5. **Combined E/F panel — no new tab**: Adding a 6th tab button would crowd the tab bar and confuse users. E and F represent the same product category; the Legacy Collection tab shows both. E rows have no workspace button (recording-only); F rows have "Open Book Workspace →".

6. **`portal-memoir.html` driven by `?type=` URL param**: Avoids a separate `portal-book.html` file and keeps a single workspace page. The type is passed from the portal when opening the workspace — no server round-trip needed for the label swap.

7. **`loadLegacyPanel()` replaces direct `loadStoryPanel('E','B')` call**: The E-tab needs to do more work now (load F codes AND F invitees). A dedicated `loadLegacyPanel()` keeps the logic clean without bloating `switchDashTab`.

### Alternatives Considered

- **Separate panelF tab**: Rejected — crowds tab bar, splits related content, requires more HTML.
- **Feature flag on E tier (`ai_enabled` boolean on promo_code)**: Rejected — adds schema complexity and makes tier logic conditional rather than declarative. A distinct code letter is simpler and consistent with existing patterns.
- **Separate `portal-book.html`**: Rejected — duplicates 350+ lines of portal-memoir.html. A `?type=` param with label swaps is far leaner.

### Open Questions

None — all decisions resolved before plan creation.

---

## Step-by-Step Tasks

### Step 1: Add F to server.py tier validation and signup logic

Three validation sets need `"F"` added. The signup logic needs a new branch for F-codes.

**Actions:**

1. Line 343 — `create_promo_code` tier validation:
   - Change: `tier = payload.tier if payload.tier in {"A", "B", "C", "D", "E"} else "A"`
   - To: `tier = payload.tier if payload.tier in {"A", "B", "C", "D", "E", "F"} else "A"`

2. Line 1466 — `create_promo_code` API tier validation:
   - Change: `tier = payload.tier.upper() if payload.tier in {"A", "B", "C", "D", "E"} else "A"`
   - To: `tier = payload.tier.upper() if payload.tier in {"A", "B", "C", "D", "E", "F"} else "A"`

3. Line 2431 — `_generate_story_promo_code` prefix validation:
   - Change: `prefix = tier.upper() if tier.upper() in {"A", "B", "C", "D", "E"} else "A"`
   - To: `prefix = tier.upper() if tier.upper() in {"A", "B", "C", "D", "E", "F"} else "A"`

4. In `storyteller_signup` (~line 1001), add F branch to the `if code_tier == "E":` block:
   - Change:
     ```python
     if code_tier == "E":
         user_tier = "B"      # E-code invitees get unlimited recording
         user_managed = True
     elif code_tier in {"B", "C", "D"}:
         user_tier = code_tier
         user_managed = False
     else:
         user_tier = "A"
         user_managed = False
     ```
   - To:
     ```python
     if code_tier == "E":
         user_tier = "B"      # E-code invitees get unlimited recording
         user_managed = True
     elif code_tier == "F":
         user_tier = "C"      # F-code invitees get deepening capability
         user_managed = False
     elif code_tier in {"B", "C", "D"}:
         user_tier = code_tier
         user_managed = False
     else:
         user_tier = "A"
         user_managed = False
     ```

5. Update `GET /api/portal/invitees` to accept a `tier` query param (default `"C"`):
   - Change the function signature from:
     ```python
     def list_portal_invitees(authorization: Optional[str] = Header(default=None)):
     ```
   - To:
     ```python
     def list_portal_invitees(tier: str = Query(default="C"), authorization: Optional[str] = Header(default=None)):
     ```
   - Change both `.eq("tier", "C")` occurrences in the function body to `.eq("tier", tier.upper())`
   - Also fix the local fallback: change `c.get("tier") == "C"` to `c.get("tier") == tier.upper()`
   - Add `Query` to FastAPI imports if not already present (check: `from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Form, Query`)

6. Update `GET /api/portal/invitee/{storyteller_id}/data` to include code tier in the invitee object:
   - After `_verify_portal_owns_storyteller` returns `st_user`, look up the tier of their signup_code:
     ```python
     signup_code = st_user.get("signup_code", "")
     code_tier = "C"  # default
     if signup_code:
         if supabase:
             ct = supabase.table("promo_codes").select("tier").eq("code", signup_code).limit(1).execute()
             code_tier = ct.data[0].get("tier", "C") if ct.data else "C"
         else:
             db_lookup = _load_db()
             pc = next((v for v in db_lookup.get("promo_codes", {}).values() if v.get("code") == signup_code), None)
             code_tier = pc.get("tier", "C") if pc else "C"
     ```
   - In the return dict, update the `invitee` key to include `code_tier`:
     ```python
     "invitee": {
         "id": st_user["id"],
         "first_name": st_user.get("first_name", ""),
         "last_name": st_user.get("last_name", ""),
         "email": st_user["email"],
         "code_tier": code_tier,
     },
     ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 2: Fix hideUpgrade in storyteller.html

F-tier invitees arrive as `tier='C'` with `signupCode` set. The current guard only hides the upgrade button if `signupCode && (tier === 'A' || tier === 'B')` — this misses tier C. The fix: hide upgrade for any portal-code user.

**Actions:**

Find this block (around line 1530):
```javascript
const hideUpgrade = stState.managed || (stState.signupCode && (stState.tier === 'A' || stState.tier === 'B'));
if (hideUpgrade) return;
```
Change to:
```javascript
const hideUpgrade = stState.managed || !!stState.signupCode;
if (hideUpgrade) return;
```

Find this block in `_applyTierUI` (around line 1532):
```javascript
const hideUpgrade = stState.managed || (stState.signupCode && (tier === 'A' || tier === 'B'));
```
Change to:
```javascript
const hideUpgrade = stState.managed || !!stState.signupCode;
```

**Files affected:**
- `apps/cogna/static/storyteller.html`

---

### Step 3: Update portal.html panelE for F-codes and F invitees

Add an F-code generate button and an F invitee list section to `panelE`. Keep the existing E-code section, prompts note, and recordings list intact.

**Actions:**

Replace the `panelE` `section-header-row` and paragraph that currently reads:
```html
<div class="section-header-row" style="margin-top:8px">
  <h2 class="section-title">User Codes <span style="font-size:12px;font-weight:400;color:var(--ink-muted)">(Legacy Collection — 5 new per month)</span></h2>
  <button class="add-btn" onclick="portal.generatePromoCode('E', 'E')">+ Generate Code</button>
</div>
<p style="font-size:13px;color:var(--ink-muted);margin-bottom:16px">Generate codes to give storytellers unlimited access. Each code remains active permanently — generate up to 5 new ones per month to grow your collection.</p>
```

With:
```html
<div class="section-header-row" style="margin-top:8px">
  <h2 class="section-title">User Codes <span style="font-size:12px;font-weight:400;color:var(--ink-muted)">(Legacy Collection)</span></h2>
  <div style="display:flex;gap:8px;">
    <button class="add-btn" onclick="portal.generatePromoCode('E', 'E')">+ E-Code (Recording)</button>
    <button class="add-btn" onclick="portal.generatePromoCode('F')">+ F-Code (Book Builder)</button>
  </div>
</div>
<p style="font-size:13px;color:var(--ink-muted);margin-bottom:16px">E-codes: recording only. F-codes: recording + AI deepening + book assembly. Both accumulate permanently.</p>
```

Then, after the `promoCodesListE` div and the prompts note, and BEFORE the existing Recordings section, add the F invitee list section:

```html
<div class="section-header-row" style="margin-top:32px">
  <h2 class="section-title">Book Workspaces</h2>
  <button class="add-btn" onclick="portal.loadLegacyInvitees()">Refresh</button>
</div>
<p style="font-size:13px;color:var(--ink-muted);margin-bottom:16px">F-code invitees can record, go deeper with AI, and have their stories compiled into a book. Click to open their workspace.</p>
<div id="inviteeListF" class="stories-list" style="margin-bottom:40px">
  <div class="empty-state"><p>No F-code invitees yet. Generate an F-code and share it to get started.</p></div>
</div>
```

**Files affected:**
- `apps/cogna/static/portal.html`

---

### Step 4: Update portal.js for F-tier

Four changes: tierOrder arrays, switchDashTab, loadLegacyPanel, loadLegacyInvitees, openMemoirWorkspace.

**Actions:**

1. Line 104 — tab locking `tierOrder`:
   - Change: `const tierOrder = ['B', 'C', 'D', 'E'];`
   - To: `const tierOrder = ['B', 'C', 'D', 'E', 'F'];`

2. Line 513 — `switchDashTab` `tierOrder`:
   - Change: `const tierOrder = ['A', 'B', 'C', 'D', 'E'];`
   - To: `const tierOrder = ['A', 'B', 'C', 'D', 'E', 'F'];`

3. In `switchDashTab`, the `forEach` that hides/shows panels:
   - Change: `['B', 'C', 'D', 'E'].forEach(t => {`
   - To: `['B', 'C', 'D', 'E', 'F'].forEach(t => {`
   
   Note: F shares `panelE` with E — there is no `panelF` in the HTML. The forEach that toggles panel visibility by ID (`document.getElementById('panel' + t)`) will simply find nothing for `panelF` and skip it harmlessly. BUT we need to make sure F users don't see a locked state. The `tabIdx > userTierIdx` check handles this — if the user has tier F, F is the last index, so all tabs are unlocked.
   
   Actually, there IS a problem: `document.getElementById('panelF')` returns null, and `panel.classList.add('hidden')` will throw. Fix: guard that line:
   
   Change the panel hide/show block from:
   ```javascript
   ['B', 'C', 'D', 'E'].forEach(t => {
     const btn = document.getElementById('dashTab' + t);
     if (btn) btn.classList.toggle('active', t === tab);
     const panel = document.getElementById('panel' + t);
     if (panel) panel.classList.add('hidden');
   });
   ```
   To:
   ```javascript
   ['B', 'C', 'D', 'E', 'F'].forEach(t => {
     const btn = document.getElementById('dashTab' + t);
     if (btn) btn.classList.toggle('active', t === tab);
     const panel = document.getElementById('panel' + t);
     if (panel) panel.classList.add('hidden');
   });
   ```
   (The `if (panel)` guard already exists, so null for panelF is safe.)

4. Add `F` to the `labels` map in `switchDashTab`:
   - Change: `const labels = { B: 'Unlimited Storyteller', C: 'AI Assisted', D: 'AI Companion', E: 'Legacy Collection' };`
   - To: `const labels = { B: 'Unlimited Storyteller', C: 'AI Assisted', D: 'AI Companion', E: 'Legacy Collection', F: 'Legacy Collection + Book Builder' };`

5. Add `dashTabF` button handling — add after the E-tab line in the tab button HTML (portal.html, not portal.js):
   - Actually F shares the E tab, so no new tab button is needed. Users with tier F land on the E tab (which shows both E and F content). The `startTab` logic in the boot sequence sends tier-F users to their highest tab which is 'F' — but 'F' has no tab button. Fix: in the boot sequence (line ~118):
   ```javascript
   const startTab = tier === 'A' ? 'B' : tier;
   ```
   Change to:
   ```javascript
   const startTab = tier === 'A' ? 'B' : (tier === 'F' ? 'E' : tier);
   ```
   This sends F-tier portal admins to the E tab (which contains all Legacy Collection content including F invitees).

6. In `switchDashTab`, update the E-tab activation line:
   - Change: `else if (tab === 'E') portal.loadStoryPanel('E', 'B');`
   - To: `else if (tab === 'E') portal.loadLegacyPanel();`

7. Add `loadLegacyPanel()` method (after `loadInvitees`):
```javascript
async loadLegacyPanel() {
  try {
    const [codesEData, codesFData, recsData] = await Promise.all([
      req(`${api}/storyteller/user-codes?tier=E`, { headers: authHeaders() }),
      req(`${api}/storyteller/user-codes?tier=F`, { headers: authHeaders() }),
      req(`${api}/storyteller/recordings?tier=E`, { headers: authHeaders() }),
    ]);
    // Render E and F promo codes together in promoCodesListE
    const allCodes = [...(codesEData.codes || []), ...(codesFData.codes || [])];
    portal._renderPromoCodes(allCodes, 'E');
    portal._renderRecordings(recsData.recordings || [], 'E');
  } catch (err) {
    console.error('loadLegacyPanel error:', err.message);
  }
  portal.loadLegacyInvitees();
},
```

8. Add `loadLegacyInvitees()` method (after `loadLegacyPanel`):
```javascript
async loadLegacyInvitees() {
  const el = document.getElementById('inviteeListF');
  if (!el) return;
  el.innerHTML = '<div class="empty-state"><p>Loading…</p></div>';
  try {
    const data = await req(`${api}/portal/invitees?tier=F`, { headers: authHeaders() });
    const invitees = data.invitees || [];
    if (!invitees.length) {
      el.innerHTML = '<div class="empty-state"><p>No F-code invitees yet. Generate an F-code and share it to get started.</p></div>';
      return;
    }
    el.innerHTML = invitees.map(inv => {
      const name = [inv.first_name, inv.last_name].filter(Boolean).join(' ') || inv.email;
      return `
        <div class="story-item">
          <div class="story-item-main">
            <div class="story-item-text">${name}</div>
            <div class="story-item-meta">${inv.email}</div>
          </div>
          <div class="story-item-actions">
            <button class="story-action-btn" onclick="portal.openMemoirWorkspace('${inv.id}', 'book')">Open Book Workspace →</button>
          </div>
        </div>`;
    }).join('');
  } catch (err) {
    el.innerHTML = `<div class="empty-state"><p>Error loading invitees: ${err.message}</p></div>`;
  }
},
```

9. Update `openMemoirWorkspace` to accept and forward a `type` param:
   - Change:
     ```javascript
     openMemoirWorkspace(storytellerId) {
       window.location = `/portal/memoir?id=${storytellerId}`;
     },
     ```
   - To:
     ```javascript
     openMemoirWorkspace(storytellerId, type) {
       const t = type || 'memoir';
       window.location = `/portal/memoir?id=${storytellerId}&type=${t}`;
     },
     ```

10. Update existing `loadInvitees()` (C-tab) to pass `?tier=C` explicitly, since the endpoint now defaults to `C` but making it explicit is clearer:
    - Change: `const data = await req(`${api}/portal/invitees`, { headers: authHeaders() });`
    - To: `const data = await req(`${api}/portal/invitees?tier=C`, { headers: authHeaders() });`

**Files affected:**
- `apps/cogna/static/portal.js`
- `apps/cogna/static/portal.html` (step 5 boot sequence fix)

---

### Step 5: Update portal-signup.html to add F plan card

Add a `planF` card after `planE`, and add `F` to `PLAN_LABELS`.

**Actions:**

After the closing `</div>` of `planE`, add:
```html
<div class="plan-card" id="planF" onclick="selectPlan('F')">
  <div class="plan-selector"></div>
  <div class="plan-badge">Institutional</div>
  <div class="plan-name">Legacy Collection +<br>Book Builder</div>
  <div class="plan-price"><sup>$</sup>35</div>
  <div class="plan-period">per month</div>
  <div class="plan-divider"></div>
  <ul class="plan-features">
    <li>Everything in Legacy Collection</li>
    <li>AI deepening sessions for invitees</li>
    <li>Portal book assembly &amp; editing</li>
    <li>Ideal for oral history projects</li>
  </ul>
</div>
```

Note: Price ($35) is a placeholder — update before going live if needed.

In the `PLAN_LABELS` JS object, add:
```javascript
F: 'Legacy Collection + Book Builder ($35/mo)',
```

**Files affected:**
- `apps/cogna/static/portal-signup.html`

---

### Step 6: Update index.html Institutional Legacy section

Add a "Legacy Collection + Book Builder" upgrade line to the Institutional Legacy section on the public homepage. This is not a new pricing card — it's an upgrade line inside the existing institutional section.

**Actions:**

Find the `<h3>Institutional Legacy</h3>` section (around line 934). Read the surrounding HTML to identify where to add the upgrade line. The pattern should show E as the base tier and F as an "Add Book Builder →" upgrade link below it.

Specifically, find the paragraph or feature list inside that section and add after the existing content:
```html
<p style="margin-top:16px;font-size:14px;">
  <strong>Add Book Builder</strong> — AI deepening + portal book assembly.
  <a href="/portal/signup" style="color:var(--gold);text-decoration:none;border-bottom:1px solid var(--gold-light);">Upgrade to Legacy + Book Builder →</a>
</p>
```

The exact placement depends on the surrounding HTML structure — read the full section before editing.

**Files affected:**
- `apps/cogna/static/index.html`

---

### Step 7: Update portal-memoir.html for ?type=book label swapping

Read `?type=` from URL params (defaulting to `memoir`). When `type === 'book'`, swap all user-facing label strings from memoir terminology to book terminology.

**Actions:**

In the JS boot section of `portal-memoir.html`, after the `STORYTELLER_ID` line, add:
```javascript
const WORKSPACE_TYPE = params.get('type') || 'memoir';
const IS_BOOK = WORKSPACE_TYPE === 'book';
```

Add a `labels` object for all swappable strings:
```javascript
const L = {
  workspaceTitle: IS_BOOK ? 'Book Workspace' : 'Memoir Workspace',
  assembleTitle: IS_BOOK ? 'Assemble Book' : 'Assemble Memoir',
  assembleSub: IS_BOOK ? 'Claude will read all recordings and generate a Book Outline and chapter structure.' : 'Claude will read all recordings and generate a Book Bible and chapter outline.',
  assembleBtn: IS_BOOK ? 'Assemble book →' : 'Assemble memoir →',
  downloadBible: IS_BOOK ? 'Download Book Outline' : 'Download Book Bible',
  downloadFile: IS_BOOK ? 'book-outline' : 'book-bible',
  manuscriptFile: IS_BOOK ? 'book' : 'manuscript',
  pageTitle: IS_BOOK ? 'MyCogna · Book Workspace' : 'MyCogna · Memoir Workspace',
  wordmark: IS_BOOK ? 'MyCogna · Book Workspace' : 'MyCogna · Memoir Workspace',
  navTitle: IS_BOOK ? 'Book Workspace' : 'Memoir Workspace',
};
```

Apply labels in the `load` event handler after data is fetched:
```javascript
document.title = L.pageTitle;
document.querySelectorAll('.wordmark').forEach(el => el.textContent = L.wordmark);
document.getElementById('assembleBtn') && (document.getElementById('assembleBtn').textContent = L.assembleBtn);
```

Update `showAssemble()`:
```javascript
document.getElementById('assembleSub').textContent =
  `${pmState.recordings.length} recording${pmState.recordings.length !== 1 ? 's' : ''} will be included. ${IS_BOOK ? 'Claude will generate a Book Outline.' : 'Claude will generate a Book Bible.'}`;
```

Update `downloadBible()`:
```javascript
const blob = new Blob([`${name}'s ${IS_BOOK ? 'Book Outline' : 'Book Bible'}\n${'='.repeat(50)}\n\n${content}`], {type:'text/plain'});
a.download = `${name.toLowerCase().replace(/\s+/g, '-')}-${L.downloadFile}.txt`;
```

Update `downloadManuscript()`:
```javascript
a.download = `${name.toLowerCase().replace(/\s+/g, '-')}-${L.manuscriptFile}.txt`;
```

Also update the static HTML in the page:
- `<title>` → use JS to set from `L.pageTitle` on load (already covered above)
- All `.wordmark` spans that say "MyCogna · Memoir Workspace" → JS sets on load (already covered)
- `<h1 id="recPageTitle">` → already set dynamically in `showRecordings()`, no change needed
- `<h2>Assemble Memoir</h2>` (screenAssemble) → change to `<h2 id="assembleHeading">Assemble</h2>` and set in load: `document.getElementById('assembleHeading').textContent = L.assembleTitle`
- `<p class="sub" id="assembleSub">` → already set dynamically in `showAssemble()`, updated above
- `<button id="assembleBtn">Assemble memoir →</button>` → set from L in load (already covered)
- `<button class="btn-primary" onclick="pm.downloadBible()">Download Book Bible</button>` → change button text dynamically: add `id="downloadBibleBtn"` and set `document.getElementById('downloadBibleBtn').textContent = L.downloadBible` in load

**Files affected:**
- `apps/cogna/static/portal-memoir.html`

---

### Step 8: Update CLAUDE.md

Add F-tier to the MyCogna portal features list.

**Actions:**

In the Guardian portal features bullet list, update the tier descriptions to mention F:
- Add: "Legacy Collection + Book Builder (F-tier): like E plus AI deepening for invitees and portal book assembly"

**Files affected:**
- `CLAUDE.md`

---

## Connections & Dependencies

### Files That Reference This Area

- `apps/cogna/supabase_schema.sql` — no schema changes needed; `promo_codes.tier` is TEXT, so `"F"` works without migration
- `apps/cogna/static/portal.html` — tab buttons (no new `dashTabF` needed since F shares E tab)
- `apps/cogna/static/portal-memoir.html` — existing C-tier memoir workspace; no changes needed for C usage since `?type=memoir` remains default

### Updates Needed for Consistency

- `CLAUDE.md` — mention F-tier in portal features
- `apps/cogna/supabase_schema.sql` — add a comment noting F is a valid tier value (documentation only, no ALTER TABLE)

### Impact on Existing Workflows

- **Independent storytellers (no signupCode)**: Zero impact — `hideUpgrade = managed || !!signupCode` evaluates to `false || false = false`, same as before for self-signup users.
- **E-code invitees**: `managed=True` still set, behavior unchanged.
- **C-code invitees**: `signupCode` set, `managed=False`, tier C. Now `hideUpgrade = false || true = true`. Previously: `hideUpgrade = false || (true && (false)) = false`. **This is a behavior change**: C-code invitees will now have the upgrade button hidden. This is the correct behavior — a portal-invited storyteller should not self-upgrade. This was a bug.
- **Portal admins with tier E**: `startTab` now maps E→E (no change). `loadLegacyPanel()` replaces `loadStoryPanel('E','B')` — same recordings load, plus F invitee list appears (empty initially).
- **Portal admins with tier F**: `startTab` maps F→E, so they land on the E/Legacy Collection tab. Tier ordering means they have access to all tabs up to E.
- **Existing C-tier memoir workspaces**: `portal.openMemoirWorkspace(id)` (no type arg) uses default `memoir` — `type` param is optional, behavior unchanged.

---

## Validation Checklist

- [ ] F-code can be generated from portal Legacy Collection tab
- [ ] F-code generates a code with `F-XXXX` format
- [ ] Storyteller can sign up with an F-code successfully
- [ ] F-invitee sees Go Deeper button after recording
- [ ] F-invitee does NOT see My Memoir button
- [ ] F-invitee does NOT see upgrade prompts
- [ ] Portal Legacy Collection tab shows both E-code and F-code lists
- [ ] F-invitees appear in Book Workspaces list after signing up
- [ ] "Open Book Workspace →" button navigates to `/portal/memoir?id=...&type=book`
- [ ] Book workspace shows "Book Workspace" in nav and title (not "Memoir Workspace")
- [ ] "Assemble Book" button label correct
- [ ] "Book Outline" download label correct
- [ ] Assemble endpoint works for F-invitee (same as C-tier)
- [ ] Chapter editor and AI chat work for F-invitee
- [ ] C-tier memoir workspace still shows "Memoir" labels (not "Book")
- [ ] E-code invitees unaffected (still managed=True, no Go Deeper)
- [ ] Independent storytellers (no signupCode) still see upgrade button
- [ ] Portal F-tier admin lands on Legacy Collection (E) tab
- [ ] `GET /api/portal/invitees?tier=F` returns only F-code invitees
- [ ] `GET /api/portal/invitees?tier=C` returns only C-code invitees (existing behavior preserved)
- [ ] `portal-signup.html` shows F plan card and correct price
- [ ] `index.html` shows Book Builder upgrade line in Institutional section
- [ ] Python syntax check passes on server.py

---

## Success Criteria

1. A portal admin with tier F can open the Legacy Collection tab, see their F-code invitees listed under "Book Workspaces," click one, and land on a workspace labeled "Book Workspace" with "Assemble Book" as the action.
2. An F-code invitee experiences Go Deeper after recording, sees no My Memoir button, and has no upgrade prompts.
3. E-code invitees and C-tier memoir users experience no behavior change.
4. A new visitor to the pricing page can see "Legacy Collection + Book Builder" as an upgrade path from Legacy Collection.

---

## Notes

- Price for F-tier ($35/mo) is a placeholder — adjust before going live. The actual Stripe/payment integration (if any) is outside this plan's scope.
- Future: F-tier could also expose the assembled book to the invitee (as a read-only view) if the portal admin chooses to share it. That's a separate feature.
- The `loadLegacyPanel` recordings section currently loads `tier=E` recordings only. F invitees' recordings will appear in their individual Book Workspaces but not in the combined recordings list. If a combined view is wanted later, `loadLegacyPanel` can also fetch `tier=F` recordings.

---

## Implementation Notes

**Implemented:** 2026-05-07

### Summary

All 8 steps executed. F added to all three server.py tier validation sets. F-code signup logic maps invitees to tier C (deepening-capable). `list_portal_invitees` now accepts `?tier=` query param. `portal_invitee_data` returns `code_tier` in the invitee object. `hideUpgrade` in storyteller.html simplified to `managed || !!signupCode`. Portal Legacy Collection tab updated with F-code button and Book Workspaces invitee list. `portal.js` updated with F in tierOrder, `loadLegacyPanel`, `loadLegacyInvitees`, `openMemoirWorkspace(id, type)`. `portal-signup.html` has new planF card and PLAN_LABELS entry. `index.html` Institutional Legacy card shows Book Builder upgrade link. `portal-memoir.html` reads `?type=book` and swaps all Memoir→Book labels throughout. CLAUDE.md updated with tier summary.

### Deviations from Plan

None — all steps executed as specified.

### Issues Encountered

None.
