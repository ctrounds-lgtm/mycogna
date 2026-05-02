-- MyCogna schema
-- Run once in Supabase SQL editor: https://app.supabase.com → SQL editor

-- Users
CREATE TABLE IF NOT EXISTS users (
  email             TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  password_salt     TEXT NOT NULL,
  password_hash     TEXT NOT NULL,
  setup_type        TEXT NOT NULL DEFAULT 'guardian',
  child_access_code TEXT NOT NULL UNIQUE,
  password_reset_token   TEXT,
  password_reset_expires TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
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
  hume_config_id      TEXT,
  voice_sample        TEXT,
  photo               TEXT,
  hume_consent        JSONB,
  last_tested_at      TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS cognas_owner_email_idx ON cognas(owner_email);

-- Conversation sessions
CREATE TABLE IF NOT EXISTS conversation_sessions (
  id               TEXT PRIMARY KEY,
  primary_cogna_id TEXT NOT NULL,
  cogna_ids        TEXT[] NOT NULL,
  voice_names      TEXT[] NOT NULL,
  transcript       JSONB NOT NULL DEFAULT '[]',
  duration_seconds INT NOT NULL DEFAULT 0,
  saved_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS sessions_primary_cogna_idx ON conversation_sessions(primary_cogna_id);

-- Storage bucket for voice samples and photos
-- The bucket is created via the SQL below; verify it appears in Supabase Storage UI as Public.
INSERT INTO storage.buckets (id, name, public)
VALUES ('cogna-uploads', 'cogna-uploads', true)
ON CONFLICT (id) DO NOTHING;

-- Allow server-side (service role) uploads
CREATE POLICY "Allow service uploads"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'cogna-uploads');

-- Allow anyone to read (public CDN)
CREATE POLICY "Allow public reads"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'cogna-uploads');


-- ─────────────────────────────────────────────
-- Migration: add sort_order to story_prompts
-- ─────────────────────────────────────────────
ALTER TABLE story_prompts ADD COLUMN IF NOT EXISTS sort_order INTEGER NOT NULL DEFAULT 0;

-- ─────────────────────────────────────────────
-- Storyteller feature (Tier 1)
-- ─────────────────────────────────────────────

-- Promo codes — gate access to the story capture flow
CREATE TABLE IF NOT EXISTS promo_codes (
  code         TEXT PRIMARY KEY,
  description  TEXT NOT NULL DEFAULT '',
  active       BOOLEAN NOT NULL DEFAULT true,
  created_by   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Story prompts — collaborators set the question shown to recorders
CREATE TABLE IF NOT EXISTS story_prompts (
  id           TEXT PRIMARY KEY,
  text         TEXT NOT NULL,
  active       BOOLEAN NOT NULL DEFAULT false,
  created_by   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS story_prompts_active_idx ON story_prompts(active);

-- Story recordings — one row per submitted recording
CREATE TABLE IF NOT EXISTS story_recordings (
  id           TEXT PRIMARY KEY,
  promo_code   TEXT NOT NULL REFERENCES promo_codes(code),
  prompt_id    TEXT REFERENCES story_prompts(id),
  transcript   TEXT NOT NULL DEFAULT '',
  audio_url    TEXT NOT NULL DEFAULT '',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS story_recordings_promo_idx ON story_recordings(promo_code);

-- Storage bucket for story audio files
INSERT INTO storage.buckets (id, name, public)
VALUES ('story-audio', 'story-audio', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "Allow story audio uploads"
  ON storage.objects FOR INSERT
  WITH CHECK (bucket_id = 'story-audio');

CREATE POLICY "Allow story audio reads"
  ON storage.objects FOR SELECT
  USING (bucket_id = 'story-audio');
