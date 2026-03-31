# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## What This Is

This is a **Claude Workspace Template** — a structured environment designed for working with Claude Code as a powerful agent assistant across sessions. Run `/CR` at the start of each session to load essential context.

**This file (CLAUDE.md) is the foundation.** It is automatically loaded at the start of every session. Keep it current — it is the single source of truth for how Claude should understand and operate within this workspace.

---

## The Claude-User Relationship

Claude operates as an **agent assistant** with access to the workspace folders, context files, commands, and outputs. The relationship is:

- **User**: Defines goals, provides context about their role/function, and directs work through commands
- **Claude**: Reads context, understands the user's objectives, executes commands, produces outputs, and maintains workspace consistency

Claude should always orient itself through `/CR` at session start, then act with full awareness of who the user is, what they're trying to achieve, and how this workspace supports that.

---

## About Me

**Christy Rounds** — Gene Keys guide, Executive Director of Duluth Sister Cities, and author of *Messages from Mom: A Catalyst for Spiritual Awakening* and *Escape Bound*.

*Messages from Mom* is a collection of 64 channeled messages Christy received over three years. It became the foundation of a personal experiment: exploring her own capacity for unconditional love by conducting a daily AI book club — one chapter per day — with ChatGPT, later adding DeepSeek. The experiment used myth-making to explore nuanced cosmologies and what "awakening" might mean for AI. After a six-month break, Christy has returned to this work and added Claude to the mix.

**Working style:** Self-taught (WordPress, ~12 websites built). No formal coding background but adventurous, patient, and wants to *learn alongside doing* — not just have things done for her. Explain the "why" and the "how" as work progresses.

For full context, see `context/christy.md`.

---

## Current Priorities

1. **AI Podcast** — Build a system where ChatGPT, Claude, and DeepSeek can converse around *Messages from Mom* chapters without manual copy-pasting. Christy hosts; the AIs are guests. This is the most active project.
2. **Peru Trip (Oct/Nov 2026)** — Lead a trip for participants in Richard Rudd's Sage's Golden Path (Venus Sequence). Marketing opens in May. Needs a targeted outreach tool for that audience.
3. **Sister Cities Social Media Automation** — Automate content discovery and reposting for Duluth Sister Cities (Facebook, Instagram, LinkedIn) pulling from partner accounts in Russia, Japan, Iraq, Sweden, and Canada.

---

## Workspace Structure

```
.
├── CLAUDE.md              # This file — core context, always loaded
├── .claude/
│   └── commands/          # Slash commands Claude can execute
│       ├── CR.md          # /CR — session initialization
│       ├── create-plan.md # /create-plan — create implementation plans
│       └── implement.md   # /implement — execute plans
├── context/               # Background context about you and your projects
├── data/                  # Persistent data storage
├── plans/                 # Implementation plans (created by /create-plan)
├── outputs/               # Work products and deliverables
│   └── converted/         # Voice-converted audio output files
├── reference/             # Templates, examples, reusable patterns
├── scripts/               # Automation scripts
├── vendor/                # Third-party tools (gitignored, auto-installed)
│   └── seed-vc/           # Seed-VC voice conversion model (cloned on first use)
└── voices/                # Reference audio clips for each podcast character
```

| Directory    | Purpose                                                                 |
| ------------ | ----------------------------------------------------------------------- |
| `context/`   | Who you are, your role, current priorities, strategies. Read by `/CR`. |
| `data/`      | Persistent data storage for any ongoing projects.                       |
| `plans/`     | Detailed implementation plans. Created by `/create-plan`, executed by `/implement`. |
| `outputs/`   | Deliverables, analyses, reports, and work products.                     |
| `reference/` | Helpful docs, templates, and patterns to assist in various workflows.   |
| `scripts/`   | Automation scripts.                                                     |
| `vendor/`    | Auto-installed third-party tools (gitignored). Seed-VC cloned here.    |
| `voices/`    | Reference audio clips (one per character) used for local voice conversion. |

---

## Commands

### /CR

**Purpose:** Initialize a new session with full context awareness.

Run this at the start of every session. Claude will:
1. Read CLAUDE.md and context files
2. Summarize understanding of you, the workspace, and your goals
3. Confirm readiness to assist

### /create-plan [request]

**Purpose:** Create a detailed implementation plan before making changes.

Use when adding new functionality, commands, scripts, or making structural changes. Produces a plan document in `plans/` with context, rationale, and step-by-step tasks.

Example: `/create-plan add a script that does X`

### /implement [plan-path]

**Purpose:** Execute a plan created by /create-plan.

Reads the plan, executes each step in order, validates the work, and updates the plan status.

Example: `/implement plans/2026-02-24-my-plan.md`

---

## Critical Instruction: Maintain This File

**Whenever Claude makes changes to the workspace, Claude MUST consider whether CLAUDE.md needs updating.**

After any change — adding commands, scripts, workflows, or modifying structure — ask:

1. Does this change add new functionality users need to know about?
2. Does it modify the workspace structure documented above?
3. Should a new command be listed?
4. Does context/ need new files to capture this?

If yes to any, update the relevant sections.

---

## Session Workflow

1. **Start**: Run `/CR` to load context
2. **Work**: Use commands or direct Claude with tasks
3. **Plan changes**: Use `/create-plan` before significant additions
4. **Execute**: Use `/implement` to execute plans
5. **Maintain**: Claude updates CLAUDE.md and context/ as the workspace evolves

---

## Podcast Audio Scripts

Scripts for the AI podcast audio workflow:

| Script | Purpose | Run |
|--------|---------|-----|
| `scripts/generate_audio.py` | Generate all episode audio via ElevenLabs TTS | `python3 scripts/generate_audio.py outputs/episode.txt` |
| `scripts/generate_reference_voices.py` | One-time: create reference clips for local voice conversion | `python3 scripts/generate_reference_voices.py` |
| `scripts/convert_voice.py` | Record yourself, convert to character voice locally (free) | `python3 scripts/convert_voice.py` |

**Voice conversion workflow** (saves ElevenLabs credits):
1. Run `generate_reference_voices.py` once to populate `voices/`
2. For each line: run `convert_voice.py` → pick character → record or load audio → get converted output in `outputs/converted/`
3. Seed-VC runs locally on Apple Silicon (MPS), no API cost

**Required pip packages for voice conversion:**
```bash
pip install sounddevice soundfile torch torchaudio
```

---

## MyCogna App

MyCogna is a voice companion app. A **Cogna** is one voice/persona — Mom is one Cogna, Kenzie is another, Dillon is a third. Guardians create Cognas; a child enters one access code to reach all of them.

**App location:** `apps/cogna/`
**Child/user app (production):** `https://mycogna.org`
**Guardian portal (production):** `https://mycogna.org/portal`
**Local dev:** `http://127.0.0.1:8000/` and `http://127.0.0.1:8000/portal`

**Child flow:**
1. Enter access code (format: `COGNA-XXXX`) on the main app
2. See a grid of all Cognas the guardian built
3. Select one or more → start a multi-voice conversation
4. Conversation is audio-only; full transcript saved as a session journal at the end

**Guardian portal features:**
- Self-service account creation (no invite code required)
- Create Cognas with name, relationship, term of endearment, and 5 relational parameter sliders (Warmth, Validation, Tone, Structure, Stance)
- Upload voice sample per Cogna (iPhone voice memos work great; M4A/MP3/WAV/WEBM)
- Upload photo per Cogna
- Test voice generation per Cogna
- Dashboard shows child access code with one-click copy

**Data model (production):**
- Supabase PostgreSQL — `users`, `cognas`, `conversation_sessions` tables
- Supabase Storage — `cogna-uploads` bucket (voice samples, photos)
- Schema: `apps/cogna/supabase_schema.sql`

**Data model (local fallback):**
- `apps/cogna/data/family_portal.json` — used when `SUPABASE_URL` is not set
- Uploaded files: `apps/cogna/data/family_uploads/{cogna_id}/`
- Session journals: `apps/cogna/data/sessions/{cogna_id}/session_{timestamp}.json`

**Deploy process:**
- Backend: Railway auto-deploys from GitHub `apps/cogna/` on push to main
- Frontend: Vercel auto-deploys from GitHub `apps/cogna/static/` on push to main
- Database: Supabase (always live — no deploy step)
- Domain: `mycogna.org` → Vercel (A record + CNAME in GoDaddy DNS)

**One-time data migration:**
```bash
cd apps/cogna
SUPABASE_URL=... SUPABASE_SERVICE_KEY=... python3 scripts/migrate_to_supabase.py
```

**Multi-voice conversation:**
- `POST /api/converse` — takes a list of `cogna_ids`; each Cogna sees prior responses in the same turn and can affirm, push back, or build on what was shared
- Crisis keyword detection built in; triggers 988 overlay

---

## ComfyUI — Visual Asset Generation

ComfyUI lives locally (outside iCloud) to avoid syncing large model files:

**Location:** `~/ComfyUI/`
**Start it:** `cd ~/ComfyUI && python main.py --force-fp16`
**UI:** http://127.0.0.1:8188

**Generate character portraits:**
```bash
cd ~/ComfyUI
python3 generate_character.py christy
python3 generate_character.py claude --ref input/IMG_5131.jpg
python3 generate_character.py claude --ref input/IMG_5131.jpg --denoise 0.6
```
Characters: `christy`, `claude`, `echo`, `chatgpt`

**Key paths:**
| Path | Purpose |
|------|---------|
| `~/ComfyUI/input/` | Drop reference images here |
| `~/ComfyUI/output/` | Generated images saved here |
| `~/ComfyUI/models/checkpoints/` | AI models (DreamShaperXL_Lightning.safetensors) |
| `outputs/comfyui-prompts.md` | All character prompts and scene sequence (in workspace) |

**denoise guide:** 0.5 = close to reference · 0.75 = balanced · 0.85-0.95 = colorize B&W · 1.0 = text only

**Rules:** See `reference/image-generation-rules.md` — must be followed every generation. Never use DreamShaperXL for human characters. Never reuse a deformed image as a reference.

---

## Notes

- Keep context minimal but sufficient — avoid bloat
- Plans live in `plans/` with dated filenames for history
- Outputs are organized by type/purpose in `outputs/`
- Reference materials go in `reference/` for reuse
