# Plan: Portal-Controlled Memoir Compilation for C-Tier Invitees

**Created:** 2026-05-06
**Status:** Implemented
**Request:** Build portal-admin memoir compilation for C-tier (Storyteller + Memoir Builder) invite code users — invitees record and deepen, portal admin assembles and edits the memoir.

---

## Overview

### What This Plan Accomplishes

Portal admins who issue C-tier invite codes gain a memoir workspace for each of their invitees: read-only access to all recordings and deepening sessions, a one-click memoir assembly button, and full chapter editing powered by Claude. The invitee experience is unchanged — they record and go deeper; they never see the assembly, outline, or editing tools. Independent (non-invited) storytellers retain the full self-directed pipeline on `/memoir` unchanged.

### Why This Matters

This completes the institutional use case (e.g. Duluth Sister Cities, family history projects): a portal admin curates questions, invitees answer them at their own pace with optional AI deepening, and the admin compiles the final memoir. The handoff is clean — recording and deepening belong to the invitee, compilation belongs to the admin.

---

## Current State

### Relevant Existing Structure

- `apps/cogna/server.py` — all memoir endpoints (`/api/memoir/*`) use `_auth_storyteller_user()`, tying them to a storyteller token
- `apps/cogna/static/memoir.html` — full memoir pipeline UI: dashboard → assemble → chapter editor. Uses `st_token` from localStorage. 720 lines.
- `apps/cogna/static/portal.html` — C-tab (`panelC`) shows promo codes, a note linking to prompts, and a recordings list. No invitee-level view or memoir controls.
- `apps/cogna/static/portal.js` — `loadStoryPanel('C')` loads recordings grouped by C-code. `switchDashTab` handles C-tab activation.
- `apps/cogna/supabase_schema.sql` — `storyteller_users.signup_code` links invitees to promo codes; `promo_codes.created_by` links codes to portal admin email. `book_bibles` and `chapters` are keyed by `storyteller_user_id`.

### Gaps or Problems Being Addressed

- No portal-side API endpoints for memoir operations — all existing memoir endpoints require a storyteller token
- No way for portal admin to view an invitee's recordings and deepening sessions
- No portal-side memoir assembly or chapter editing UI
- C-tab in portal is minimal — shows codes and recordings but no path to memoir work

---

## Proposed Changes

### Summary of Changes

- Add server helper `_get_storyteller_user_by_id(storyteller_id)` for lookups by `id` field
- Add server helper `_verify_portal_owns_storyteller(portal_user, storyteller_id)` — checks `promo_codes.created_by`
- Add new endpoint `GET /api/portal/invitees` — lists all storytellers who used this admin's C-codes
- Add new endpoint `GET /api/portal/invitee/{storyteller_id}/data` — recordings + deepening sessions + book_bible + chapters for one invitee
- Add new endpoint `POST /api/portal/invitee/{storyteller_id}/memoir/assemble` — triggers memoir assembly for an invitee
- Add new endpoint `GET /api/portal/invitee/{storyteller_id}/memoir/chapters` — get chapters
- Add new endpoint `PUT /api/portal/invitee/{storyteller_id}/memoir/chapters/{chapter_id}` — save chapter content
- Add new endpoint `POST /api/portal/invitee/{storyteller_id}/memoir/chapters/{chapter_id}/edit` — AI editorial chat
- Create new page `apps/cogna/static/portal-memoir.html` — portal admin memoir workspace for a specific invitee
- Update `portal.html` C-tab — add invitee list section with "Open Memoir Workspace" button per invitee
- Update `portal.js` — add `loadInvitees()`, `openMemoirWorkspace(storytellerId)` methods; call `loadInvitees()` when C-tab activates
- Add route `GET /portal/memoir` in `server.py` to serve `portal-memoir.html`

### New Files to Create

| File Path | Purpose |
|-----------|---------|
| `apps/cogna/static/portal-memoir.html` | Portal admin memoir workspace — read-only recordings view, assemble button, chapter editor |

### Files to Modify

| File Path | Changes |
|-----------|---------|
| `apps/cogna/server.py` | Add `_get_storyteller_user_by_id`, `_verify_portal_owns_storyteller`, 6 new portal-invitee endpoints, route for portal-memoir page |
| `apps/cogna/static/portal.html` | Add invitee list section to C-tab panel |
| `apps/cogna/static/portal.js` | Add `loadInvitees()`, `openMemoirWorkspace()`, call on C-tab switch |

---

## Design Decisions

### Key Decisions Made

1. **New portal-specific endpoints rather than modifying existing memoir endpoints**: Keeps the two auth models cleanly separated. Portal admin uses `_auth_user()` (portal token). Existing `/api/memoir/*` endpoints for storytellers are untouched.

2. **`book_bibles` and `chapters` stay tied to `storyteller_user_id`**: Reuses existing tables. When the portal admin assembles a memoir, it's stored under the invitee's `storyteller_user_id` — same as if the storyteller had done it themselves. This means if the invitee later gains independent access, their memoir is already there.

3. **New page `/portal/memoir` rather than embedding in portal.html**: The memoir editor is complex (chapter sidebar, AI chat, etc.). A dedicated page keeps portal.html manageable and allows the memoir workspace to have its own full-screen layout.

4. **Authorization via `promo_codes.created_by`**: Portal admin can only access invitees whose `signup_code` was created by that admin. Prevents cross-account data access.

5. **Invitees limited to C-codes**: `GET /api/portal/invitees` only returns storytellers who used C-codes from this admin. B-code and E-code invitees are not included (they don't have memoir access in their tier).

6. **Recordings are read-only in portal memoir workspace**: No delete, no transcript edit. The portal admin can view and use the content for assembly but cannot alter it.

### Alternatives Considered

- **Proxy token approach** (portal admin gets a temp storyteller token to impersonate invitee): Rejected — bypasses auth model and is a security risk.
- **Embed memoir editor inside portal.html as a modal**: Rejected — too much complexity in one file; full-screen editor is better UX.
- **Store memoir under portal_user rather than storyteller_user_id**: Rejected — would require schema changes and break the existing memoir pipeline. Keeping it under storyteller_user_id means we can reuse all existing memoir logic.

### Open Questions

None — all design decisions resolved.

---

## Step-by-Step Tasks

### Step 1: Add server helpers and route for portal-memoir page

Add two helpers after the existing `_get_storyteller_user` helper, and add the page route.

**Actions:**

- In `server.py`, after `_get_storyteller_user`, add:

```python
def _get_storyteller_user_by_id(storyteller_id: str) -> Optional[Dict[str, Any]]:
    if supabase:
        r = supabase.table("storyteller_users").select("*").eq("id", storyteller_id).limit(1).execute()
        return r.data[0] if r.data else None
    db = _load_db()
    return db.get("storyteller_users", {}).get(storyteller_id)


def _verify_portal_owns_storyteller(portal_user: Dict, storyteller_id: str) -> Dict[str, Any]:
    """Return storyteller record if the portal admin owns the invite code they used."""
    st_user = _get_storyteller_user_by_id(storyteller_id)
    if not st_user:
        raise HTTPException(status_code=404, detail="Storyteller not found")
    signup_code = st_user.get("signup_code")
    if not signup_code:
        raise HTTPException(status_code=403, detail="This storyteller did not sign up with your code")
    if supabase:
        r = supabase.table("promo_codes").select("created_by").eq("code", signup_code).limit(1).execute()
        created_by = r.data[0].get("created_by") if r.data else None
    else:
        db = _load_db()
        pc = db.get("promo_codes", {}).get(signup_code)
        created_by = pc.get("created_by") if pc else None
    if created_by != portal_user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return st_user
```

- Add page route near the other static page routes (near `def memoir()`):

```python
@app.get("/portal/memoir")
def portal_memoir_page():
    return FileResponse(os.path.join(STATIC_DIR, "portal-memoir.html"))
```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 2: Add portal invitee API endpoints

Add six new endpoints in `server.py` in a new section `# Portal-invitee memoir endpoints` after the existing memoir endpoints (after line ~1920).

**Actions:**

**Endpoint 1 — List C-tier invitees:**
```python
@app.get("/api/portal/invitees")
def list_portal_invitees(authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    # Get all C-codes owned by this portal user
    if supabase:
        codes_r = supabase.table("promo_codes").select("code").eq("created_by", portal_user["email"]).eq("tier", "C").execute()
        codes = [r["code"] for r in (codes_r.data or [])]
        if not codes:
            return {"invitees": []}
        st_r = supabase.table("storyteller_users").select("id, email, first_name, last_name, created_at").in_("signup_code", codes).order("created_at").execute()
        invitees = st_r.data or []
    else:
        db = _load_db()
        codes = {c["code"] for c in db.get("promo_codes", {}).values() if c.get("created_by") == portal_user["email"] and c.get("tier") == "C"}
        invitees = sorted([{"id": u["id"], "email": u["email"], "first_name": u.get("first_name", ""), "last_name": u.get("last_name", ""), "created_at": u.get("created_at", "")} for u in db.get("storyteller_users", {}).values() if u.get("signup_code") in codes], key=lambda x: x.get("created_at", ""))
    return {"invitees": invitees}
```

**Endpoint 2 — Invitee data (recordings + deepening + memoir):**
```python
@app.get("/api/portal/invitee/{storyteller_id}/data")
def portal_invitee_data(storyteller_id: str, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    user_id = st_user["id"]
    # Same query pattern as memoir_dashboard but keyed by user_id
    if supabase:
        r = supabase.table("story_recordings").select("id, prompt_id, transcript, created_at").eq("storyteller_user_id", user_id).order("created_at").execute()
        recordings = r.data or []
        prompt_ids = [rec["prompt_id"] for rec in recordings if rec.get("prompt_id")]
        prompt_map = {}
        if prompt_ids:
            pr = supabase.table("story_prompts").select("id, text").in_("id", prompt_ids).execute()
            prompt_map = {p["id"]: p["text"] for p in (pr.data or [])}
        ms = supabase.table("memoir_sessions").select("id, recording_id, finished").eq("storyteller_user_id", user_id).execute()
        session_map = {s["recording_id"]: s for s in (ms.data or [])}
        bb = supabase.table("book_bibles").select("id, content, assembled_at").eq("storyteller_user_id", user_id).order("assembled_at", desc=True).limit(1).execute()
        book_bible = bb.data[0] if bb.data else None
        ch = supabase.table("chapters").select("id, title, sort_order, content, updated_at").eq("storyteller_user_id", user_id).order("sort_order").execute()
        chapters = ch.data or []
    else:
        db = _load_db(); _memoir_db_defaults(db)
        recordings = sorted([rec for rec in db["story_recordings"].values() if rec.get("storyteller_user_id") == user_id], key=lambda x: x.get("created_at", ""))
        prompt_map = {p["id"]: p["text"] for p in db.get("story_prompts", {}).values()}
        session_map = {s["recording_id"]: s for s in db["memoir_sessions"].values() if s.get("storyteller_user_id") == user_id}
        bbs = sorted([b for b in db["book_bibles"].values() if b.get("storyteller_user_id") == user_id], key=lambda x: x.get("assembled_at", ""), reverse=True)
        book_bible = bbs[0] if bbs else None
        chapters = sorted([c for c in db["chapters"].values() if c.get("storyteller_user_id") == user_id], key=lambda x: x.get("sort_order", 0))
    for rec in recordings:
        rec["prompt_text"] = prompt_map.get(rec.get("prompt_id") or "", "Custom question")
        session = session_map.get(rec["id"])
        rec["deepening_status"] = "finished" if session and session.get("finished") else ("started" if session else "none")
        rec["memoir_session_id"] = session["id"] if session else None
    return {
        "invitee": {"id": st_user["id"], "first_name": st_user.get("first_name", ""), "last_name": st_user.get("last_name", ""), "email": st_user["email"]},
        "recordings": recordings,
        "book_bible": book_bible,
        "chapters": chapters,
    }
```

**Endpoint 3 — Assemble memoir:**
```python
@app.post("/api/portal/invitee/{storyteller_id}/memoir/assemble")
async def portal_invitee_assemble(storyteller_id: str, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    user_id = st_user["id"]
    # Reuse same assembly logic as memoir_assemble but with user_id from invitee
    if supabase:
        r = supabase.table("story_recordings").select("id, prompt_id, transcript, created_at").eq("storyteller_user_id", user_id).order("created_at").execute()
        recordings = r.data or []
        prompt_ids = [rec["prompt_id"] for rec in recordings if rec.get("prompt_id")]
        prompt_map = {}
        if prompt_ids:
            pr = supabase.table("story_prompts").select("id, text").in_("id", prompt_ids).execute()
            prompt_map = {p["id"]: p["text"] for p in (pr.data or [])}
        ms = supabase.table("memoir_sessions").select("recording_id, messages").eq("storyteller_user_id", user_id).eq("finished", True).execute()
        sessions_by_recording = {s["recording_id"]: s["messages"] for s in (ms.data or [])}
    else:
        db = _load_db(); _memoir_db_defaults(db)
        recordings = sorted([rec for rec in db["story_recordings"].values() if rec.get("storyteller_user_id") == user_id], key=lambda x: x.get("created_at", ""))
        prompt_map = {p["id"]: p["text"] for p in db.get("story_prompts", {}).values()}
        sessions_by_recording = {s["recording_id"]: s["messages"] for s in db["memoir_sessions"].values() if s.get("storyteller_user_id") == user_id and s.get("finished")}
    if not recordings:
        raise HTTPException(status_code=400, detail="No recordings found to assemble")
    context_parts = []
    for rec in recordings:
        question = prompt_map.get(rec.get("prompt_id") or "", "Custom question")
        context_parts.append(f"QUESTION: {question}\nANSWER: {rec.get('transcript', '')}")
        if rec["id"] in sessions_by_recording:
            msgs = sessions_by_recording[rec["id"]]
            exchanges = [f"  {'AI' if m['role'] == 'assistant' else 'User'}: {m['content']}" for m in msgs]
            context_parts.append("FOLLOW-UP CONVERSATION:\n" + "\n".join(exchanges))
        context_parts.append("")
    full_context = "\n".join(context_parts)
    content = _generate_memoir_response(MEMOIR_ASSEMBLE_SYSTEM, [{"role": "user", "content": full_context}], max_tokens=2000)
    bible_id = "bible_" + secrets.token_hex(8)
    now = _utc_now()
    if supabase:
        supabase.table("book_bibles").insert({"id": bible_id, "storyteller_user_id": user_id, "content": content, "assembled_at": now}).execute()
    else:
        db["book_bibles"][bible_id] = {"id": bible_id, "storyteller_user_id": user_id, "content": content, "assembled_at": now}
        _save_db(db)
    return {"book_bible_id": bible_id, "content": content}
```

**Endpoint 4 — Get chapters:**
```python
@app.get("/api/portal/invitee/{storyteller_id}/memoir/chapters")
async def portal_invitee_get_chapters(storyteller_id: str, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    user_id = st_user["id"]
    if supabase:
        r = supabase.table("chapters").select("*").eq("storyteller_user_id", user_id).order("sort_order").execute()
        return {"chapters": r.data or []}
    db = _load_db(); _memoir_db_defaults(db)
    chapters = sorted([c for c in db["chapters"].values() if c.get("storyteller_user_id") == user_id], key=lambda x: x.get("sort_order", 0))
    return {"chapters": chapters}
```

**Endpoint 5 — Save chapter:**
```python
@app.put("/api/portal/invitee/{storyteller_id}/memoir/chapters/{chapter_id}")
async def portal_invitee_save_chapter(storyteller_id: str, chapter_id: str, payload: MemoirChapterRequest, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    updates = {"title": payload.title, "content": payload.content, "updated_at": _utc_now()}
    if supabase:
        supabase.table("chapters").update(updates).eq("id", chapter_id).eq("storyteller_user_id", st_user["id"]).execute()
    else:
        db = _load_db(); _memoir_db_defaults(db)
        if chapter_id in db["chapters"]:
            db["chapters"][chapter_id].update(updates)
        _save_db(db)
    return {"ok": True}
```

**Endpoint 6 — AI chapter edit chat:**
```python
@app.post("/api/portal/invitee/{storyteller_id}/memoir/chapters/{chapter_id}/edit")
async def portal_invitee_chapter_edit(storyteller_id: str, chapter_id: str, payload: MemoirChapterEditRequest, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    user_id = st_user["id"]
    if supabase:
        r = supabase.table("chapters").select("*").eq("id", chapter_id).eq("storyteller_user_id", user_id).limit(1).execute()
        chapter = r.data[0] if r.data else None
    else:
        db = _load_db(); _memoir_db_defaults(db)
        c = db["chapters"].get(chapter_id)
        chapter = c if c and c.get("storyteller_user_id") == user_id else None
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    messages = chapter.get("edit_messages") or []
    if not messages:
        system = MEMOIR_EDIT_SYSTEM + f"\n\nHere are the raw transcripts for this chapter:\n\n{chapter.get('content', '')}"
        messages.append({"role": "user", "content": "Please give me your initial editorial feedback on this chapter."})
        opening = _generate_memoir_response(system, messages)
        messages.append({"role": "assistant", "content": opening})
    messages.append({"role": "user", "content": payload.message})
    system = MEMOIR_EDIT_SYSTEM + f"\n\nHere are the raw transcripts for this chapter:\n\n{chapter.get('content', '')}"
    reply = _generate_memoir_response(system, messages)
    messages.append({"role": "assistant", "content": reply})
    if supabase:
        supabase.table("chapters").update({"edit_messages": messages, "updated_at": _utc_now()}).eq("id", chapter_id).execute()
    else:
        db["chapters"][chapter_id]["edit_messages"] = messages
        db["chapters"][chapter_id]["updated_at"] = _utc_now()
        _save_db(db)
    return {"message": reply}
```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 3: Create portal-memoir.html

Create `apps/cogna/static/portal-memoir.html`. This is a standalone page adapted from `memoir.html` with these key differences:
- Auth: reads `portal_token` from localStorage (not `st_token`)
- Reads `?id=<storyteller_id>` from URL params to know which invitee's memoir to load
- If no `portal_token` or no `?id`, redirects to `/portal`
- All API calls go to `/api/portal/invitee/{storytellerId}/...`
- Recordings section is read-only: displays transcript text, deepening status badge, no action buttons
- Assembly button calls `POST /api/portal/invitee/{id}/memoir/assemble`
- Chapter editor calls portal-specific chapter endpoints
- Nav shows "← Back to portal" link and invitee name

**Full page structure:**
- Progress steps: `Recordings → Assemble → Edit Chapters` (same visual as memoir.html)
- **Screen 1: Recordings** — list all recordings with prompt text, transcript (collapsed/expandable), deepening badge (None / In Progress / Deepened). No action buttons. Button at bottom: "Assemble Memoir →" (if recordings exist) or disabled state.
- **Screen 2: Assembling** — spinner while Claude processes (same pattern as memoir.html)
- **Screen 3: Chapter Editor** — left sidebar chapter list, right panel with textarea + AI chat. Save and Download buttons. "Download Full Manuscript" button. "← Back to recordings" link.

The page uses the same CSS variables and design tokens as `memoir.html`. Copy the CSS and layout structure; change only the JS auth model and API base URL.

Key JS structure:
```javascript
const PORTAL_API = window.location.origin + '/api/portal/invitee';
const params = new URLSearchParams(window.location.search);
const STORYTELLER_ID = params.get('id');

const pmState = {
  authToken: '',      // portal token
  storytellerId: STORYTELLER_ID,
  invitee: null,      // {first_name, last_name, email}
  recordings: [],
  bookBible: null,
  chapters: [],
  currentChapterId: null,
};

function apiUrl(path) {
  return `${PORTAL_API}/${pmState.storytellerId}${path}`;
}

async function apiFetch(url, opts = {}) {
  opts.headers = { ...opts.headers, 'Authorization': 'Bearer ' + pmState.authToken };
  const res = await fetch(url, opts);
  if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.detail || 'Request failed'); }
  return res.json();
}

window.addEventListener('load', async () => {
  const token = localStorage.getItem('portal_token');
  if (!token || !STORYTELLER_ID) { window.location = '/portal'; return; }
  pmState.authToken = token;
  // Load invitee data
  const data = await apiFetch(apiUrl('/data'));
  pmState.invitee = data.invitee;
  pmState.recordings = data.recordings;
  pmState.bookBible = data.book_bible;
  pmState.chapters = data.chapters;
  // Show name in nav
  document.getElementById('inviteeName').textContent =
    `${data.invitee.first_name} ${data.invitee.last_name}`.trim() || data.invitee.email;
  // Route to appropriate screen
  if (pmState.chapters.length > 0) {
    pm.showChapterEditor();
  } else if (pmState.bookBible) {
    pm.showChapterEditor();
  } else {
    pm.showRecordings();
  }
});
```

**Files affected:**
- `apps/cogna/static/portal-memoir.html` (new file)

---

### Step 4: Update portal C-tab to show invitee list

In `portal.html`, update `panelC` to add an invitees section above the recordings. This section shows each C-code invitee with their name, email, deepening count, and an "Open Memoir Workspace →" button.

**Actions:**

Replace the recordings section header in `panelC` with this expanded layout (add BEFORE the existing recordings section):

```html
<div class="section-header-row" style="margin-top:32px">
  <h2 class="section-title">Memoir Workspaces</h2>
</div>
<p style="font-size:13px;color:var(--ink-muted);margin-bottom:16px">
  Each person who used a C-code gets their own memoir workspace. View their recordings, assemble a memoir, and edit chapters.
</p>
<div id="inviteeList" class="stories-list" style="margin-bottom:40px">
  <div class="empty-state"><p>No invitees yet. Generate a C-code and share it to get started.</p></div>
</div>
```

Keep the existing promo codes section and the prompts note. The recordings section can be removed from `panelC` since the invitee list + memoir workspace gives a better per-person view. (The recordings section was redundant with the per-invitee workspace.)

**Files affected:**
- `apps/cogna/static/portal.html`

---

### Step 5: Update portal.js to load invitees and open memoir workspace

**Actions:**

1. Update `switchDashTab` — when tab === 'C', call `portal.loadInvitees()` instead of `portal.loadStoryPanel('C')`:

Change:
```javascript
else if (tab === 'C') portal.loadStoryPanel('C');
```
To:
```javascript
else if (tab === 'C') portal.loadInvitees();
```

2. Add `loadInvitees()` method to the portal object:

```javascript
async loadInvitees() {
  const el = document.getElementById('inviteeList');
  if (!el) return;
  try {
    const data = await req(`${api}/portal/invitees`, { headers: authHeaders() });
    const invitees = data.invitees || [];
    if (!invitees.length) {
      el.innerHTML = '<div class="empty-state"><p>No invitees yet. Generate a C-code and share it to get started.</p></div>';
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
            <button class="story-action-btn" onclick="portal.openMemoirWorkspace('${inv.id}')">Open Memoir Workspace →</button>
          </div>
        </div>`;
    }).join('');
  } catch (err) {
    if (el) el.innerHTML = `<div class="empty-state"><p>Error loading invitees: ${err.message}</p></div>`;
  }
},

openMemoirWorkspace(storytellerId) {
  window.location = `/portal/memoir?id=${storytellerId}`;
},
```

**Files affected:**
- `apps/cogna/static/portal.js`

---

## Connections & Dependencies

### Files That Reference This Area

- `apps/cogna/static/portal.html` — C-tab panel updated
- `apps/cogna/static/portal.js` — invitee loading and navigation
- `apps/cogna/server.py` — all new endpoints
- `apps/cogna/static/portal-memoir.html` — new page (new file)

### Updates Needed for Consistency

- `CLAUDE.md` — mention `/portal/memoir` page in MyCogna app section
- `apps/cogna/supabase_schema.sql` — no schema changes needed (reuses existing tables)

### Impact on Existing Workflows

- Independent storytellers (no signup_code): zero impact — `/memoir` page and all `/api/memoir/*` endpoints unchanged
- Portal-invited C-tier storytellers: they still can't access `/memoir` (hidden in UI, would redirect to `/storyteller` if accessed directly since they have an `st_token` but the page checks managed/signupCode)
- Portal admins: new workflow via C-tab → invitee list → memoir workspace

---

## Validation Checklist

- [ ] `GET /api/portal/invitees` returns C-code invitees for the logged-in portal admin only
- [ ] `GET /api/portal/invitee/{id}/data` returns 403 for invitees belonging to a different admin
- [ ] `POST /api/portal/invitee/{id}/memoir/assemble` produces a book bible stored under `storyteller_user_id`
- [ ] Chapter save and AI edit endpoints work correctly
- [ ] Portal C-tab shows invitee list after switching to it
- [ ] "Open Memoir Workspace" button navigates to `/portal/memoir?id=...`
- [ ] `portal-memoir.html` redirects to `/portal` if no `portal_token` or no `?id` param
- [ ] Recordings display as read-only (no edit/delete buttons)
- [ ] Assembling shows loading state; on completion transitions to chapter editor
- [ ] Chapter editor allows text editing + AI chat
- [ ] Existing `/memoir` page for independent storytellers still works normally
- [ ] Portal admin cannot access invitee data for a different admin's invitees (403)

---

## Success Criteria

1. A portal admin can open the C-tab, see all their C-code invitees, click one, and land on a workspace showing that person's recordings and deepening sessions — read-only.
2. The portal admin can click "Assemble Memoir" and receive a structured book bible with chapters for editing.
3. The chapter editor works: portal admin can edit chapter text and chat with Claude for editorial feedback.
4. Independent storytellers on `/memoir` experience no changes.
5. Invited C-tier storytellers cannot access `/portal/memoir` or any of the new portal-invitee endpoints.

---

## Notes

- The `portal-memoir.html` page authenticates with `portal_token` (stored as `localStorage.getItem('portal_token')`) — confirm this key name matches what `portal.js` sets on login. If it uses a different key name, update accordingly.
- Future: portal admin could add chapters manually (not just from assembly). The `POST /api/portal/invitee/{id}/memoir/chapters` endpoint could be added later.
- Future: if a storyteller later upgrades to independent access, their assembled memoir (stored under `storyteller_user_id`) will already be visible in their own `/memoir` dashboard.

---

## Implementation Notes

**Implemented:** 2026-05-06

### Summary

All five steps executed. Six new server endpoints added under `/api/portal/invitee/{id}/...`. Two new server helpers (`_get_storyteller_user_by_id`, `_verify_portal_owns_storyteller`) added. Page route `/portal/memoir` added. New `portal-memoir.html` created (read-only recordings, assemble, chapter editor with AI chat). Portal C-tab updated to show invitee list instead of recordings. `portal.js` updated with `loadInvitees()` and `openMemoirWorkspace()`.

### Deviations from Plan

None.

### Issues Encountered

None.
