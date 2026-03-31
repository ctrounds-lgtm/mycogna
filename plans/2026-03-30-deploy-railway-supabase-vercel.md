# Plan: Deploy MyCogna — Railway + Supabase + Vercel

**Created:** 2026-03-30
**Status:** Implemented
**Request:** Deploy the MyCogna app to production using Railway (FastAPI backend), Supabase (PostgreSQL database + file storage), and Vercel (static frontend).

---

## Overview

### What This Plan Accomplishes

Moves MyCogna from a local-only app (flat JSON database, local file uploads) to a fully hosted production system. The FastAPI backend runs on Railway, the database and file storage live in Supabase, and the static frontend is served globally via Vercel. Vercel proxies all `/api/*` calls to Railway so the frontend needs no hardcoded URLs.

### Why This Matters

Right now the app only runs on Christy's Mac. This deployment lets Christopher (and future users) reach it from any device, anytime — which is the whole point of MyCogna. The three-service stack costs under $20/month at early scale, requires no DevOps expertise to maintain, and each service scales independently if the app grows.

---

## Current State

### Relevant Existing Structure

| File / Path | Role |
|---|---|
| `apps/cogna/server.py` | FastAPI backend — all API logic, reads/writes `family_portal.json` |
| `apps/cogna/static/` | Frontend — `index.html` (child app), `portal.html` + `portal.js` (guardian portal), CSS |
| `apps/cogna/data/family_portal.json` | Flat JSON "database" — users, cognas |
| `apps/cogna/data/family_uploads/` | Voice samples and photos uploaded by guardians |
| `apps/cogna/data/cogna_cache/` | Cached TTS audio files (ephemeral OK) |
| `apps/cogna/data/sessions/` | Saved conversation transcripts (per cogna) |
| `apps/cogna/requirements.txt` | Python dependencies |
| `apps/cogna/config.json` | App config (API key env var name, voice defaults) |
| `apps/cogna/.env` | Local API keys (never committed) |

### Gaps or Problems Being Addressed

- **No production hosting** — app only runs locally on one Mac
- **Fragile data storage** — a single JSON file; no backup, no concurrent access safety
- **Local-only file uploads** — voice samples and photos stored on Christy's hard drive
- **Session state lost on restart** — in-memory `SESSIONS` dict (acceptable for v1)
- **Audio cache is local** — TTS cache works locally but won't persist on Railway (acceptable — cache is optional optimization; EVI handles the primary audio path)

---

## Proposed Changes

### Summary of Changes

- Add `supabase-py` to `requirements.txt`
- Create Supabase schema SQL file (run once in Supabase dashboard)
- Rewrite `server.py` database helpers to use Supabase instead of JSON file I/O
- Rewrite `server.py` file upload helpers to use Supabase Storage (returns CDN URLs)
- Remove the `serve_upload` FastAPI route (files served directly from Supabase CDN)
- Update `portal.js` photo display: `src="/${cogna.photo}"` → `src="${cogna.photo}"`
- Change audio cache directory to `/tmp/cogna_cache` (Railway has ephemeral local storage)
- Create `apps/cogna/railway.toml` — Railway deployment config
- Create `apps/cogna/Procfile` — fallback start command
- Create `apps/cogna/vercel.json` — static frontend config + API proxy rewrites
- Update `.gitignore` to exclude `apps/cogna/data/`
- Write a one-time data migration script `apps/cogna/scripts/migrate_to_supabase.py`
- Update `CLAUDE.md` to document the production URLs and deployment workflow

### New Files to Create

| File Path | Purpose |
|---|---|
| `apps/cogna/supabase_schema.sql` | SQL to run once in Supabase SQL editor — creates all tables and storage bucket |
| `apps/cogna/railway.toml` | Railway deployment config — start command, health check |
| `apps/cogna/Procfile` | Fallback start command for Railway |
| `apps/cogna/vercel.json` | Vercel config — marks static/ as root, proxies /api/* to Railway |
| `apps/cogna/scripts/migrate_to_supabase.py` | One-time script to migrate family_portal.json + local uploads → Supabase |

### Files to Modify

| File Path | Changes |
|---|---|
| `apps/cogna/server.py` | Replace JSON file I/O with Supabase client; replace local upload with Supabase Storage; update cache dir to /tmp |
| `apps/cogna/requirements.txt` | Add `supabase` package |
| `apps/cogna/static/portal.js` | Fix photo `src` to use full URL (not `/${path}`) |
| `.gitignore` | Exclude `apps/cogna/data/` from git |

### Files to Delete (if any)

None deleted — `data/family_portal.json` and `data/family_uploads/` remain locally as backup; they just stop being the source of truth after migration.

---

## Design Decisions

### Key Decisions Made

1. **Vercel proxy for API calls**: `vercel.json` rewrites `/api/*` to Railway, so the frontend never needs a hardcoded Railway URL. The Vercel env var `RAILWAY_BACKEND_URL` stores the Railway URL and is injected into `vercel.json` rewrites at deploy time.

2. **Drop `cogna_ids` array from users**: Instead of maintaining a `cogna_ids: []` array on the user, query `SELECT * FROM cognas WHERE owner_email = ?`. Cleaner SQL, same result — eliminates a dual-write problem.

3. **In-memory sessions stay in-memory (v1)**: `SESSIONS` dict remains. Railway keeps the process alive; users are only logged out on redeploy. Acceptable for early-stage. Migrate to a `auth_tokens` Supabase table in v2 if needed.

4. **Supabase Storage for uploads**: Voice samples and photos upload directly to a `cogna-uploads` bucket and the returned public CDN URL is stored in the DB. The FastAPI `serve_upload` route is removed — Supabase CDN handles it.

5. **Ephemeral audio cache on Railway**: `CACHE_DIR` changes to `/tmp/cogna_cache`. Cache is lost on restart, but EVI handles primary audio so the cache is only used for voice test playback in the guardian portal — fast enough to regenerate.

6. **`config.json` committed without secrets**: `config.json` contains no API keys. It stays committed. API keys remain in `.env` (local) and Railway/Vercel environment variable settings.

7. **Data migration is a one-time script, not automatic**: Run `migrate_to_supabase.py` once after Supabase is set up to port the existing account and cogna data. After that, the local JSON is a read-only backup.

### Alternatives Considered

- **Fly.io instead of Railway**: Similar capability, slightly more complex CLI setup for a non-DevOps user. Railway's GitHub auto-deploy is simpler.
- **Supabase Auth instead of custom auth**: Would eliminate password hashing code, but requires rewriting the existing session model. Too much churn for v1; current auth works fine.
- **Single-service on Railway** (backend serves static files): Simpler, but Vercel's global CDN gives faster load times for the child app and portal. Worth the split.
- **Store sessions in Supabase from day one**: Adds one table and a few lines of code. Deferred to v2 — Railway uptime is high enough that in-memory is fine early on.

### Open Questions

1. **Custom domain?** Does Christy want `mycogna.com` or similar? If yes, add DNS steps after Railway + Vercel are live. Not blocking for initial deployment.
2. **Supabase Storage public vs. signed URLs?** Using public URLs (simplest). If photos/audio need to be private in the future, switch to signed URLs — requires a server-side proxy.

---

## Step-by-Step Tasks

### Step 1: Update `.gitignore`

Add `apps/cogna/data/` so the local JSON database, uploads, and audio cache are never accidentally committed to git (they contain real user data).

**Actions:**
- Append `apps/cogna/data/` to the root `.gitignore`

**Files affected:**
- `.gitignore`

---

### Step 2: Add `supabase` to requirements

**Actions:**
- Add `supabase` on a new line in `requirements.txt`

**Files affected:**
- `apps/cogna/requirements.txt`

---

### Step 3: Create Supabase schema SQL file

Create `apps/cogna/supabase_schema.sql` — this file is run **once** in the Supabase SQL editor to create all tables and configure storage. It is safe to commit (no secrets).

**Full content of `apps/cogna/supabase_schema.sql`:**

```sql
-- MyCogna schema
-- Run once in Supabase SQL editor: https://app.supabase.com → SQL editor

-- Users
CREATE TABLE IF NOT EXISTS users (
  email            TEXT PRIMARY KEY,
  name             TEXT NOT NULL,
  password_salt    TEXT NOT NULL,
  password_hash    TEXT NOT NULL,
  setup_type       TEXT NOT NULL DEFAULT 'guardian',
  child_access_code TEXT NOT NULL UNIQUE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Cognas
CREATE TABLE IF NOT EXISTS cognas (
  id                  TEXT PRIMARY KEY,
  owner_email         TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
  name                TEXT NOT NULL,
  relationship        TEXT NOT NULL DEFAULT '',
  term_of_endearment  TEXT NOT NULL DEFAULT '',
  params              JSONB NOT NULL DEFAULT '{"warmth":50,"validation":50,"tone":50,"structure":50,"stance":50}',
  voice_backend       TEXT NOT NULL DEFAULT 'tts',
  elevenlabs_voice_id TEXT,
  hume_voice_id       TEXT,
  voice_sample        TEXT,
  photo               TEXT,
  hume_consent        JSONB,
  last_tested_at      TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cognas_owner_email_idx ON cognas(owner_email);

-- Conversation sessions
CREATE TABLE IF NOT EXISTS conversation_sessions (
  id                TEXT PRIMARY KEY,
  primary_cogna_id  TEXT NOT NULL,
  cogna_ids         TEXT[] NOT NULL,
  voice_names       TEXT[] NOT NULL,
  transcript        JSONB NOT NULL DEFAULT '[]',
  duration_seconds  INT NOT NULL DEFAULT 0,
  saved_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sessions_primary_cogna_idx ON conversation_sessions(primary_cogna_id);

-- Storage bucket for voice samples and photos
-- Run this AFTER creating the bucket manually in Supabase Storage UI
-- Bucket name: cogna-uploads   Type: Public
-- Then set this policy to allow server-side uploads:
INSERT INTO storage.buckets (id, name, public) VALUES ('cogna-uploads', 'cogna-uploads', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Allow authenticated uploads"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'cogna-uploads');

CREATE POLICY "Allow public reads"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'cogna-uploads');
```

**Files affected:**
- `apps/cogna/supabase_schema.sql` (new)

---

### Step 4: Update `server.py` — Supabase initialization

Add Supabase client initialization near the top of `server.py`, alongside the existing Anthropic client setup.

**Actions:**

After the existing `HUME_SECRET_KEY` and `HUME_CONFIG_ID` lines (around line 86), add:

```python
# Supabase setup
from supabase import create_client, Client as SupabaseClient

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")  # service_role key (not anon)

if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
else:
    supabase = None
```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 5: Update `server.py` — replace DB helper functions

Replace `_load_db()` and `_save_db()` with individual Supabase helper functions. Add these to the Helpers section at the bottom of `server.py`:

```python
# ── Supabase DB helpers ──────────────────────────────────────────────────────

def _sb_get_user(email: str):
    r = supabase.table("users").select("*").eq("email", email).maybe_single().execute()
    return r.data

def _sb_create_user(user: dict):
    supabase.table("users").insert(user).execute()

def _sb_get_cogna(cogna_id: str):
    r = supabase.table("cognas").select("*").eq("id", cogna_id).maybe_single().execute()
    return r.data

def _sb_list_cognas(owner_email: str) -> list:
    r = supabase.table("cognas").select("*").eq("owner_email", owner_email).order("created_at").execute()
    return r.data or []

def _sb_create_cogna(cogna: dict):
    supabase.table("cognas").insert(cogna).execute()

def _sb_update_cogna(cogna_id: str, updates: dict):
    supabase.table("cognas").update(updates).eq("id", cogna_id).execute()

def _sb_delete_cogna(cogna_id: str):
    supabase.table("cognas").delete().eq("id", cogna_id).execute()

def _sb_find_user_by_code(code: str):
    r = supabase.table("users").select("*").eq("child_access_code", code).maybe_single().execute()
    return r.data

def _sb_save_session(session_id: str, primary_cogna_id: str, cogna_ids: list,
                      voice_names: list, transcript: list, duration_seconds: int):
    supabase.table("conversation_sessions").insert({
        "id": session_id,
        "primary_cogna_id": primary_cogna_id,
        "cogna_ids": cogna_ids,
        "voice_names": voice_names,
        "transcript": transcript,
        "duration_seconds": duration_seconds,
    }).execute()

def _sb_list_sessions(primary_cogna_id: str) -> list:
    r = (supabase.table("conversation_sessions")
         .select("id, saved_at, voice_names, duration_seconds, transcript")
         .eq("primary_cogna_id", primary_cogna_id)
         .order("saved_at", desc=True)
         .limit(20)
         .execute())
    return r.data or []
```

Keep `_load_db()` and `_save_db()` as **fallback stubs** so the app can still run locally without Supabase during development:

```python
def _load_db() -> Dict[str, Any]:
    """Local fallback — only used when SUPABASE_URL is not set."""
    if not PORTAL_DB_PATH.exists():
        db = {"users": {}, "cognas": {}, "created_at": _utc_now()}
        _save_db(db)
        return db
    with open(PORTAL_DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    db.setdefault("users", {})
    db.setdefault("cognas", {})
    return db

def _save_db(db: Dict[str, Any]):
    """Local fallback — only used when SUPABASE_URL is not set."""
    with open(PORTAL_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)
```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 6: Update `server.py` — rewrite all API endpoints to use Supabase

Each endpoint currently calls `_load_db()` / `_save_db()`. Replace with the Supabase helpers. The logic structure stays the same — only the data access layer changes.

**Pattern for each endpoint:**

| Endpoint | Old pattern | New pattern |
|---|---|---|
| `auth_register` | `db["users"][email] = {...}; _save_db(db)` | `_sb_create_user({...})` |
| `auth_login` | `db["users"].get(email)` | `_sb_get_user(email)` |
| `auth_me` | via `_auth_user()` → `db["users"].get(email)` | `_sb_get_user(email)` |
| `list_cognas` | load user's `cogna_ids`, fetch each | `_sb_list_cognas(user["email"])` |
| `create_cogna` | `db["cognas"][id] = {...}; user["cogna_ids"].append(id)` | `_sb_create_cogna({...})` (no cogna_ids array needed) |
| `get_cogna_detail` | `db["cognas"].get(cogna_id)` | `_sb_get_cogna(cogna_id)` |
| `update_cogna` | mutate dict, `_save_db()` | `_sb_update_cogna(cogna_id, {...})` |
| `delete_cogna` | `del db["cognas"][cogna_id]` | `_sb_delete_cogna(cogna_id)` |
| `record_hume_consent` | mutate cogna dict | `_sb_update_cogna(cogna_id, {"hume_consent": {...}})` |
| `upload_cogna_sample` | save file locally | upload to Supabase Storage, `_sb_update_cogna(...)` |
| `upload_cogna_photo` | save file locally | upload to Supabase Storage, `_sb_update_cogna(...)` |
| `test_cogna_voice` | `_load_db()` then `_save_db()` | `_sb_get_cogna()` then `_sb_update_cogna()` |
| `child_access` | loop users by access code | `_sb_find_user_by_code(code)` → `_sb_list_cognas(email)` |
| `evi_session` | `db["cognas"].get(cogna_id)` | `_sb_get_cogna(cogna_id)` |
| `converse` | `db["cognas"].get(cid)` for each | `_sb_get_cogna(cid)` for each |
| `save_session` | write JSON file to `data/sessions/` | `_sb_save_session(...)` |
| `list_sessions` | read JSON files from `data/sessions/` | `_sb_list_sessions(cogna_id)` |
| `respond` (legacy) | `db["cognas"].get(cogna_id)` | `_sb_get_cogna(cogna_id)` |

Also update `_auth_user()` to use `_sb_get_user()`:

```python
def _auth_user(authorization: Optional[str]) -> Any:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    email = SESSIONS.get(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = _sb_get_user(email)
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user  # returns the user dict directly (no db dict needed)
```

And update `_get_cogna()`:

```python
def _get_cogna(cogna_id: str) -> Dict[str, Any]:
    cogna = _sb_get_cogna(cogna_id)
    if not cogna:
        raise HTTPException(status_code=404, detail="Cogna not found")
    return cogna
```

Note: `_get_cogna` signature drops the `db` parameter since it no longer needs it. Update all callers.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 7: Update `server.py` — Supabase Storage for file uploads

Replace `_save_cogna_upload()` with a version that uploads to Supabase Storage and returns a public CDN URL.

**New `_save_cogna_upload`:**

```python
def _save_cogna_upload(cogna_id: str, kind: str, file: UploadFile) -> str:
    """Upload voice sample or photo to Supabase Storage. Returns public CDN URL."""
    ext = Path(file.filename or "upload.bin").suffix.lower()
    filename = f"{kind}-{int(datetime.now().timestamp())}{ext}"
    storage_path = f"{cogna_id}/{filename}"

    content = file.file.read()
    mime = {
        ".mp3": "audio/mpeg", ".wav": "audio/wav", ".m4a": "audio/mp4",
        ".webm": "audio/webm", ".mp4": "audio/mp4",
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
    }.get(ext, "application/octet-stream")

    supabase.storage.from_("cogna-uploads").upload(
        path=storage_path,
        file=content,
        file_options={"content-type": mime, "upsert": "true"},
    )

    public_url = supabase.storage.from_("cogna-uploads").get_public_url(storage_path)
    return public_url
```

Remove the `serve_upload` FastAPI route — it's no longer needed since Supabase CDN serves files directly.

Update audio cache directory to use `/tmp`:

```python
import tempfile
CACHE_DIR = Path(os.getenv("CACHE_DIR", tempfile.gettempdir())) / "cogna_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 8: Update `portal.js` — fix photo `src` attribute

Currently photos are displayed as `src="/${cogna.photo}"` which assumes a local path. With Supabase Storage the `photo` field is a full URL.

**Change in `portal.js` (around line 153):**

```javascript
// Before:
preview.innerHTML = `<img src="/${cogna.photo}" alt="Photo">`;

// After:
preview.innerHTML = `<img src="${cogna.photo}" alt="Photo">`;
```

**Files affected:**
- `apps/cogna/static/portal.js`

---

### Step 9: Create Railway config files

**`apps/cogna/railway.toml`:**

```toml
[build]
builder = "nixpacks"

[deploy]
startCommand = "uvicorn server:app --host 0.0.0.0 --port $PORT"
healthcheckPath = "/api/health"
healthcheckTimeout = 30
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

**`apps/cogna/Procfile`** (fallback):

```
web: uvicorn server:app --host 0.0.0.0 --port $PORT
```

**Files affected:**
- `apps/cogna/railway.toml` (new)
- `apps/cogna/Procfile` (new)

---

### Step 10: Create Vercel config

Vercel serves the `static/` directory as the frontend root and proxies all `/api/*` requests to Railway.

**`apps/cogna/vercel.json`:**

```json
{
  "version": 2,
  "rewrites": [
    {
      "source": "/api/(.*)",
      "destination": "REPLACE_WITH_RAILWAY_URL/api/$1"
    }
  ],
  "routes": [
    { "src": "/static/(.*)", "dest": "/static/$1" },
    { "src": "/portal", "dest": "/static/portal.html" },
    { "src": "/", "dest": "/static/index.html" }
  ]
}
```

**Note:** Replace `REPLACE_WITH_RAILWAY_URL` with the actual Railway URL (e.g. `https://mycogna-production.up.railway.app`) after Railway is deployed in the next section.

**Files affected:**
- `apps/cogna/vercel.json` (new)

---

### Step 11: Write the data migration script

Creates `apps/cogna/scripts/migrate_to_supabase.py` — run once locally to port existing data.

```python
#!/usr/bin/env python3
"""
One-time migration: family_portal.json + local uploads → Supabase.

Usage:
  SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python3 migrate_to_supabase.py

Run from the apps/cogna/ directory.
"""
import json
import os
import sys
from pathlib import Path
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "family_portal.json"
UPLOADS_DIR = ROOT / "data" / "family_uploads"

url = os.environ["SUPABASE_URL"]
key = os.environ["SUPABASE_SERVICE_KEY"]
sb = create_client(url, key)

with open(DB_PATH) as f:
    db = json.load(f)

# Migrate users
for email, user in db["users"].items():
    row = {k: user[k] for k in
           ("email","name","password_salt","password_hash","setup_type","child_access_code","created_at")}
    try:
        sb.table("users").insert(row).execute()
        print(f"  user: {email}")
    except Exception as e:
        print(f"  SKIP user {email}: {e}")

# Migrate cognas + upload files
for cogna_id, cogna in db["cognas"].items():
    row = {k: cogna.get(k) for k in
           ("id","owner_email","name","relationship","term_of_endearment","params",
            "voice_backend","elevenlabs_voice_id","hume_voice_id",
            "hume_consent","last_tested_at","created_at")}

    # Upload voice sample if present
    voice_path = None
    if cogna.get("voice_sample"):
        local = ROOT / cogna["voice_sample"]
        if local.exists():
            storage_path = f"{cogna_id}/{local.name}"
            with open(local, "rb") as fh:
                sb.storage.from_("cogna-uploads").upload(storage_path, fh.read(),
                    {"content-type": "audio/mp4", "upsert": "true"})
            voice_path = sb.storage.from_("cogna-uploads").get_public_url(storage_path)
            print(f"  voice uploaded: {storage_path}")

    # Upload photo if present
    photo_path = None
    if cogna.get("photo"):
        local = ROOT / cogna["photo"]
        if local.exists():
            storage_path = f"{cogna_id}/{local.name}"
            with open(local, "rb") as fh:
                sb.storage.from_("cogna-uploads").upload(storage_path, fh.read(),
                    {"content-type": "image/jpeg", "upsert": "true"})
            photo_path = sb.storage.from_("cogna-uploads").get_public_url(storage_path)
            print(f"  photo uploaded: {storage_path}")

    row["voice_sample"] = voice_path
    row["photo"] = photo_path

    try:
        sb.table("cognas").insert(row).execute()
        print(f"  cogna: {cogna_id} ({cogna['name']})")
    except Exception as e:
        print(f"  SKIP cogna {cogna_id}: {e}")

print("\nMigration complete.")
```

**Files affected:**
- `apps/cogna/scripts/migrate_to_supabase.py` (new)

---

### Step 12: Update `.gitignore`

**Actions:**
- Append to root `.gitignore`:

```
# MyCogna local data (real user data — never commit)
apps/cogna/data/
```

**Files affected:**
- `.gitignore`

---

### Step 13: Account setup and deployment (manual steps — Christy does these)

These require clicking through web dashboards. Do them in order.

#### 13a — Supabase

1. Go to [supabase.com](https://supabase.com) → Create new project → name it `mycogna`
2. Once provisioned: **SQL Editor** → paste contents of `supabase_schema.sql` → Run
3. Go to **Storage** → verify `cogna-uploads` bucket was created → set to **Public**
4. Go to **Settings → API** → copy:
   - `Project URL` → this is `SUPABASE_URL`
   - `service_role` secret key → this is `SUPABASE_SERVICE_KEY`
5. Add both to `apps/cogna/.env` for local testing

#### 13b — Run the migration

```bash
cd apps/cogna
SUPABASE_URL=your-url SUPABASE_SERVICE_KEY=your-key python3 scripts/migrate_to_supabase.py
```

Verify in Supabase Table Editor that users, cognas, and uploads are present.

#### 13c — Railway

1. Push this repo to GitHub (if not already there)
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub → select this repo
3. Set **Root Directory** to `apps/cogna`
4. Add environment variables in Railway dashboard:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `CLAUDE_API_KEY`
   - `HUME_API_KEY`
   - `HUME_SECRET_KEY`
   - `OPENAI_API_KEY`
   - `ELEVENLABS_API_KEY` (if used)
5. Railway will detect `railway.toml` and start the server
6. Copy the Railway-provided URL (e.g. `https://mycogna-production.up.railway.app`)

#### 13d — Update `vercel.json` with Railway URL

In `apps/cogna/vercel.json`, replace `REPLACE_WITH_RAILWAY_URL` with the actual Railway URL from step 13c.

Commit and push this change.

#### 13e — Vercel

1. Go to [vercel.com](https://vercel.com) → New Project → Import from GitHub → select this repo
2. Set **Root Directory** to `apps/cogna`
3. Set **Output Directory** to `static`
4. No build command needed (pure static)
5. Deploy → copy the Vercel URL

#### 13f — Test end-to-end

- Open the Vercel URL → enter access code `COGNA-ZN9P` → select Mom → Start Conversation
- Verify EVI connects and responds with Mom's voice
- Open `/portal` → log in as `ctrounds@gmail.com` → verify cogna is visible

---

### Step 14: Connect mycogna.org custom domain (manual steps)

`mycogna.org` is registered on GoDaddy. Only Vercel needs the custom domain — Railway stays on its internal `.railway.app` URL since Vercel proxies all API calls.

#### 14a — Add domain in Vercel

1. In your Vercel project → **Settings → Domains**
2. Add `mycogna.org` and `www.mycogna.org`
3. Vercel will show you two DNS records to add:
   - **Root domain (`mycogna.org`)**: An `A` record pointing to `76.76.21.21`
   - **www subdomain**: A `CNAME` record pointing to `cname.vercel-dns.com`

#### 14b — Add DNS records in GoDaddy

1. Log in to GoDaddy → **My Products** → find `mycogna.org` → **DNS**
2. Add/edit these records:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `@` | `76.76.21.21` | 600 |
| CNAME | `www` | `cname.vercel-dns.com` | 600 |

3. Save. DNS propagation typically takes 5–30 minutes.

#### 14c — Verify in Vercel

Back in Vercel → **Settings → Domains** → both `mycogna.org` and `www.mycogna.org` should show a green checkmark within ~30 minutes.

#### 14d — Update `vercel.json` to redirect www → root (optional but recommended)

Vercel handles this automatically when you add both domains — it redirects `www.mycogna.org` → `mycogna.org` by default.

**Note:** Railway keeps its auto-generated URL (e.g. `mycogna-production.up.railway.app`). The frontend never exposes this URL to users since all API calls are proxied through Vercel.

---

### Step 15: Update `CLAUDE.md`

Add a production deployment section to CLAUDE.md under MyCogna App:

```markdown
**Production URLs:**
- Child app: https://mycogna.org
- Guardian portal: https://mycogna.org/portal
- Backend API: [Railway URL] (internal — proxied through Vercel, not user-facing)

**Deploy process:**
- Backend: Railway auto-deploys from GitHub `apps/cogna/` on push to main
- Frontend: Vercel auto-deploys from GitHub `apps/cogna/static/` on push to main
- Database: Supabase (no deploy needed — always live)
- Domain: mycogna.org → Vercel (A record + CNAME in GoDaddy DNS)
```

**Files affected:**
- `CLAUDE.md`

---

## Connections & Dependencies

### Files That Reference This Area

- `CLAUDE.md` — documents the app location, start command, and URLs
- `apps/cogna/.env` — must add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`

### Updates Needed for Consistency

- After Railway deploys, update `vercel.json` with the actual Railway URL (Step 13d)
- After Vercel deploys, update `CLAUDE.md` with both production URLs (Step 14)

### Impact on Existing Workflows

- **Local development still works**: when `SUPABASE_URL` is not set, `server.py` should fall back to `_load_db()` / `_save_db()`. This fallback is preserved in Step 5.
- **EVI flow is unchanged**: the WebSocket connection and audio pipeline in `index.html` are not modified
- **Crisis detection is unchanged**: both the server-side keyword check and the client-side overlay are untouched

---

## Validation Checklist

- [ ] `supabase` added to `requirements.txt`
- [ ] `supabase_schema.sql` runs without errors in Supabase SQL editor
- [ ] `cogna-uploads` storage bucket created and set to Public
- [ ] Migration script runs and data appears in Supabase tables
- [ ] `railway.toml` detected by Railway; server starts successfully (`/api/health` returns 200)
- [ ] All Railway environment variables set
- [ ] `vercel.json` updated with real Railway URL
- [ ] Vercel deployment serves `index.html` at root
- [ ] `/api/health` works through Vercel proxy (returns `{"status":"ok"}`)
- [ ] Child app: access code `COGNA-ZN9P` loads Mom cogna
- [ ] EVI conversation connects and plays audio
- [ ] Guardian portal: login works, cogna visible, photo loads from Supabase CDN
- [ ] Voice upload in portal stores to Supabase Storage (not local disk)
- [ ] `apps/cogna/data/` does not appear in `git status`
- [ ] `mycogna.org` A record and `www` CNAME added in GoDaddy DNS
- [ ] Vercel shows green checkmark for `mycogna.org` and `www.mycogna.org`
- [ ] `https://mycogna.org` loads the child app
- [ ] `CLAUDE.md` updated with production URLs

---

## Success Criteria

1. A user on any device can reach `https://mycogna.org`, enter access code `COGNA-ZN9P`, and have a real-time voice conversation with Mom via Hume EVI.
2. A guardian can log into the portal at the Vercel URL, create or update a Cogna, upload a photo and voice sample, and see changes persist across browser sessions (data in Supabase, not local JSON).
3. The local development server (`uvicorn server:app`) still works on Christy's Mac using the local `.env` and Supabase credentials — no separate local DB required.

---

## Notes

- **Cost estimate**: Supabase free tier (up to 500MB DB, 1GB storage), Railway Hobby ($5/month), Vercel free tier. Total: ~$5/month to start, scales to ~$20/month with moderate usage.
- **v2 improvements to consider**: Move sessions from in-memory to Supabase `auth_tokens` table (survives restarts), add Supabase Row Level Security (RLS) for multi-tenant safety, add signed URLs for private voice files.
- **`config.json`** on Railway: The server reads `config.json` from disk. Since Railway pulls from git, commit `config.json` as-is (no secrets in it). If config needs to differ per environment, move values to env vars later.
- **WebSocket note**: EVI WebSocket connections go browser → Hume directly. They bypass both Railway and Vercel. The Vercel proxy only handles REST calls. This is by design and requires no changes.

---

## Implementation Notes

**Implemented:** 2026-03-30

### Summary

- Updated `.gitignore` to exclude `apps/cogna/data/`
- Added `supabase` to `requirements.txt`
- Created `apps/cogna/supabase_schema.sql` with full DB + storage schema
- Rewrote `apps/cogna/server.py`: Supabase data layer with local JSON fallback, Supabase Storage for uploads, `/tmp` audio cache, removed `serve_upload` route, updated all endpoints
- Fixed photo `src` in `apps/cogna/static/portal.js`
- Created `apps/cogna/railway.toml` and `apps/cogna/Procfile`
- Created `apps/cogna/vercel.json` (Railway URL placeholder still needs replacing after Railway deploy)
- Created `apps/cogna/scripts/migrate_to_supabase.py`
- Updated `CLAUDE.md` with production URLs and deploy process

### Deviations from Plan

- `serve_upload` FastAPI route removed (was `GET /data/family_uploads/{path}`). Files now served directly from Supabase CDN. Local fallback still writes to disk; audio remains served via `/audio/{filename}`.
- Data access functions renamed from `_sb_*` helpers + separate `_load_db` calls to unified `_get_user`, `_get_cogna`, etc. functions that internally branch on whether `supabase` client is available. Cleaner interface.

### Issues Encountered

None.
