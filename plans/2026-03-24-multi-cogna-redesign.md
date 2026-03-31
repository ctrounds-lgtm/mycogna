# Plan: MyCogna Redesign

**Created:** 2026-03-24
**Status:** Implemented
**Request:** A Cogna IS a single voice/persona — not a container of voices. Guardian creates one Cogna per person (Mom, Kenzie, Dillon = three Cognas). One child access code unlocks all Cognas the guardian built. Child enters code, sees all available Cognas, selects which ones to include in a conversation. Multi-voice conversations where selected Cognas respond to the user AND to each other. Audio-only conversation with session journal at the end.

---

## Overview

### What This Plan Accomplishes

Rebuilds Cogna around a corrected core model: **a Cogna is a single voice/persona**, not a container. A guardian creates one Cogna per person — Mom is one Cogna, Kenzie is another, Dillon is a third. One child access code unlocks all Cognas the guardian built. The child sees a grid of those voices and chooses which ones to bring into a conversation. Selected Cognas respond to the user and to each other — affirming, pushing back, building on what was shared. The conversation is audio-only; a full labeled transcript is saved at the end as a session journal.

### Why This Matters

This model maps naturally to how people actually think about support: "I need to hear Mom today" or "I want to talk to Kenzie and Dillon together." Each Cogna has its own distinct personality, relationship, and voice. The guardian builds the circle once; the child reaches for whoever they need, whenever they need it.

---

## Current State

### Relevant Existing Structure

| File | Role |
|------|------|
| `apps/cogna/server.py` | FastAPI backend (~720 lines). Auth, respond, voice upload, family portal APIs. |
| `apps/cogna/config.json` | Global persona list (Mom, Ciara, Echo) with voice backends. |
| `apps/cogna/static/index.html` | Christopher's app — hardcoded 3 personas, no dynamic loading. |
| `apps/cogna/static/family.html` | Portal — auth + profile setup for one fixed user per role. |
| `apps/cogna/static/family.js` | JS for portal — login, register (with invite code), dashboard, uploads. |
| `apps/cogna/static/family.css` | Portal styles. |
| `apps/cogna/data/family_portal.json` | JSON database: users, invites. No concept of Cognas. |

### Gaps or Problems Being Addressed

- App is hardwired to one child with three hardcoded voices; no concept of Cognas as individual personas.
- Voices are defined globally in `config.json`; no per-user or per-guardian customization.
- Account registration requires an invite code (blocks self-service signup).
- Main app loads personas from static config — cannot support dynamically built personal support circles.
- No child access code system to hand off the app from guardian to child.
- No relational model for personas (no relationship type, closeness, or term of endearment).
- No multi-voice conversation — voices only respond to the user, never to each other.
- No session journal.

---

## Proposed Changes

### Summary of Changes

- **A Cogna = one voice/persona.** A guardian creates one Cogna per person. Three people = three Cognas.
- Guardian account has: `cogna_ids[]` (list of all Cognas they built) and one `child_access_code`.
- Each Cogna has: name, relationship, closeness (0–100), term of endearment, voice backend, voice sample, photo.
- Guardian portal: auth → dashboard (all Cognas + access code) → create/edit individual Cognas → voice upload + test per Cogna.
- Child access code is account-level (one code unlocks all Cognas the guardian built, not one Cogna).
- Main app (`index.html`): code entry → grid of all available Cognas → select one or more → conversation.
- Multi-voice conversation: selected Cognas respond to user AND to each other in sequence.
- Conversation is audio-only. Session journal saved at end.
- Self-setup adults follow the same flow: create Cognas in portal, use access code to enter conversation mode.
- Remove `config.json` personas. Remove account-level invite codes for registration.

### New Files to Create

| File Path | Purpose |
|-----------|---------|
| `apps/cogna/static/portal.html` | Replaces family.html. Multi-screen SPA: auth, Cogna dashboard, create Cogna, voice setup. |
| `apps/cogna/static/portal.js` | All JS for the new portal. |
| `apps/cogna/static/portal.css` | Styles for the new portal (can extend family.css patterns). |
| `apps/cogna/data/sessions/` | Directory for session journal JSON files, organized by cogna_id. |

### Files to Modify

| File Path | Changes |
|-----------|---------|
| `apps/cogna/server.py` | New data model helpers, new API endpoints, update `/api/respond`, remove old family portal routes, add `/portal` route. |
| `apps/cogna/config.json` | Remove personas block. Keep voice backend defaults and cache/voice dir config. |
| `apps/cogna/static/index.html` | Add child invite code entry screen. Load voices dynamically from API instead of hardcoded cards. |
| `apps/cogna/data/family_portal.json` | Migrate schema: add `cognas: {}` collection; keep existing user. |
| `apps/cogna/requirements.txt` | No new packages needed (requests already present for ElevenLabs). |
| `CLAUDE.md` | Update Cogna section: new portal URL, updated data model description. |

### Files to Delete

| File | Reason |
|------|--------|
| `apps/cogna/static/family.html` | Replaced by `portal.html`. |
| `apps/cogna/static/family.js` | Replaced by `portal.js`. |
| `apps/cogna/static/family.css` | Replaced by `portal.css` (styles reused/extended). |

---

## Design Decisions

### Key Decisions Made

1. **A Cogna is a single voice/persona, not a container.** Mom is one Cogna. Kenzie is another. This maps directly to how users think: "I want to hear Mom today." Each Cogna has its own name, relationship, personality, and voice.

2. **Child access code is account-level, not Cogna-level.** One code unlocks all Cognas the guardian has built. The guardian shares one code with the child; the child immediately sees the full support circle.

3. **Cogna schema (flat, no nested voices array):**
   ```json
   {
     "id": "cogna_XXXXXX",
     "owner_email": "...",
     "name": "Mom",
     "relationship": "Mother",
     "term_of_endearment": "Sweetie",
     "params": {
       "warmth": 80,
       "validation": 30,
       "tone": 25,
       "structure": 45,
       "stance": 20
     },
     "voice_backend": "seed_vc",
     "elevenlabs_voice_id": null,
     "voice_sample": "data/family_uploads/...",
     "photo": "data/family_uploads/...",
     "last_tested_at": null,
     "created_at": "..."
   }
   ```

4. **User schema includes `cogna_ids` and `child_access_code`:**
   ```json
   {
     "email": "...",
     "name": "...",
     "password_salt": "...",
     "password_hash": "...",
     "setup_type": "guardian",
     "child_access_code": "COGNA-K7X2",
     "cogna_ids": ["cogna_abc", "cogna_def", "cogna_ghi"],
     "created_at": "..."
   }
   ```
   `setup_type` is `"guardian"` (building for a child) or `"self"` (building for themselves). Both types use the same access code flow to enter conversation mode.

5. **Relational model per Cogna — 5 parameters (0–100 each):**

   | Parameter | Left pole | Right pole | What it shapes |
   |-----------|-----------|------------|----------------|
   | `warmth` | Warm | Direct | Soft landing vs. straight talk |
   | `validation` | Affirm | Challenge | Mirror vs. catalyst |
   | `tone` | Playful | Serious | Levity vs. gravity |
   | `structure` | Steps | Explore | Roadmap vs. open road |
   | `stance` | Protect | Empower | Safe harbor vs. launchpad |

   Plus `name`, `relationship` (free text), and `term_of_endearment` (free text). All 8 fields feed into the auto-generated persona prompt.

   **Design reference:** `reference/mycogna-voice-setup-reference.html` — the exact UI to implement for the create-Cogna screen in the portal. Fonts: Cormorant Garamond (serif, headings) + DM Sans (body). Colors defined in that file's CSS variables.

6. **`/api/converse` takes a list of `cogna_ids`** — each being a complete persona. No sub-voice lookup needed. The endpoint builds each Cogna's prompt, generates responses in sequence with inter-voice awareness, returns ordered audio + text.

7. **`/api/child/access`** takes the access code → looks up the owner's account → returns all their Cognas. Stored in localStorage so child doesn't re-enter the code each session.

8. **Self-setup adults use the same access code flow** — after building their Cognas in the portal, they click "Start Talking" which auto-uses their own access code to enter conversation mode.

### Alternatives Considered

- **Separate database file per Cogna**: Simpler isolation but adds file management complexity. Rejected in favor of one JSON file.
- **Keep invite codes for adult accounts**: Adds access control but kills self-service. Removed since there's no stated need to restrict who can create an account.
- **Hardcoded relationship types in prompt**: Simpler but loses the nuance of closeness level. The slider allows fine-grained prompt tuning.

### Resolved Decisions

1. **Sliding scale labels**: Keep as-is — Acquaintance (0–30) / Familiar (31–60) / Close (61–85) / Very Close (86–100).
2. **Relationship types**: Mom, Friend, Coach.
3. **Voice name examples** (used in placeholders throughout UI): Mom, Kenzie, Dillon.
4. **Term of endearment**: New field on each voice. Placeholder examples: Sweetie, My Dear, Bro. Helper text below field: "(You can also use a nickname)".
5. **Child invite code format**: `COGNA-XXXX` confirmed.
6. **Database**: Wipe `family_portal.json` and start fresh. The existing test account has no real data (no voice samples, no photos), the old schema is incompatible with the new model, and writing one-time migration code for test data is not worth the effort.

---

## Step-by-Step Tasks

### Step 1: Wipe and Reinitialize the Database

Replace `data/family_portal.json` with a clean slate matching the new schema. The old data (test account only, no real voice samples or photos) is incompatible with the new model and not worth migrating.

**Actions:**

- Overwrite `family_portal.json` with:
  ```json
  {
    "users": {},
    "cognas": {},
    "created_at": "<current UTC timestamp>"
  }
  ```
- Delete any cached audio in `data/cogna_cache/` (generated from old hardcoded personas, no longer valid).
- The new schema per user:
  ```json
  {
    "email": "...",
    "name": "...",
    "password_salt": "...",
    "password_hash": "...",
    "setup_type": "guardian",
    "child_access_code": "COGNA-XXXX",
    "cogna_ids": [],
    "created_at": "..."
  }
  ```
- The new schema per Cogna (flat — a Cogna IS the persona, no nested voices):
  ```json
  {
    "id": "cogna_XXXXXX",
    "owner_email": "...",
    "name": "Mom",
    "relationship": "Mother",
    "term_of_endearment": "Sweetie",
    "params": {
      "warmth": 80,
      "validation": 30,
      "tone": 25,
      "structure": 45,
      "stance": 20
    },
    "voice_backend": "seed_vc",
    "elevenlabs_voice_id": null,
    "voice_sample": null,
    "photo": null,
    "last_tested_at": null,
    "created_at": "..."
  }
  ```

**Files affected:**
- `apps/cogna/data/family_portal.json`
- `apps/cogna/data/cogna_cache/` (clear contents)

---

### Step 2: Update `config.json`

Remove the `personas` block. Add a `voice_defaults` block with ElevenLabs model preference.

**Actions:**

- Remove the entire `"personas"` key and all its contents.
- Add:
  ```json
  "voice_defaults": {
    "elevenlabs_model": "eleven_monolingual_v1",
    "tts_fallback": true
  }
  ```
- Keep `voice_reference_dir`, `cache_dir`, `claude_api_key_env`.

**Files affected:**
- `apps/cogna/config.json`

---

### Step 3: Refactor `server.py` — Data Model Helpers

Add new helper functions for Cogna CRUD. Update `_load_db` to initialize `cognas: {}`.

**Actions:**

- In `_load_db`: add `db.setdefault("cognas", {})`.
- Remove `DEFAULT_INVITES` constant (no more account-level invite codes).
- Add helper `_get_cogna(db, cogna_id) -> dict` — returns Cogna or raises 404.
- Add helper `_get_voice(cogna, voice_id) -> dict` — returns voice dict or raises 404.
- Add helper `_cogna_voice_prompt(cogna) -> str` — builds a rich persona prompt from all 8 fields. Each of the 5 parameters maps to a descriptive phrase based on its value (0–100):

  ```python
  def _cogna_voice_prompt(cogna):
      p = cogna.get("params", {})
      name = cogna["name"]
      relationship = cogna.get("relationship", "")
      tod = cogna.get("term_of_endearment", "")

      warmth_desc    = "lead with tenderness and emotional safety" if p.get("warmth",50) < 50 else "be candid and direct, offering straight talk over softness"
      validation_desc = "primarily affirm and reflect feelings back" if p.get("validation",50) < 50 else "gently challenge, ask hard questions, and invite growth"
      tone_desc      = "bring lightness, humor, and ease when appropriate" if p.get("tone",50) < 50 else "hold space with gravity, weight, and emotional presence"
      structure_desc = "offer clear steps and practical guidance" if p.get("structure",50) < 50 else "ask open-ended questions and invite the person to find their own way"
      stance_desc    = "wrap around and protect, making them feel safe" if p.get("stance",50) < 50 else "believe in their capability and nudge them toward their own strength"

      tod_line = f" Address them as '{tod}'." if tod else ""

      return (
          f"You are {name}, a {relationship}.{tod_line} "
          f"When you respond: {warmth_desc}. "
          f"You tend to {validation_desc}. "
          f"In terms of tone, {tone_desc}. "
          f"For guidance, {structure_desc}. "
          f"Your stance is to {stance_desc}. "
          f"Keep responses warm, concise, and human — 2 to 4 sentences unless more is needed."
      )
  ```
- Add helper `_generate_child_invite_code() -> str` — returns `"COGNA-" + 4 random uppercase alphanumeric chars`.
- Update `_public_user` to remove `persona_name` and `profile` fields; add `cogna_ids`.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 4: Refactor `server.py` — Update Auth Endpoints

Remove invite code from registration. Update register to initialize `cogna_ids: []`.

**Actions:**

- Remove `FamilyRegisterRequest.invite_code` field.
- Remove invite validation logic from `family_register`.
- Add `setup_type` field to `FamilyRegisterRequest` (`"guardian"` or `"self"`).
- In `family_register`, create user with:
  ```python
  {
    "email": email,
    "name": payload.name.strip(),
    "password_salt": salt,
    "password_hash": password_hash,
    "setup_type": payload.setup_type,
    "child_access_code": _generate_child_access_code(),
    "cogna_ids": [],
    "created_at": _utc_now(),
  }
  ```
  The access code is always generated at registration — both guardian and self-setup users need one to enter conversation mode.
- Remove `DEFAULT_INVITES` from `_load_db` setdefault call.
- Rename routes from `/api/family/*` to `/api/auth/*` (`/api/auth/register`, `/api/auth/login`, `/api/auth/me`).
- Update `/portal` route to serve `portal.html` (replacing `/family` → `family.html`).

**Files affected:**
- `apps/cogna/server.py`

---

### Step 5: Add Cogna API Endpoints to `server.py`

Add all Cogna management endpoints.

**Actions:**

Add the following endpoints:

```
GET    /api/cognas                   — list all Cognas owned by authenticated user
POST   /api/cognas                   — create a new Cogna (one persona)
GET    /api/cognas/{cogna_id}        — get Cogna detail
PUT    /api/cognas/{cogna_id}        — update Cogna metadata
DELETE /api/cognas/{cogna_id}        — delete a Cogna
POST   /api/cognas/{cogna_id}/sample — upload voice sample for this Cogna
POST   /api/cognas/{cogna_id}/photo  — upload photo for this Cogna
POST   /api/cognas/{cogna_id}/test   — generate test audio for this Cogna
GET    /api/auth/me/access-code      — return the authenticated user's child_access_code
POST   /api/child/access             — child submits access code, returns all owner's Cognas
```

**`POST /api/cognas` request body:**
```json
{
  "name": "Mom",
  "relationship": "Mother",
  "term_of_endearment": "Sweetie",
  "params": {
    "warmth": 80,
    "validation": 30,
    "tone": 25,
    "structure": 45,
    "stance": 20
  },
  "voice_backend": "seed_vc",
  "elevenlabs_voice_id": null
}
```
Generate `cogna_id` with `"cogna_" + secrets.token_hex(6)`.
UI placeholder name examples: Mom, Kenzie, Dillon.

**`POST /api/child/access` request body:**
```json
{ "access_code": "COGNA-K7X2" }
```
Scans all users for matching `child_access_code`. Returns:
```json
{
  "owner_name": "Christy",
  "cognas": [
    {"id": "cogna_abc", "name": "Mom", "relationship": "Mom", "closeness": 95, "photo": null},
    {"id": "cogna_def", "name": "Kenzie", "relationship": "Friend", "closeness": 75, "photo": null},
    {"id": "cogna_ghi", "name": "Dillon", "relationship": "Coach", "closeness": 60, "photo": null}
  ]
}
```
Child stores `access_code` in localStorage; re-fetches Cogna list on each app load.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 6: Update `/api/respond` in `server.py`

Simplify to use a single `cogna_id` — a Cogna IS the persona, no sub-voice lookup needed.

**Actions:**

- Replace `persona` form field with `cogna_id`.
- Look up Cogna directly: `cogna = db["cognas"][cogna_id]`.
- Build prompt using `_cogna_voice_prompt(cogna)`.
- Route to voice backend using `cogna["voice_backend"]` and `cogna["elevenlabs_voice_id"]`.
- Cache key: `f"{cogna_id}|{generated_text}"`.
- Remove all backward-compatibility code for old global config personas.

**Files affected:**
- `apps/cogna/server.py`

---

### Step 7: Create `portal.html`

New single-page portal replacing `family.html`. Contains all screens as hidden sections.

**Screens (as `<section>` elements toggled by JS):**

1. **`authScreen`** — Login form + Register form side by side. Register has: Name, Email, Password, Confirm Password. No invite code field.

2. **`dashboardScreen`** — Guardian's home base:
   - "Your Cognas" heading
   - Grid of Cogna cards (photo/avatar, name, relationship chip, completeness indicator: voice ✅/⚠️, photo ✅/⚠️)
   - "+ Add a Cogna" button
   - **Child Access Code box**: highlighted, monospace code (`COGNA-XXXX`), copy button, note: "Give this code to [child's name] to start using the app."
   - "I am setting this up for myself" toggle (self-setup users see "Start Talking" button instead of access code box)
   - Logout button

3. **`createCognaScreen`** — Implemented pixel-faithfully from `reference/mycogna-voice-setup-reference.html`:
   - Dark header: "MyCogna · Voice Setup" eyebrow, "Shape your companion's voice" title (Cormorant Garamond), gold subtitle
   - Avatar circle (shows first initial of name, updates live)
   - Voice name input (placeholder: "e.g. Mom, Kenzie, Dillon…")
   - Two-column row: Relationship (free text, placeholder: "e.g. Mother, Friend, Coach…") + Term of endearment (placeholder: "e.g. Buddy, Sunshine, Champ…")
   - Divider + "RELATIONAL PARAMETERS" section label
   - **5 sliders**, each with colored dot, name, left/right poles, live value badge, and italic description:
     1. **Warmth** (gold #C9963A) — Warm ↔ Direct
     2. **Validation** (teal #3A7B72) — Affirm ↔ Challenge
     3. **Tone** (coral #C45E4A) — Playful ↔ Serious
     4. **Structure** (blue #5A7EA8) — Steps ↔ Explore
     5. **Stance** (purple #6E5A8A) — Protect ↔ Empower
   - Voice backend section (below sliders, before save button): radio — "Upload a voice recording" / "Use an ElevenLabs voice ID". If ElevenLabs: text input for voice ID.
   - "Save this Cogna voice →" full-width dark button
   - Back button

4. **`cognaDetailScreen`** — Setup completion for one Cogna:
   - Shows Cogna name, relationship, closeness bar, term of endearment
   - Upload voice sample section (accepts MP3, WAV, M4A, WEBM; hint: "iPhone voice memos work great")
   - Upload photo section
   - Test voice section: textarea with default message → "Generate Test Audio" → inline audio player
   - Completion checklist: voice ✅/⚠️, photo ✅/⚠️, tested ✅/⚠️
   - Back to dashboard button

**Files affected:**
- `apps/cogna/static/portal.html` (new file)

---

### Step 8: Create `portal.js`

JS for the new portal SPA.

**Key functions:**

- `showScreen(id)` — hides all screens, shows the target one.
- `initSession()` — checks localStorage token; if valid, loads Cogna list; else shows auth screen.
- `loadCognaList()` — `GET /api/cognas`, renders Cogna cards, shows `cognaListScreen`.
- `openCogna(cognaId)` — `GET /api/cognas/{id}`, renders voice list + child invite code, shows `cognaDetailScreen`.
- `createCogna(formData)` — `POST /api/cognas`, then opens the new Cogna detail screen.
- `addVoice(cognaId, formData)` — `POST /api/cognas/{id}/voices`, then opens voice detail screen.
- `openVoiceDetail(cognaId, voiceId)` — shows `voiceDetailScreen` with upload and test forms pre-wired.
- `uploadVoiceSample(cognaId, voiceId, file)` — `POST /api/cognas/{id}/voices/{vid}/sample`.
- `testVoice(cognaId, voiceId, message)` — `POST /api/cognas/{id}/voices/{vid}/test`, renders audio player.
- `copyInviteCode(code)` — copies child invite code to clipboard, shows confirmation.
- Inline error display pattern (matching `registerError` approach from the current `family.js`).

Closeness slider label logic:
```js
function closenessLabel(val) {
  if (val <= 30) return 'Acquaintance';
  if (val <= 60) return 'Familiar';
  if (val <= 85) return 'Close';
  return 'Very Close';
}
```

**Files affected:**
- `apps/cogna/static/portal.js` (new file)

---

### Step 9: Create `portal.css`

Styles for the new portal. Reuse the CSS custom properties and base patterns from `family.css`.

**Key additions over `family.css`:**

- `.cogna-grid` — responsive card grid for Cogna list.
- `.cogna-card` — card with name, user chip, voice count badge.
- `.voice-list` — list of voice cards within a Cogna.
- `.voice-card` — compact card showing name, relationship chip, closeness bar.
- `.invite-code-box` — highlighted box with monospace code and copy button.
- `.slider-row` — flex row with slider + live label.
- `.radio-group` — backend selector radio buttons.
- `.closeness-bar` — visual fill bar (0–100%) shown on voice cards.

**Files affected:**
- `apps/cogna/static/portal.css` (new file)

---

### Step 10: Add Multi-Voice Conversation Endpoint to `server.py`

Add `POST /api/converse` — the core multi-voice engine. Each voice in the turn sees the user's message plus all prior voice responses in the same turn, enabling natural inter-voice dialogue.

**Actions:**

- Add `ConverseTurn` Pydantic model:
  ```python
  class ConverseTurn(BaseModel):
      cogna_ids: List[str]           # ordered list; each is a full Cogna (= one persona)
      message: Optional[str] = None  # text input
      history: List[Dict] = []       # prior turns: [{"role": "user"|cogna_name, "content": "..."}]
  ```
- Add `POST /api/converse` endpoint logic:
  1. Transcribe audio if provided (same as existing `/api/respond` path).
  2. For each `cogna_id` in order:
     - Load the Cogna directly from `db["cognas"][cogna_id]`.
     - Build system prompt with `_cogna_voice_prompt(cogna)`.
     - Inject group awareness into system prompt:
       ```
       "You are in a group conversation with {other_voice_names}.
        Respond to the user and authentically to what others have shared.
        You may affirm, gently push back, or add your own perspective.
        Keep your response warm and concise — 2 to 4 sentences."
       ```
     - Build message list from `history` + user message + any prior voice responses in THIS turn.
     - Generate text response via Claude API.
     - Generate audio via the voice's backend (ElevenLabs or Seed-VC/TTS).
     - Append `{"role": cogna["name"], "content": response_text}` to this turn's running context.
  3. Return ordered list of responses:
     ```json
     {
       "turn": [
         {"cogna_id": "...", "cogna_name": "Mom", "text": "...", "audio_url": "/audio/..."},
         {"cogna_id": "...", "cogna_name": "Kenzie", "text": "...", "audio_url": "/audio/..."}
       ],
       "transcript_entry": [
         {"role": "user", "content": "I'm feeling overwhelmed"},
         {"role": "Mom", "content": "Sweetie, I hear you..."},
         {"role": "Kenzie", "content": "Yeah, what Mom said — and also..."}
       ]
     }
     ```
- Add `POST /api/sessions` endpoint to save a completed session journal:
  ```python
  class SaveSessionRequest(BaseModel):
      cogna_id: str
      transcript: List[Dict]   # full conversation history
      voice_names: List[str]   # which voices participated
      duration_seconds: int
  ```
  Saves to `data/sessions/{cogna_id}/session_{timestamp}.json`.
- Add `GET /api/sessions/{cogna_id}` to list saved sessions for a Cogna (used by guardian portal).

**Files affected:**
- `apps/cogna/server.py`
- `apps/cogna/data/sessions/` (directory created on first save)

---

### Step 11: Update `index.html` — Full Main App Redesign

Replace the current main app with the new child-facing experience: code entry → voice selection → audio-only multi-voice conversation → session journal.

**Screens:**

1. **`codeEntryCard`** — Shown on first load (no `accessCode` in localStorage):
   - "Welcome to Cogna" heading
   - "Enter the code your parent or guardian gave you." (or "Enter your access code." for self-setup)
   - Text input: placeholder `COGNA-XXXX`
   - Inline error display
   - "Continue" button → `POST /api/child/access` → store `accessCode` + `cognas[]` in localStorage

2. **`cognaSelectCard`** — "Who do you want to talk to today?":
   - Grid of Cogna cards, one per persona (Mom, Kenzie, Dillon…)
   - Each card shows: photo (or initial avatar), name, relationship chip, closeness-derived tagline
   - Each card has a checkbox — user can select one or more
   - "Start Conversation" button enabled when ≥1 selected
   - Cards loaded dynamically from `cognas[]` in localStorage, refreshed on each visit via `/api/child/access`

3. **`conversationCard`** — Audio-only conversation:
   - No message thread displayed during conversation
   - Large mic button (hold to speak) in center
   - While voices are responding: animated waveform + active voice name shown (e.g., "Mom is speaking…")
   - Voices play sequentially, auto-advancing
   - After all voices in a turn have played: mic button reactivates
   - "End Conversation" button in corner → triggers session journal screen
   - Crisis overlay remains intact (keyword detection on transcribed text)

4. **`journalCard`** — Session transcript shown after "End Conversation":
   - "Your conversation" heading with date/time
   - Scrollable transcript: each line labeled with speaker name (User, Mom, Kenzie, etc.)
   - "Save & Close" button → `POST /api/sessions` → returns to `voiceSelectCard`
   - "Start a new conversation" button

**JS logic additions:**

- `loadCogna(code)` — calls `/api/child/access`, stores result, renders voice select screen.
- `startConversation(selectedCognaIds)` — initializes conversation state, shows `conversationCard`.
- `sendTurn(audioBlob | text)` — calls `POST /api/converse` with `cogna_ids` + current history, receives ordered responses.
- `playResponseSequence(responses)` — plays audio files one after another. While each plays, shows `"{voice_name} is speaking…"`. After all finish, re-enables mic.
- `appendToHistory(turn)` — appends transcript entries to the in-memory session history.
- `endConversation()` — shows `journalCard` with full history rendered.
- `saveSession()` — calls `POST /api/sessions`, then resets state.

**Files affected:**
- `apps/cogna/static/index.html`

---

### Step 12: Clean Up Old Files

Remove the old family portal files now replaced by the portal.

**Actions:**

- Delete `apps/cogna/static/family.html`.
- Delete `apps/cogna/static/family.js`.
- Delete `apps/cogna/static/family.css`.

**Files affected:**
- `apps/cogna/static/family.html` (delete)
- `apps/cogna/static/family.js` (delete)
- `apps/cogna/static/family.css` (delete)

---

### Step 13: Update `CLAUDE.md`

Reflect new URLs, structure, and data model.

**Actions:**

- Update Cogna section:
  - Portal URL: `/portal` (was `/family`)
  - Data model: reference `cognas` collection in `family_portal.json`
  - Add note about child invite codes
  - Remove reference to hardcoded personas in `config.json`

**Files affected:**
- `CLAUDE.md`

---

### Step 14: Restart Server and Validate

**Actions:**

- Stop and restart the uvicorn server.
- Verify `/portal` loads the new portal.
- Verify `/` shows the code entry screen when no `cognaId` in localStorage.
- Create a test account (no invite code required).
- Create a Cogna for a child → confirm invite code appears.
- Add 2+ voices with relationship, closeness, and term of endearment → confirm they appear.
- Enter child invite code on the main app → confirm voice selection screen loads.
- Select 2 voices, speak a message → confirm both voices respond sequentially in audio.
- Confirm Voice 2's response references or reacts to Voice 1's response.
- Click "End Conversation" → confirm full transcript appears.
- Save session → confirm file created in `data/sessions/{cogna_id}/`.
- Verify single-voice mode still works (select 1 voice → standard conversation).

---

## Connections & Dependencies

### Files That Reference This Area

- `CLAUDE.md` — references `/family`, family portal, and the Cogna app section.
- `apps/cogna/server.py` — all routes and data logic.
- `apps/cogna/data/family_portal.json` — wiped and reinitialized in Step 1.

### Updates Needed for Consistency

- `CLAUDE.md` Cogna section (Step 12).
- Any saved browser bookmarks to `/family` will break; new URL is `/portal`.

### Impact on Existing Workflows

- Old test account and cached audio are wiped in Step 1. User re-registers fresh.
- ElevenLabs voice IDs will be re-entered through the new voice setup UI.

---

## Validation Checklist

- [ ] `/portal` loads the new portal without JS errors
- [ ] New account can be created without an invite code
- [ ] Creating a Cogna for a child generates and displays an invite code
- [ ] Creating a Cogna for self skips child invite code
- [ ] Voice can be added with relationship type and closeness slider
- [ ] Closeness slider label updates live (Acquaintance → Familiar → Close → Very Close)
- [ ] Voice sample upload saves correctly per Cogna/voice
- [ ] Child entering invite code on `/` loads that Cogna's voices dynamically
- [ ] Guardian registers without invite code; account has a `child_access_code` immediately
- [ ] Guardian creates 3 Cognas (Mom, Kenzie, Dillon) — each is a separate, flat persona record
- [ ] Each Cogna: relationship + closeness slider + term of endearment all save correctly
- [ ] Voice sample upload (M4A/MP3/WAV) saves to `data/family_uploads/`
- [ ] Photo upload saves correctly
- [ ] Test audio generates using correct backend (ElevenLabs or Seed-VC)
- [ ] Dashboard shows child access code with copy button
- [ ] Child enters access code on `/` → sees grid of all 3 Cognas
- [ ] Child selects 1 Cogna → single-voice conversation works
- [ ] Child selects 2+ Cognas → multi-voice: each responds in sequence, later voices react to earlier ones
- [ ] Conversation UI is audio-only (no message text during playback)
- [ ] Active Cogna name shown while its audio plays
- [ ] "End Conversation" → full labeled transcript displayed
- [ ] Session saved to `data/sessions/` and retrievable via API
- [ ] Crisis overlay triggers in multi-voice mode
- [ ] `/api/respond` with single `cogna_id` still works
- [ ] Old `/family` URL replaced by `/portal`
- [ ] `CLAUDE.md` updated

---

## Success Criteria

1. A guardian registers, creates three Cognas (Mom, Kenzie, Dillon — each a flat persona with relationship, closeness, term of endearment, and a voice), and sees a child access code on their dashboard.
2. A child enters the access code and sees the full grid of Cognas the guardian built. They pick the voice they need that day — one or several.
3. In multi-voice mode, each selected Cogna responds to the user AND authentically to what the preceding Cognas said, creating genuine inter-voice dialogue.
4. The conversation is audio-only. A full labeled session transcript is saved at the end and accessible to the guardian.

---

## Notes

- **Sliding scale code**: The user referenced previously created code for a relational slider. No such code was found in the workspace. The slider in Step 8 is built from scratch using a standard HTML `<input type="range">` with a live JS label.
- **Seed-VC for Mom's voice**: The `seed_vc` backend is still a copy-through stub. Wiring up actual Seed-VC conversion is a separate task after this redesign is complete.
- **Session persistence**: Sessions are still in-memory (lost on server restart). This is a known limitation; adding persistent sessions is a separate future task.
- **Voice prompt quality**: The auto-generated prompt from `_cogna_voice_prompt()` is a starting point. A future enhancement could let users customize the prompt per voice.
- **Multi-voice conversation and the podcast**: This feature is architecturally identical to Christy's AI podcast work — voices with distinct personas responding to each other in sequence. The session journal is the equivalent of a conversation transcript. These two projects may eventually share infrastructure.
- **Response length in multi-voice mode**: Each voice is instructed to keep responses to 2–4 sentences to prevent lag and keep the audio experience moving naturally. This is enforced in the system prompt.
- **Lag consideration**: Audio files for all voices in a turn are generated server-side before any playback begins. This means a short wait after the user speaks, then all audio plays without interruption. This is preferable to streaming each voice one-by-one with gaps between API calls.
- **Session journal access for guardians**: The portal's Cogna detail screen should eventually show saved sessions. This is noted as a follow-up enhancement — the storage and API are built now, the portal UI for viewing them comes next.

---

## Implementation Notes

**Implemented:** 2026-03-24

### Summary

- Wiped `family_portal.json` to new schema (`users`, `cognas`, `created_at`)
- Updated `config.json` — removed personas block, added `voice_defaults`
- Rewrote `server.py` — new data model, all Cogna CRUD endpoints, `/api/auth/*`, `/api/child/access`, `/api/converse` multi-voice engine, `/api/sessions`, updated `/api/respond` for `cogna_id`, `/portal` route
- Created `portal.html` — 4-screen SPA: auth, dashboard (with access code box), create Cogna (pixel-faithful to reference design with 5 colored sliders), Cogna detail (uploads + test)
- Created `portal.css` — full MyCogna design system (Cormorant Garamond + DM Sans, cream/ink/gold palette)
- Created `portal.js` — complete SPA logic (auth, Cogna CRUD, slider live updates, upload forms, test voice)
- Redesigned `index.html` — 4 screens: code entry, Cogna selection grid, audio-only conversation with waveform, session journal
- Deleted `family.html`, `family.js`, `family.css`
- Updated `CLAUDE.md` with new architecture, URLs, and data model

### Deviations from Plan

- `/api/converse` accepts form data with JSON-encoded `cogna_ids` and `history` fields (plus optional audio file) rather than a pure JSON body, to allow audio file upload in the same request
- `portal.js` event listener bindings for forms are done via `addEventListener` at the bottom of the file rather than inline, for cleaner separation

### Issues Encountered

None
