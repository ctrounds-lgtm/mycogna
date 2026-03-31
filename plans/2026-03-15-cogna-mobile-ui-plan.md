# Plan: Build Christopher Mobile Web App (Screens + UX Flow)

**Date:** 2026-03-15
**Updated:** 2026-03-17
**Goal:** Implement the full mobile app experience — voice-first, calm, single-surface conversation design.

---

## Overview

We have a working backend (Claude text + Whisper transcription + local TTS) and a baseline mobile UI. This plan builds the full multi-screen experience.

Key screens:
1. **Home / Persona selection**
2. **Unified conversation screen** — talk, waiting, and playing all on one surface (no screen transitions)
3. **Crisis mode** — overlay on the conversation screen

---

## Design Decision: Unified Conversation Surface

Talk, waiting, and playing are **not separate screens**. They are phases of one screen — like the Claude.ai voice interface. A central visual element morphs based on what's happening:

| Phase | What the user sees |
|---|---|
| `idle` | Mic button + "Hold to speak" hint |
| `listening` | Pulsing rings + "Listening…" |
| `thinking` | Breathing orb + "[Persona] is thinking…" + dots |
| `playing` | Waveform bars + response text in thread + Replay / Reply controls |

Conversation history scrolls up naturally in a message thread above the voice surface. No separate history screen needed — scrolling is sufficient.

---

## Tasks

### 1) Home / Persona Selection ✅
- Persona grid with emoji, name, mood chip
- "Hey Christopher" header
- Continue button (enabled after selection)

### 2) Unified Conversation Screen ✅
- Chat nav: back arrow + persona name
- Scrollable message thread (user bubbles right, AI bubbles left)
- Voice surface with 4 morphing phases (idle/listening/thinking/playing)
- Text panel (hidden by default, toggled)
- Bottom bar: "Type instead" toggle + "New session"

### 3) Crisis Detection & Overlay ✅
- Keyword detection on user text input
- Crisis overlay covers conversation (not a separate screen)
- Direct call buttons: Mom / Dad / 988
- "I'm okay — go back" button to dismiss

### 4) Accessibility + Polish
- [ ] WCAG AA color contrast on all text + buttons
- [ ] `aria-live` on voice surface for phase changes
- [ ] Keyboard-accessible controls (focus outlines)
- [ ] Touch targets ≥ 44×44px throughout

---

## Deliverables

- `apps/cogna/static/index.html` — unified voice surface conversation screen
- `apps/cogna/static/styles.css` — all new phase animations and layout styles

---

## Status

Core screens implemented. Accessibility pass remaining.
