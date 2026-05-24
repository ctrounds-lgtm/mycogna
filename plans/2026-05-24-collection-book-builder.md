# Plan: Legacy Collection Book Builder

**Created:** 2026-05-24
**Status:** Draft
**Request:** Build a dedicated Collection Book Builder page for F-tier portal users that compiles all enrolled storytellers' recordings into a structured collective book, mirroring the individual memoir assembly flow.

---

## Overview

### What This Plan Accomplishes

A new standalone page (`portal-collection-book.html` at `/portal/collection-book`) gives F-tier Legacy Collection + Book Builder users a two-screen workspace: an Assemble screen where Claude reads all storytellers' recordings and generates an editable Book Bible, Chapter Outline, and What's Missing section; and an Edit screen where chapters are drafted and refined with Claude's help, including a one-click "first pass" generator.

### Why This Matters

F-tier is MyCogna's highest-value tier. Its differentiator over E-tier is the Book Builder — the ability to weave multiple storytellers' voices into a single organized archive. Without a working, end-to-end book compilation experience, F-tier has no functional premium over E-tier. This plan delivers that experience cleanly, replacing the broken IS_COLLECTION branching in portal-memoir.html with a purpose-built page that's easier to maintain and debug.

---

## Current State

### Relevant Existing Structure

- `apps/cogna/static/portal-memoir.html` — individual memoir workspace (3-screen: Recordings → Assemble → Edit). UI/UX reference for this build.
- `apps/cogna/static/portal.html` — F-tier panel has `<a href="/portal/memoir?type=collection">` tab that currently redirects back to the Questions tab due to auth/data errors
- `apps/cogna/server.py` — collection endpoints already exist (lines ~3061–3240):
  - `GET /api/portal/collection/data` — returns recordings + book_bible + chapters + storyteller_count
  - `POST /api/portal/collection/memoir/assemble` — calls Claude, returns `{book_bible_id, content}` (one blob, not parsed)
  - `POST /api/portal/collection/memoir/chapters` — create chapter
  - `GET /api/portal/collection/memoir/chapters` — list chapters
  - `PUT /api/portal/collection/memoir/chapters/{id}` — save chapter
  - `POST /api/portal/collection/memoir/chapters/{id}/edit` — chat-style editing (has a bug: calls `_build_memoir_edit_system` with portal email, which queries wrong tables)
- `apps/cogna/supabase_schema.sql` — `collection_book_bibles` and `collection_chapters` tables defined (migration must be run manually)
- `apps/cogna/server.py` line 3159 — `MEMOIR_ASSEMBLE_SYSTEM` already instructs Claude to output `BOOK BIBLE:` / `CHAPTER OUTLINE:` / `WHAT'S MISSING:` sections

### Gaps or Problems Being Addressed

1. **No working navigation** — `/portal/memoir?type=collection` errors out and redirects back to portal
2. **Assembly returns one unparsed blob** — frontend can't cleanly display/edit the three sections separately
3. **No schema columns for chapter_outline and whats_missing** — they're buried in the content blob
4. **No "first pass" chapter generation** — a core F-tier feature is missing
5. **Collection chapter editing uses wrong system prompt builder** — `_build_memoir_edit_system` queries `book_bibles` and `storyteller_users`, not the collection tables
6. **No auto-population of chapters from outline** — user has no path from outline to editor without manually creating each chapter
7. **IS_COLLECTION branching is tangled and hard to debug** — a clean dedicated page removes all ambiguity

---

## Proposed Changes

### Summary of Changes

- Create new `portal-collection-book.html` — dedicated two-screen workspace
- Add `GET /portal/collection-book` route in server.py
- Modify `POST /api/portal/collection/memoir/assemble` to parse and return three separate fields + store chapter_outline and whats_missing separately
- Add `PUT /api/portal/collection/memoir/bible` — saves user edits to book bible and/or chapter outline
- Add `POST /api/portal/collection/memoir/chapters/{id}/first-pass` — Claude generates a draft chapter
- Add `POST /api/portal/collection/memoir/chapters/from-outline` — parses chapter outline text and bulk-creates chapters
- Add `_build_collection_edit_system()` — correct system prompt builder for collection chapter editing
- Fix `portal_collection_chapter_edit` to call the new collection edit system builder
- Update portal.html tab href from `/portal/memoir?type=collection` to `/portal/collection-book`
- Add schema migration for two new columns on `collection_book_bibles`

### New Files to Create

| File Path | Purpose |
|---|---|
| `apps/cogna/static/portal-collection-book.html` | Dedicated collection book builder page (two screens: Assemble + Edit) |

### Files to Modify

| File Path | Changes |
|---|---|
| `apps/cogna/server.py` | New route, modified assemble endpoint, new save-bible/first-pass/from-outline endpoints, new collection edit system builder |
| `apps/cogna/static/portal.html` | Update `<a>` href to `/portal/collection-book` |
| `apps/cogna/supabase_schema.sql` | Add chapter_outline and whats_missing columns to collection_book_bibles |

---

## Design Decisions

### Key Decisions Made

1. **Dedicated page, not IS_COLLECTION branching**: A separate `portal-collection-book.html` is easier to debug, test, and maintain than weaving collection logic through portal-memoir.html. The IS_COLLECTION path has caused multiple hard-to-trace redirect bugs.

2. **Two screens only (Assemble + Edit), no Recordings screen**: Individual users need the Recordings screen to review what they've recorded. F-tier portal admins already see storyteller recordings in the Stories tab. Starting directly on the Assemble screen is a cleaner entry point.

3. **Three sections parsed server-side**: The assemble endpoint parses Claude's output into `book_bible`, `chapter_outline`, `whats_missing` before returning — simpler and more reliable than client-side regex.

4. **Book Bible and Chapter Outline are editable textareas, auto-saved on blur**: Mirrors a note-taking pattern the user is already familiar with; no explicit save button needed for these fields.

5. **"Proceed to editing" auto-populates chapters if none exist**: When the user first proceeds to the Edit screen with an empty chapter list, the frontend sends the chapter_outline text to `chapters/from-outline` which parses and creates them. On subsequent visits, existing chapters are shown unchanged.

6. **"Ask Claude for first pass" generates and inserts draft content**: The first-pass endpoint reads the Book Bible + all collection recordings + the chapter title and writes a draft. The draft is saved to the chapter and displayed in the editor — the user then edits it directly or uses the chat interface for refinement.

7. **`portal_user["email"]` as portal_id throughout**: The `users` table has no `id` column; email is the primary key. All collection endpoints already use `portal_user["email"]` after the recent fix; this plan is consistent.

### Alternatives Considered

- **Reuse portal-memoir.html with IS_COLLECTION**: Rejected because the redirect bug was caused by tangled IS_COLLECTION logic and it would continue to be fragile. A clean page is more maintainable.
- **Client-side section parsing**: Rejected in favor of server-side parsing — more reliable, no regex fragility in JS.

### Open Questions

None — all design decisions are settled.

---

## Step-by-Step Tasks

### Step 1: Add schema migration for new columns

Add two new columns to `collection_book_bibles` to store the three parsed sections separately from the raw blob.

**Actions:**
- Append to the bottom of `apps/cogna/supabase_schema.sql`:
  ```sql
  ALTER TABLE collection_book_bibles ADD COLUMN IF NOT EXISTS chapter_outline TEXT;
  ALTER TABLE collection_book_bibles ADD COLUMN IF NOT EXISTS whats_missing TEXT;
  ```
- Note in the file (as a comment) that this migration must be run in the Supabase SQL editor

**Files affected:**
- `apps/cogna/supabase_schema.sql`

---

### Step 2: Add helper to parse Claude's assembly output

Add a function in `server.py` that splits the raw Claude response into three named sections.

**Actions:**
- Add after the existing `MEMOIR_ASSEMBLE_SYSTEM` constant (around line 2414):
  ```python
  def _parse_assembly_output(text: str) -> dict:
      """Split Claude's assembly output into book_bible, chapter_outline, whats_missing."""
      import re
      def extract(label: str, text: str) -> str:
          pattern = rf'\*?\*?{label}\*?\*?:?\s*(.*?)(?=\*?\*?(?:BOOK BIBLE|CHAPTER OUTLINE|WHAT\'S MISSING)\*?\*?:|$)'
          m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
          return m.group(1).strip() if m else ''
      return {
          'book_bible':      extract('BOOK BIBLE', text),
          'chapter_outline': extract('CHAPTER OUTLINE', text),
          'whats_missing':   extract("WHAT'S MISSING", text),
      }
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 3: Add a collection-specific assembly system prompt

The current collection system prompt appends a short note to `MEMOIR_ASSEMBLE_SYSTEM`. Replace with a dedicated constant that's explicit about the multi-storyteller context.

**Actions:**
- Add a new constant `COLLECTION_ASSEMBLE_SYSTEM` after `MEMOIR_EDIT_SYSTEM`:
  ```python
  COLLECTION_ASSEMBLE_SYSTEM = """You are an experienced editor assembling a collective Legacy Archive from the recorded stories of multiple contributors.

  You have been given transcripts grouped by storyteller name and question. Your job is to read across all contributors and produce three things:

  CRITICAL RULES:
  - Work only with what was actually said. Never invent details, events, or emotions.
  - If transcripts are too thin to support a full book, say so honestly.
  - Each storyteller's voice is distinct — honor that; don't flatten them into a single narrator.

  1. BOOK BIBLE: Write 3–5 paragraphs describing the collective themes, the range of voices, and the emotional arc of the archive as a whole. What unifies these stories? What tensions or contrasts make them interesting together? What is the organizing emotional truth of this collection?

  2. CHAPTER OUTLINE: Suggest 5–10 chapters that weave across multiple storytellers. Each chapter should gather multiple voices around a shared theme, question, or life stage. Format as a numbered list: chapter title in bold, followed by a 1–2 sentence description naming which storytellers' voices are most relevant.

  3. WHAT'S MISSING: A short, encouraging paragraph noting gaps — stories not yet told, questions not yet asked, voices not yet captured — that would strengthen the archive.

  Format your response with these exact section headers:
  BOOK BIBLE:
  CHAPTER OUTLINE:
  WHAT'S MISSING:

  Tone: warm, editorial, respectful of each contributor's individuality."""
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 4: Modify the assembly endpoint to return parsed sections

Update `portal_collection_assemble` to use the new system prompt, parse the output, store the parsed fields, and return all three sections.

**Actions:**
- Replace the current `portal_collection_assemble` function body with:
  ```python
  @app.post("/api/portal/collection/memoir/assemble")
  async def portal_collection_assemble(authorization: Optional[str] = Header(default=None)):
      portal_user = _auth_user(authorization)
      portal_id = portal_user["email"]
      storytellers = _get_f_tier_storyteller_ids(portal_user)
      st_ids = [s["id"] for s in storytellers]
      st_name_map = {s["id"]: " ".join(p for p in [s.get("first_name", ""), s.get("last_name", "")] if p) or s["email"] for s in storytellers}

      if not st_ids:
          raise HTTPException(status_code=400, detail="No storytellers found. Share an invite code first.")

      if supabase:
          recs_r = supabase.table("story_recordings").select("id, storyteller_user_id, prompt_id, transcript, created_at").in_("storyteller_user_id", st_ids).order("created_at").execute()
          recs = recs_r.data or []
          prompt_ids = list({rec["prompt_id"] for rec in recs if rec.get("prompt_id")})
          prompt_map = {}
          if prompt_ids:
              pr = supabase.table("story_prompts").select("id, text").in_("id", prompt_ids).execute()
              prompt_map = {p["id"]: p["text"] for p in (pr.data or [])}
      else:
          db = _load_db()
          recs = sorted([r for r in db["story_recordings"].values() if r.get("storyteller_user_id") in st_ids], key=lambda x: x.get("created_at", ""))
          prompt_map = {p["id"]: p["text"] for p in db.get("story_prompts", {}).values()}

      if not recs:
          raise HTTPException(status_code=400, detail="No recordings yet. Wait for your storytellers to record their stories first.")

      context_parts = []
      for rec in recs:
          name = st_name_map.get(rec.get("storyteller_user_id"), "Unknown")
          question = prompt_map.get(rec.get("prompt_id") or "", "Custom question")
          context_parts.append(f"STORYTELLER: {name}\nQUESTION: {question}\nANSWER: {rec.get('transcript', '')}\n")

      full_context = "\n---\n".join(context_parts)
      raw_content = _generate_memoir_response(COLLECTION_ASSEMBLE_SYSTEM, [{"role": "user", "content": full_context}], max_tokens=3000)
      parsed = _parse_assembly_output(raw_content)

      bible_id = "cbible_" + secrets.token_hex(8)
      now = _utc_now()
      record = {
          "id": bible_id,
          "portal_user_id": portal_id,
          "content": parsed["book_bible"],
          "chapter_outline": parsed["chapter_outline"],
          "whats_missing": parsed["whats_missing"],
          "assembled_at": now,
      }
      if supabase:
          supabase.table("collection_book_bibles").insert(record).execute()
      else:
          db = _load_db(); _collection_db_defaults(db)
          db["collection_book_bibles"][bible_id] = record
          _save_db(db)

      return {
          "book_bible_id": bible_id,
          "book_bible": parsed["book_bible"],
          "chapter_outline": parsed["chapter_outline"],
          "whats_missing": parsed["whats_missing"],
      }
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 5: Add save-bible endpoint (for user edits to Book Bible / Chapter Outline)

**Actions:**
- Add after the assemble endpoint:
  ```python
  class CollectionBibleSaveRequest(BaseModel):
      book_bible: Optional[str] = None
      chapter_outline: Optional[str] = None

  @app.put("/api/portal/collection/memoir/bible")
  async def portal_collection_save_bible(payload: CollectionBibleSaveRequest, authorization: Optional[str] = Header(default=None)):
      portal_user = _auth_user(authorization)
      portal_id = portal_user["email"]
      updates = {"assembled_at": _utc_now()}
      if payload.book_bible is not None:
          updates["content"] = payload.book_bible
      if payload.chapter_outline is not None:
          updates["chapter_outline"] = payload.chapter_outline
      if supabase:
          # Update the most recent bible for this portal user
          bb_r = supabase.table("collection_book_bibles").select("id").eq("portal_user_id", portal_id).order("assembled_at", desc=True).limit(1).execute()
          if bb_r.data:
              supabase.table("collection_book_bibles").update(updates).eq("id", bb_r.data[0]["id"]).execute()
      else:
          db = _load_db(); _collection_db_defaults(db)
          bbs = sorted([b for b in db["collection_book_bibles"].values() if b.get("portal_user_id") == portal_id], key=lambda x: x.get("assembled_at", ""), reverse=True)
          if bbs:
              bbs[0].update(updates)
          _save_db(db)
      return {"ok": True}
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 6: Add from-outline endpoint (bulk-creates chapters from parsed outline text)

**Actions:**
- Add after the save-bible endpoint:
  ```python
  class FromOutlineRequest(BaseModel):
      outline_text: str

  @app.post("/api/portal/collection/memoir/chapters/from-outline")
  async def portal_collection_chapters_from_outline(payload: FromOutlineRequest, authorization: Optional[str] = Header(default=None)):
      portal_user = _auth_user(authorization)
      portal_id = portal_user["email"]

      # Parse numbered list: "1. **Title** — description" or "1. Title — description"
      import re
      lines = payload.outline_text.strip().split("\n")
      chapters = []
      for line in lines:
          line = line.strip()
          if not line:
              continue
          m = re.match(r'^\d+\.\s+\*?\*?([^*\n]+?)\*?\*?\s*[—–-]?\s*(.*)', line)
          if m:
              title = m.group(1).strip()
              description = m.group(2).strip()
              chapters.append({"title": title, "content": description})

      if not chapters:
          raise HTTPException(status_code=400, detail="Could not parse any chapters from the outline.")

      now = _utc_now()
      created = []
      for i, ch in enumerate(chapters):
          chapter_id = "cc_" + secrets.token_hex(8)
          record = {
              "id": chapter_id,
              "portal_user_id": portal_id,
              "title": ch["title"],
              "content": ch["content"],
              "edit_messages": [],
              "sort_order": i,
              "created_at": now,
              "updated_at": now,
          }
          if supabase:
              supabase.table("collection_chapters").insert(record).execute()
          else:
              db = _load_db(); _collection_db_defaults(db)
              db["collection_chapters"][chapter_id] = record
              _save_db(db)
          created.append(record)

      return {"chapters": created}
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 7: Add first-pass chapter generation endpoint

**Actions:**
- Add after the from-outline endpoint:
  ```python
  COLLECTION_FIRST_PASS_SYSTEM = """You are a skilled editor writing a first-draft chapter for a Legacy Collection — a book that weaves together the recorded stories of multiple contributors.

  You have been given:
  - The Book Bible: the thematic overview and organizing vision for the entire collection
  - The chapter title and any existing description
  - All storyteller recordings from the collection

  Write a complete first-draft chapter that:
  1. Opens with a scene or line that draws the reader into the chapter's theme
  2. Weaves together relevant voices from multiple storytellers — quoting or paraphrasing their actual words
  3. Finds the thread that connects different contributors' experiences of this theme
  4. Closes with a line that resonates forward into the next chapter

  CRITICAL: Use only what was actually said. Never invent quotes, events, or details. If a storyteller's words are directly quoted, make that clear. Write in a warm, literary non-fiction style — like a skilled oral history editor, not a ghostwriter making things up.

  Return the chapter text only — no commentary, no preamble. Write it as finished prose."""

  @app.post("/api/portal/collection/memoir/chapters/{chapter_id}/first-pass")
  async def portal_collection_chapter_first_pass(chapter_id: str, authorization: Optional[str] = Header(default=None)):
      portal_user = _auth_user(authorization)
      portal_id = portal_user["email"]

      # Get chapter
      if supabase:
          r = supabase.table("collection_chapters").select("*").eq("id", chapter_id).eq("portal_user_id", portal_id).limit(1).execute()
          chapter = r.data[0] if r.data else None
      else:
          db = _load_db(); _collection_db_defaults(db)
          chapter = next((c for c in db["collection_chapters"].values() if c.get("id") == chapter_id and c.get("portal_user_id") == portal_id), None)
      if not chapter:
          raise HTTPException(status_code=404, detail="Chapter not found.")

      # Get Book Bible
      book_bible = ""
      if supabase:
          try:
              bb_r = supabase.table("collection_book_bibles").select("content").eq("portal_user_id", portal_id).order("assembled_at", desc=True).limit(1).execute()
              if bb_r.data:
                  book_bible = bb_r.data[0].get("content", "")
          except Exception:
              pass
      else:
          db = _load_db(); _collection_db_defaults(db)
          bbs = sorted([b for b in db["collection_book_bibles"].values() if b.get("portal_user_id") == portal_id], key=lambda x: x.get("assembled_at", ""), reverse=True)
          if bbs:
              book_bible = bbs[0].get("content", "")

      # Get all recordings
      storytellers = _get_f_tier_storyteller_ids(portal_user)
      st_ids = [s["id"] for s in storytellers]
      st_name_map = {s["id"]: " ".join(p for p in [s.get("first_name", ""), s.get("last_name", "")] if p) or s["email"] for s in storytellers}
      if supabase:
          recs_r = supabase.table("story_recordings").select("storyteller_user_id, prompt_id, transcript").in_("storyteller_user_id", st_ids).execute()
          recs = recs_r.data or []
          prompt_ids = list({rec["prompt_id"] for rec in recs if rec.get("prompt_id")})
          prompt_map = {}
          if prompt_ids:
              pr = supabase.table("story_prompts").select("id, text").in_("id", prompt_ids).execute()
              prompt_map = {p["id"]: p["text"] for p in (pr.data or [])}
      else:
          db = _load_db()
          recs = [r for r in db["story_recordings"].values() if r.get("storyteller_user_id") in st_ids]
          prompt_map = {p["id"]: p["text"] for p in db.get("story_prompts", {}).values()}

      recording_context = "\n---\n".join(
          f"STORYTELLER: {st_name_map.get(rec.get('storyteller_user_id'), 'Unknown')}\n"
          f"QUESTION: {prompt_map.get(rec.get('prompt_id') or '', 'Custom question')}\n"
          f"ANSWER: {rec.get('transcript', '')}"
          for rec in recs
      )

      user_message = (
          f"BOOK BIBLE:\n{book_bible}\n\n"
          f"CHAPTER TO WRITE: {chapter['title']}\n"
          f"CHAPTER DESCRIPTION: {chapter.get('content', '')}\n\n"
          f"ALL STORYTELLER RECORDINGS:\n{recording_context}"
      )

      draft = _generate_memoir_response(COLLECTION_FIRST_PASS_SYSTEM, [{"role": "user", "content": user_message}], max_tokens=2500)

      # Save draft as chapter content
      if supabase:
          supabase.table("collection_chapters").update({"content": draft, "updated_at": _utc_now()}).eq("id", chapter_id).execute()
      else:
          db = _load_db(); _collection_db_defaults(db)
          if chapter_id in db["collection_chapters"]:
              db["collection_chapters"][chapter_id]["content"] = draft
              db["collection_chapters"][chapter_id]["updated_at"] = _utc_now()
          _save_db(db)

      return {"content": draft}
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 8: Add collection-specific edit system builder and fix chapter edit endpoint

The existing chapter edit endpoint calls `_build_memoir_edit_system(portal_id, ...)` which queries `book_bibles` and `storyteller_users` — tables that don't apply to the collection context. Add a collection-specific version.

**Actions:**
- Add `_build_collection_edit_system` function after `_build_memoir_edit_system`:
  ```python
  def _build_collection_edit_system(portal_id: str, chapter_id: str, chapter_content: str) -> str:
      book_bible = ""
      sibling_chapters = []

      if supabase:
          try:
              bb = supabase.table("collection_book_bibles").select("content").eq("portal_user_id", portal_id).order("assembled_at", desc=True).limit(1).execute()
              if bb.data:
                  book_bible = bb.data[0].get("content", "")
          except Exception:
              pass
          try:
              chs = supabase.table("collection_chapters").select("title, content").eq("portal_user_id", portal_id).execute()
              sibling_chapters = [c for c in (chs.data or []) if c.get("id") != chapter_id]
          except Exception:
              pass
      else:
          db = _load_db(); _collection_db_defaults(db)
          bbs = sorted([b for b in db["collection_book_bibles"].values() if b.get("portal_user_id") == portal_id], key=lambda x: x.get("assembled_at", ""), reverse=True)
          if bbs:
              book_bible = bbs[0].get("content", "")
          sibling_chapters = [c for c in db["collection_chapters"].values() if c.get("portal_user_id") == portal_id and c.get("id") != chapter_id]

      system = MEMOIR_EDIT_SYSTEM
      if book_bible:
          system += f"\n\n---\nBOOK BIBLE (collection overview and structure):\n\n{book_bible}"
      if sibling_chapters:
          system += "\n\n---\nOTHER CHAPTERS ALREADY DRAFTED:\n" + "\n\n".join(
              f"Chapter: {c['title']}\n{(c.get('content') or '')[:300]}..." for c in sibling_chapters if c.get('content')
          )
      if chapter_content:
          system += f"\n\n---\nCURRENT CHAPTER CONTENT:\n\n{chapter_content}"
      return system
  ```

- In `portal_collection_chapter_edit`, replace:
  ```python
  system = _build_memoir_edit_system(portal_id, chapter_id, chapter.get("content", ""))
  ```
  with:
  ```python
  system = _build_collection_edit_system(portal_id, chapter_id, chapter.get("content", ""))
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 9: Add the new page route in server.py

**Actions:**
- Add after the existing `/portal/memoir` route (line ~431):
  ```python
  @app.get("/portal/collection-book")
  def portal_collection_book_page():
      return FileResponse(ROOT / "static" / "portal-collection-book.html")
  ```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 10: Update portal.html tab link

**Actions:**
- Find the `<a>` tag in the F-tier inner tab bar (around line 396 in portal.html):
  ```html
  <a href="/portal/memoir?type=collection" class="dash-tab" id="fTab-book" style="text-decoration:none">Compile into Book</a>
  ```
- Change to:
  ```html
  <a href="/portal/collection-book" class="dash-tab" id="fTab-book" style="text-decoration:none">Compile into Book</a>
  ```
- Also bump the version string from `v=20260524a` to `v=20260524b`

**Files affected:**
- `apps/cogna/static/portal.html`

---

### Step 11: Create portal-collection-book.html

Create the new standalone page. It has two screens: Assemble and Edit. Copy the CSS and structural patterns from portal-memoir.html.

**Full file content:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light" />
  <title>MyCogna · Collection Book Builder</title>
  <style>
    :root {
      --gold: #B8860B; --gold-light: #F5EDD6; --gold-pale: #FDFAF3;
      --cream: #FAF7F2; --ink: #1C1A17; --ink-muted: #6B6560;
      --border: #E8E2D9; --danger: #C0392B;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Georgia', serif; background: var(--cream); color: var(--ink); min-height: 100vh; }
    .screen { display: none; min-height: 100vh; }
    .screen.active { display: flex; flex-direction: column; }
    .top-nav {
      display: flex; align-items: center; justify-content: space-between;
      padding: 14px 20px; border-bottom: 1px solid var(--border);
      background: #fff; position: sticky; top: 0; z-index: 10;
    }
    .top-nav .wordmark { font-size: 13px; font-weight: 600; letter-spacing: 0.08em; color: var(--ink-muted); text-transform: uppercase; }
    .top-nav a, .top-nav button.link-btn {
      font-size: 13px; color: var(--ink-muted); text-decoration: none;
      background: none; border: none; cursor: pointer; font-family: inherit;
    }
    .top-nav a:hover, .top-nav button.link-btn:hover { color: var(--ink); }
    .page { max-width: 720px; margin: 0 auto; padding: 32px 20px 60px; width: 100%; }
    .btn-primary {
      display: block; width: 100%; padding: 14px 20px;
      background: var(--gold); color: #fff; border: none; border-radius: 10px;
      font-size: 16px; font-family: 'Georgia', serif; font-weight: 600;
      cursor: pointer; text-align: center;
    }
    .btn-primary:hover { opacity: 0.88; }
    .btn-primary:disabled { opacity: 0.5; cursor: default; }
    .btn-secondary {
      display: block; width: 100%; padding: 12px 20px;
      background: transparent; color: var(--ink); border: 1.5px solid var(--border);
      border-radius: 10px; font-size: 15px; font-family: 'Georgia', serif;
      cursor: pointer; text-align: center; margin-top: 10px;
    }
    .btn-secondary:hover { border-color: var(--ink-muted); }
    .btn-sm {
      display: inline-block; padding: 7px 14px;
      background: var(--gold-light); color: var(--gold); border: 1px solid #e0d0a0;
      border-radius: 6px; font-size: 13px; font-family: 'Georgia', serif; cursor: pointer;
    }
    .btn-sm:hover { background: #eee4c0; }
    .btn-first-pass {
      display: block; width: 100%; padding: 11px 20px; margin-bottom: 16px;
      background: #fff; color: var(--gold); border: 1.5px solid var(--gold);
      border-radius: 10px; font-size: 14px; font-family: 'Georgia', serif;
      cursor: pointer; text-align: center; font-weight: 600;
    }
    .btn-first-pass:hover { background: var(--gold-light); }
    .btn-first-pass:disabled { opacity: 0.5; cursor: default; }
    .stat-row { display: flex; gap: 20px; margin-bottom: 24px; }
    .stat { background: #fff; border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; flex: 1; text-align: center; }
    .stat-num { font-size: 28px; font-weight: 700; color: var(--gold); }
    .stat-label { font-size: 12px; color: var(--ink-muted); margin-top: 2px; }
    .section-label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.08em; color: var(--ink-muted); margin-bottom: 8px; }
    .section-block { margin-bottom: 28px; }
    .editable-area {
      width: 100%; padding: 16px; border: 1.5px solid var(--border); border-radius: 10px;
      font-size: 15px; font-family: 'Georgia', serif; line-height: 1.75; resize: vertical;
      color: var(--ink); background: #fff; min-height: 160px;
    }
    .editable-area:focus { outline: 2px solid var(--gold); border-color: transparent; }
    .readonly-box {
      background: var(--gold-pale); border: 1px solid var(--border); border-radius: 10px;
      padding: 16px; font-size: 15px; line-height: 1.75; color: var(--ink);
      white-space: pre-wrap;
    }
    .chapter-item {
      display: flex; align-items: center; justify-content: space-between;
      padding: 12px 14px; background: #fff; border: 1px solid var(--border);
      border-radius: 10px; margin-bottom: 8px; cursor: pointer; gap: 10px;
    }
    .chapter-item:hover { border-color: var(--gold); }
    .chapter-item.active { border-color: var(--gold); background: var(--gold-light); }
    .chapter-title-text { font-size: 14px; font-weight: 600; }
    .edit-layout { display: flex; gap: 20px; align-items: flex-start; }
    .edit-sidebar { width: 220px; flex-shrink: 0; }
    .edit-main { flex: 1; min-width: 0; }
    @media (max-width: 600px) { .edit-layout { flex-direction: column; } .edit-sidebar { width: 100%; } }
    .chapter-editor {
      width: 100%; min-height: 200px; padding: 14px; border: 1.5px solid var(--border);
      border-radius: 10px; font-size: 15px; font-family: 'Georgia', serif;
      line-height: 1.7; resize: vertical; color: var(--ink); margin-bottom: 12px;
    }
    .chapter-editor:focus { outline: 2px solid var(--gold); border-color: transparent; }
    .chat-messages { display: flex; flex-direction: column; gap: 14px; margin-bottom: 16px; }
    .chat-bubble { max-width: 85%; padding: 12px 16px; border-radius: 12px; font-size: 15px; line-height: 1.6; }
    .chat-bubble.ai { background: var(--gold-light); color: var(--ink); align-self: flex-start; border-bottom-left-radius: 4px; }
    .chat-bubble.user { background: var(--ink); color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }
    .chat-input-row { display: flex; gap: 10px; align-items: flex-end; }
    .chat-input-row textarea {
      flex: 1; padding: 12px 14px; border: 1.5px solid var(--border); border-radius: 10px;
      font-size: 15px; font-family: 'Georgia', serif; color: var(--ink); resize: none; height: 70px; line-height: 1.5;
    }
    .chat-input-row textarea:focus { outline: 2px solid var(--gold); border-color: transparent; }
    .chat-send-btn {
      padding: 12px 18px; background: var(--gold); color: #fff; border: none;
      border-radius: 10px; font-size: 15px; cursor: pointer; font-family: 'Georgia', serif;
    }
    .chat-send-btn:disabled { opacity: 0.5; cursor: default; }
    .divider { border: none; border-top: 1px solid var(--border); margin: 20px 0; }
    .empty-state { text-align: center; color: var(--ink-muted); padding: 32px 0; font-size: 15px; }
    .error-msg { color: var(--danger); font-size: 14px; margin-top: 8px; }
    .loading-msg { color: var(--ink-muted); font-size: 14px; font-style: italic; }
    h1 { font-size: clamp(22px, 5vw, 32px); margin-bottom: 6px; }
    h2 { font-size: clamp(18px, 4vw, 26px); margin-bottom: 6px; }
    .sub { color: var(--ink-muted); font-size: 15px; margin-bottom: 24px; line-height: 1.5; }
    .save-notice { font-size: 12px; color: var(--ink-muted); font-style: italic; margin-top: 4px; }
  </style>
</head>
<body>

<!-- ══════════════════════════════════════════════
     SCREEN: ASSEMBLE
══════════════════════════════════════════════ -->
<div class="screen" id="screenAssemble">
  <nav class="top-nav">
    <a href="/portal">← Back to portal</a>
    <span class="wordmark">MyCogna · Collection Book Builder</span>
    <span></span>
  </nav>
  <div class="page">
    <h1>Compile Combined Book</h1>
    <p class="sub" id="assembleSub">Loading…</p>

    <div class="stat-row">
      <div class="stat"><div class="stat-num" id="statStorytellers">—</div><div class="stat-label">Storytellers</div></div>
      <div class="stat"><div class="stat-num" id="statRecordings">—</div><div class="stat-label">Recordings</div></div>
      <div class="stat"><div class="stat-num" id="statChapters">—</div><div class="stat-label">Chapters</div></div>
    </div>

    <!-- Pre-assemble action -->
    <div id="assembleAction">
      <button class="btn-primary" id="assembleBtn" onclick="cb.runAssemble()">Assemble Book →</button>
    </div>

    <!-- Loading state -->
    <div id="assembleLoading" style="display:none; text-align:center; padding:48px 0;">
      <p class="loading-msg">Claude is reading all recordings… this may take 30–90 seconds.</p>
    </div>

    <!-- Output sections -->
    <div id="assembleOutput" style="display:none;">

      <div class="section-block">
        <div class="section-label">Book Bible</div>
        <p style="font-size:13px;color:var(--ink-muted);margin-bottom:8px">The organizing vision for the whole collection. Edit freely — your changes are saved automatically.</p>
        <textarea class="editable-area" id="bibleEditor" rows="10" placeholder="Book Bible will appear here after assembly…" onblur="cb.saveBible()"></textarea>
        <p class="save-notice" id="bibleSaveNotice"></p>
      </div>

      <div class="section-block">
        <div class="section-label">Chapter Outline</div>
        <p style="font-size:13px;color:var(--ink-muted);margin-bottom:8px">Suggested chapter structure. Edit or rearrange before proceeding. Your changes are saved automatically.</p>
        <textarea class="editable-area" id="outlineEditor" rows="12" placeholder="Chapter outline will appear here after assembly…" onblur="cb.saveOutline()"></textarea>
        <p class="save-notice" id="outlineSaveNotice"></p>
      </div>

      <div class="section-block">
        <div class="section-label">What's Missing</div>
        <div class="readonly-box" id="whatsMissingBox"></div>
      </div>

      <button class="btn-primary" onclick="cb.downloadBible()">Download Book Bible</button>
      <button class="btn-secondary" onclick="cb.proceedToEdit()">Proceed to editing →</button>
      <button class="btn-secondary" onclick="cb.runAssemble()">Reassemble with new stories</button>
    </div>

    <div id="assembleError" class="error-msg" style="display:none; margin-top:12px;"></div>
  </div>
</div>

<!-- ══════════════════════════════════════════════
     SCREEN: EDIT CHAPTERS
══════════════════════════════════════════════ -->
<div class="screen" id="screenEdit">
  <nav class="top-nav">
    <button class="link-btn" onclick="cb.showAssemble()">← Book Bible</button>
    <span class="wordmark">MyCogna · Collection Book Builder</span>
    <div style="display:flex;gap:10px;align-items:center;">
      <button class="btn-sm" onclick="cb.downloadManuscript()">Download full book</button>
    </div>
  </nav>
  <div class="page">
    <h2>Edit Chapters</h2>
    <p class="sub">Select a chapter to draft or refine it. Use Claude to generate a first pass or get editorial feedback.</p>

    <div class="edit-layout">
      <div class="edit-sidebar">
        <div class="section-label">Chapters</div>
        <button class="btn-sm" style="margin-bottom:12px;width:100%;" onclick="cb.addChapter()">+ Add chapter</button>
        <div id="editChapterList"><p class="loading-msg">Loading…</p></div>
      </div>
      <div class="edit-main" id="editMain">
        <p class="empty-state">Select a chapter from the list to begin editing.</p>
      </div>
    </div>
  </div>
</div>

<script>
  const API = window.location.origin + '/api/portal/collection';

  const cbState = {
    authToken: '',
    recordings: [],
    storytellerCount: 0,
    bookBibleId: null,
    bookBible: '',
    chapterOutline: '',
    whatsMissing: '',
    chapters: [],
    currentChapterId: null,
  };

  async function apiFetch(url, opts = {}) {
    opts.headers = { ...opts.headers, 'Authorization': 'Bearer ' + cbState.authToken };
    const res = await fetch(url, opts);
    if (!res.ok) {
      let detail = `Error ${res.status}`;
      try { const b = await res.json(); if (b.detail) detail = b.detail; } catch {}
      throw new Error(detail);
    }
    return res.json();
  }

  const cb = {

    showAssemble() {
      document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
      document.getElementById('screenAssemble').classList.add('active');
      window.scrollTo(0, 0);
    },

    showEdit() {
      document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
      document.getElementById('screenEdit').classList.add('active');
      window.scrollTo(0, 0);
    },

    updateStats() {
      document.getElementById('statStorytellers').textContent = cbState.storytellerCount;
      document.getElementById('statRecordings').textContent = cbState.recordings.length;
      document.getElementById('statChapters').textContent = cbState.chapters.length;
    },

    async runAssemble() {
      document.getElementById('assembleAction').style.display = 'none';
      document.getElementById('assembleOutput').style.display = 'none';
      document.getElementById('assembleLoading').style.display = '';
      document.getElementById('assembleError').style.display = 'none';
      try {
        const data = await apiFetch(`${API}/memoir/assemble`, { method: 'POST' });
        cbState.bookBibleId = data.book_bible_id;
        cbState.bookBible = data.book_bible || '';
        cbState.chapterOutline = data.chapter_outline || '';
        cbState.whatsMissing = data.whats_missing || '';
        cb.showAssembleOutput();
      } catch (err) {
        document.getElementById('assembleLoading').style.display = 'none';
        document.getElementById('assembleAction').style.display = '';
        document.getElementById('assembleError').textContent = err.message;
        document.getElementById('assembleError').style.display = '';
      }
    },

    showAssembleOutput() {
      document.getElementById('assembleLoading').style.display = 'none';
      document.getElementById('assembleAction').style.display = 'none';
      document.getElementById('bibleEditor').value = cbState.bookBible;
      document.getElementById('outlineEditor').value = cbState.chapterOutline;
      document.getElementById('whatsMissingBox').textContent = cbState.whatsMissing;
      document.getElementById('assembleOutput').style.display = '';
    },

    async saveBible() {
      const val = document.getElementById('bibleEditor').value;
      cbState.bookBible = val;
      const notice = document.getElementById('bibleSaveNotice');
      try {
        await apiFetch(`${API}/memoir/bible`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ book_bible: val }),
        });
        notice.textContent = 'Saved.';
        setTimeout(() => { notice.textContent = ''; }, 2000);
      } catch (err) {
        notice.textContent = 'Save failed: ' + err.message;
      }
    },

    async saveOutline() {
      const val = document.getElementById('outlineEditor').value;
      cbState.chapterOutline = val;
      const notice = document.getElementById('outlineSaveNotice');
      try {
        await apiFetch(`${API}/memoir/bible`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ chapter_outline: val }),
        });
        notice.textContent = 'Saved.';
        setTimeout(() => { notice.textContent = ''; }, 2000);
      } catch (err) {
        notice.textContent = 'Save failed: ' + err.message;
      }
    },

    downloadBible() {
      const content = `COLLECTION BOOK BIBLE\n${'='.repeat(50)}\n\n${cbState.bookBible}\n\nCHAPTER OUTLINE\n${'='.repeat(50)}\n\n${cbState.chapterOutline}\n\nWHAT'S MISSING\n${'='.repeat(50)}\n\n${cbState.whatsMissing}`;
      const blob = new Blob([content], { type: 'text/plain' });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
      a.download = 'collection-book-bible.txt'; a.click();
    },

    async proceedToEdit() {
      cb.showEdit();
      try {
        const data = await apiFetch(`${API}/memoir/chapters`);
        cbState.chapters = data.chapters || [];
        if (cbState.chapters.length === 0 && cbState.chapterOutline.trim()) {
          // Auto-populate from outline
          const populated = await apiFetch(`${API}/memoir/chapters/from-outline`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ outline_text: cbState.chapterOutline }),
          });
          cbState.chapters = populated.chapters || [];
          cb.updateStats();
        }
        cb._renderChapterSidebar(null);
        if (cbState.chapters.length > 0) cb.loadChapter(cbState.chapters[0].id);
      } catch (err) {
        document.getElementById('editMain').innerHTML = `<p class="error-msg">${err.message}</p>`;
      }
    },

    _renderChapterSidebar(activeId) {
      const list = document.getElementById('editChapterList');
      if (cbState.chapters.length === 0) {
        list.innerHTML = '<p style="font-size:13px;color:var(--ink-muted);">No chapters yet. Go back to the Book Bible and assemble first, or add a chapter manually.</p>';
        return;
      }
      list.innerHTML = cbState.chapters.map(c =>
        `<div class="chapter-item ${c.id === activeId ? 'active' : ''}" onclick="cb.loadChapter('${c.id}')" id="chap-item-${c.id}">
          <span class="chapter-title-text">${cb._esc(c.title)}</span>
        </div>`
      ).join('');
    },

    async addChapter() {
      const title = prompt('Chapter title:');
      if (!title || !title.trim()) return;
      try {
        const data = await apiFetch(`${API}/memoir/chapters`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: title.trim(), content: '', sort_order: cbState.chapters.length }),
        });
        cbState.chapters.push(data.chapter);
        cb._renderChapterSidebar(data.chapter.id);
        cb.loadChapter(data.chapter.id);
        cb.updateStats();
      } catch (err) {
        alert('Could not create chapter: ' + err.message);
      }
    },

    async loadChapter(chapterId) {
      cbState.currentChapterId = chapterId;
      document.querySelectorAll('.chapter-item').forEach(el => el.classList.remove('active'));
      const item = document.getElementById('chap-item-' + chapterId);
      if (item) item.classList.add('active');

      const chapter = cbState.chapters.find(c => c.id === chapterId);
      if (!chapter) return;

      document.getElementById('editMain').innerHTML = `
        <div>
          <div class="section-label">${cb._esc(chapter.title)}</div>
          <textarea class="chapter-editor" id="chapterEditor" placeholder="This chapter's content will appear here. Use 'Ask Claude for a first pass' to generate a draft, then edit freely.">${cb._esc(chapter.content || '')}</textarea>
          <div style="display:flex;gap:10px;margin-bottom:20px;flex-wrap:wrap;">
            <button class="btn-sm" onclick="cb.saveChapter()">Save</button>
            <button class="btn-sm" onclick="cb.downloadChapter()">Download chapter</button>
            <button class="btn-sm" onclick="cb.downloadManuscript()">Download full book</button>
          </div>
          <button class="btn-first-pass" id="firstPassBtn" onclick="cb.runFirstPass()">Ask Claude to write a first pass →</button>
          <div id="firstPassLoading" style="display:none;text-align:center;padding:16px 0;"><p class="loading-msg">Claude is drafting the chapter… this may take 30–60 seconds.</p></div>
          <hr class="divider" />
          <div class="section-label">Editorial feedback</div>
          <div class="chat-messages" id="editMessages"><p class="loading-msg">Ask Claude for feedback, or request a rewrite of any section.</p></div>
          <div class="chat-input-row" style="margin-top:12px;">
            <textarea id="editInput" placeholder="Ask Claude for feedback or a rewrite…" onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();cb.editSend();}"></textarea>
            <button class="chat-send-btn" id="editSendBtn" onclick="cb.editSend()">Send</button>
          </div>
          <div id="editError" class="error-msg" style="display:none;margin-top:8px;"></div>
        </div>`;

      // Load existing edit messages
      const msgs = chapter.edit_messages || [];
      if (msgs.length > 0) {
        const container = document.getElementById('editMessages');
        container.innerHTML = '';
        msgs.forEach(m => {
          const div = document.createElement('div');
          div.className = `chat-bubble ${m.role === 'user' ? 'user' : 'ai'}`;
          div.textContent = m.content;
          container.appendChild(div);
        });
      }
    },

    async saveChapter() {
      const chapter = cbState.chapters.find(c => c.id === cbState.currentChapterId);
      if (!chapter) return;
      const content = document.getElementById('chapterEditor').value;
      try {
        await apiFetch(`${API}/memoir/chapters/${cbState.currentChapterId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: chapter.title, content, sort_order: chapter.sort_order }),
        });
        chapter.content = content;
      } catch (err) {
        const errEl = document.getElementById('editError');
        if (errEl) { errEl.textContent = err.message; errEl.style.display = ''; }
      }
    },

    downloadChapter() {
      const chapter = cbState.chapters.find(c => c.id === cbState.currentChapterId);
      if (!chapter) return;
      const content = document.getElementById('chapterEditor')?.value || chapter.content || '';
      const blob = new Blob([`${chapter.title}\n${'='.repeat(50)}\n\n${content}`], { type: 'text/plain' });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
      a.download = `${chapter.title.toLowerCase().replace(/\s+/g, '-')}.txt`; a.click();
    },

    downloadManuscript() {
      const parts = cbState.chapters.map(c => `${c.title}\n${'='.repeat(50)}\n\n${c.content || ''}`);
      const blob = new Blob([parts.join('\n\n\n')], { type: 'text/plain' });
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
      a.download = 'collection-book.txt'; a.click();
    },

    async runFirstPass() {
      if (!cbState.currentChapterId) return;
      const btn = document.getElementById('firstPassBtn');
      const loading = document.getElementById('firstPassLoading');
      if (btn) btn.disabled = true;
      if (loading) loading.style.display = '';
      try {
        const data = await apiFetch(`${API}/memoir/chapters/${cbState.currentChapterId}/first-pass`, { method: 'POST' });
        const editor = document.getElementById('chapterEditor');
        if (editor) editor.value = data.content || '';
        const chapter = cbState.chapters.find(c => c.id === cbState.currentChapterId);
        if (chapter) chapter.content = data.content || '';
      } catch (err) {
        const errEl = document.getElementById('editError');
        if (errEl) { errEl.textContent = 'First pass failed: ' + err.message; errEl.style.display = ''; }
      } finally {
        if (btn) btn.disabled = false;
        if (loading) loading.style.display = 'none';
      }
    },

    _appendEditMessage(role, text) {
      const container = document.getElementById('editMessages');
      if (!container) return;
      const loading = container.querySelector('.loading-msg');
      if (loading) loading.remove();
      const div = document.createElement('div');
      div.className = `chat-bubble ${role}`;
      div.textContent = text;
      container.appendChild(div);
      container.scrollTop = container.scrollHeight;
    },

    async editSend() {
      const input = document.getElementById('editInput');
      if (!input) return;
      const text = input.value.trim();
      if (!text || !cbState.currentChapterId) return;
      input.value = '';
      const btn = document.getElementById('editSendBtn');
      if (btn) btn.disabled = true;
      cb._appendEditMessage('user', text);
      cb._appendEditMessage('ai', '…');
      try {
        const data = await apiFetch(`${API}/memoir/chapters/${cbState.currentChapterId}/edit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text }),
        });
        document.querySelectorAll('#editMessages .chat-bubble.ai').forEach((el, i, arr) => {
          if (i === arr.length - 1) el.textContent = data.message;
        });
      } catch (err) {
        const errEl = document.getElementById('editError');
        if (errEl) { errEl.textContent = err.message; errEl.style.display = ''; }
      } finally {
        if (btn) btn.disabled = false;
        if (input) input.focus();
      }
    },

    _esc(str) {
      return String(str || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    },
  };

  // ── Boot ──
  window.addEventListener('load', async () => {
    const token = localStorage.getItem('portalToken');
    if (!token) { window.location = '/portal'; return; }
    cbState.authToken = token;

    try {
      const data = await apiFetch(`${API}/data`);
      cbState.recordings = data.recordings || [];
      cbState.storytellerCount = data.storyteller_count || 0;
      cbState.chapters = data.chapters || [];

      // Restore previous Book Bible if one exists
      if (data.book_bible) {
        cbState.bookBibleId = data.book_bible.id;
        cbState.bookBible = data.book_bible.content || '';
        cbState.chapterOutline = data.book_bible.chapter_outline || '';
        cbState.whatsMissing = data.book_bible.whats_missing || '';
      }

      cb.updateStats();
      document.getElementById('assembleSub').textContent =
        `${cbState.recordings.length} recording${cbState.recordings.length !== 1 ? 's' : ''} from ${cbState.storytellerCount} storyteller${cbState.storytellerCount !== 1 ? 's' : ''} will be included. Claude will generate a Book Bible, chapter outline, and editorial notes.`;

      if (cbState.bookBible) {
        cb.showAssembleOutput();
      } else {
        document.getElementById('assembleAction').style.display = '';
      }

      // Show assemble screen on load
      cb.showAssemble();
    } catch (err) {
      document.body.innerHTML = `<div style="padding:40px;text-align:center;font-family:Georgia,serif;color:#C0392B;">
        <p>Error loading workspace: ${err.message}</p>
        <p style="margin-top:16px;"><a href="/portal" style="color:#B8860B;">← Back to portal</a></p>
      </div>`;
    }
  });
</script>
</body>
</html>
```

**Files affected:**
- `apps/cogna/static/portal-collection-book.html` (new file)

---

### Step 12: Update collection/data endpoint to return chapter_outline and whats_missing

The `/api/portal/collection/data` endpoint currently returns `book_bible` as an object with only `{id, content, assembled_at}`. Update it to also return `chapter_outline` and `whats_missing`.

**Actions:**
- In `portal_collection_data` (around line 3107), update the Supabase query to include the new columns:
  ```python
  bb_r = supabase.table("collection_book_bibles").select("id, content, chapter_outline, whats_missing, assembled_at").eq("portal_user_id", portal_id).order("assembled_at", desc=True).limit(1).execute()
  ```
- The local DB fallback already passes through the full bible dict, so no change needed there.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 13: Commit, push, and run Supabase migration

**Actions:**
- Run the Supabase migration in the SQL editor:
  ```sql
  ALTER TABLE collection_book_bibles ADD COLUMN IF NOT EXISTS chapter_outline TEXT;
  ALTER TABLE collection_book_bibles ADD COLUMN IF NOT EXISTS whats_missing TEXT;
  ```
  (And also the initial table creation if not yet run:)
  ```sql
  CREATE TABLE IF NOT EXISTS collection_book_bibles (
    id              TEXT PRIMARY KEY,
    portal_user_id  TEXT NOT NULL,
    content         TEXT,
    assembled_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  CREATE TABLE IF NOT EXISTS collection_chapters (
    id                        TEXT PRIMARY KEY,
    portal_user_id            TEXT NOT NULL,
    collection_book_bible_id  TEXT,
    title                     TEXT,
    content                   TEXT,
    edit_messages             JSONB NOT NULL DEFAULT '[]',
    sort_order                INTEGER NOT NULL DEFAULT 0,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
  );
  ```
- `git add` all changed files and commit with a descriptive message
- `git push` — Railway and Vercel auto-deploy

**Files affected:**
- All modified files

---

## Connections & Dependencies

### Files That Reference This Area

- `apps/cogna/static/portal.html` — the `<a>` tag in the F-tier tab bar points to this new page
- `apps/cogna/server.py` — all collection API endpoints and the new page route
- `apps/cogna/supabase_schema.sql` — schema source of truth for the two collection tables

### Updates Needed for Consistency

- `CLAUDE.md` — update the portal tiers section to note that `/portal/collection-book` is the F-tier book workspace URL
- The old `IS_COLLECTION` references in `portal-memoir.html` can be left in place for now (they are no longer reachable via navigation) and cleaned up in a future pass

### Impact on Existing Workflows

- The broken `/portal/memoir?type=collection` flow is replaced; nothing else in the codebase links to it
- Individual memoir flow (`/portal/memoir?id=...`) is completely untouched

---

## Validation Checklist

- [ ] Clicking "Compile into Book" tab navigates to `/portal/collection-book` without redirect
- [ ] Page loads and shows correct stats (storyteller count, recording count)
- [ ] "Assemble Book →" button triggers Claude and returns all three sections
- [ ] Book Bible textarea is populated and saves on blur
- [ ] Chapter Outline textarea is populated and saves on blur
- [ ] "What's Missing" is shown as read-only text
- [ ] "Download Book Bible" downloads a .txt file with all three sections
- [ ] "Proceed to editing →" auto-populates chapters from the outline on first visit
- [ ] Subsequent visits to Edit screen show existing chapters without duplication
- [ ] Selecting a chapter loads it in the editor
- [ ] "Ask Claude to write a first pass →" generates and inserts draft content
- [ ] Chapter save works
- [ ] Download chapter and Download full book work
- [ ] Chat interface ("Editorial feedback") sends messages and gets responses
- [ ] Reassemble with new stories re-runs Claude and refreshes all three sections
- [ ] Supabase migration has been run (collection_book_bibles, collection_chapters, new columns)

---

## Success Criteria

The implementation is complete when:

1. An F-tier portal user can click "Compile into Book," reach the workspace, and assemble a Book Bible + Chapter Outline + What's Missing from their storytellers' recordings in one click
2. The user can edit the Book Bible and Chapter Outline inline and see "Saved." confirm
3. The user can proceed to the Edit screen, select any chapter, and either ask Claude for a first-pass draft or send editorial chat messages — and receive coherent responses that reference the Book Bible and other chapters

---

## Notes

- The `_build_collection_edit_system` function doesn't feed individual recordings into the chat context (that would be very expensive per turn). If richer per-chapter chat context is needed later, add a `recordings_context` summary field to collection_chapters.
- The "from-outline" parser handles both `**Bold**` and plain-text numbered list formats. If Claude's outline format shifts, the regex may need updating.
- The `portal-memoir.html` IS_COLLECTION branching is left in place but is now unreachable via navigation. It should be cleaned up in a future pass to reduce confusion.
- If a user reassembles after already having chapters in the edit screen, the chapters are NOT automatically wiped — they keep their existing content. The user would need to delete and re-create chapters manually if they want a fresh start from the new outline.
