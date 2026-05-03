-- MyCogna schema
-- Run once in Supabase SQL editor: https://app.supabase.com → SQL editor

-- Users
CREATE TABLE IF NOT EXISTS users (
  email             TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  password_salt     TEXT NOT NULL,
  password_hash     TEXT NOT NULL,
  setup_type        TEXT NOT NULL DEFAULT 'guardian',
  tier              TEXT NOT NULL DEFAULT 'A',
  child_access_code TEXT NOT NULL UNIQUE,
  password_reset_token   TEXT,
  password_reset_expires TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'A';

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
  tier         TEXT NOT NULL DEFAULT 'A',
  description  TEXT NOT NULL DEFAULT '',
  active       BOOLEAN NOT NULL DEFAULT true,
  created_by   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'A';

-- Story prompts — collaborators set the question shown to recorders
CREATE TABLE IF NOT EXISTS story_prompts (
  id           TEXT PRIMARY KEY,
  text         TEXT NOT NULL,
  active       BOOLEAN NOT NULL DEFAULT false,
  created_by   TEXT,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default system prompts (seed data — run once)
INSERT INTO story_prompts (id, text, active, created_by, created_at) VALUES
  ('sys-001', 'Where did you grow up, and what do you remember most about that place?',                    true, 'system', '2026-01-01 00:00:01+00'),
  ('sys-002', 'Tell me about the home you grew up in — what did it look, smell, and feel like?',           true, 'system', '2026-01-01 00:00:02+00'),
  ('sys-003', 'Who was the most influential person in your childhood, and why?',                           true, 'system', '2026-01-01 00:00:03+00'),
  ('sys-004', 'Describe a moment that changed the direction of your life.',                                true, 'system', '2026-01-01 00:00:04+00'),
  ('sys-005', 'What is the hardest thing you''ve ever been through, and what did it teach you?',          true, 'system', '2026-01-01 00:00:05+00'),
  ('sys-006', 'Tell me about a time you took a risk that surprised even you.',                             true, 'system', '2026-01-01 00:00:06+00'),
  ('sys-007', 'What work have you done that you''re most proud of, and why did it matter?',               true, 'system', '2026-01-01 00:00:07+00'),
  ('sys-008', 'Was there a moment when you knew what you were meant to do?',                               true, 'system', '2026-01-01 00:00:08+00'),
  ('sys-009', 'Tell me about a friendship that shaped who you are.',                                       true, 'system', '2026-01-01 00:00:09+00'),
  ('sys-010', 'How did you meet the most important person in your life?',                                  true, 'system', '2026-01-01 00:00:10+00'),
  ('sys-011', 'What do you know now that you wish you''d known at 25?',                                   true, 'system', '2026-01-01 00:00:11+00'),
  ('sys-012', 'What values do you hope the people who love you will carry forward?',                       true, 'system', '2026-01-01 00:00:12+00'),
  ('sys-013', 'What story do you most want your grandchildren to know?',                                   true, 'system', '2026-01-01 00:00:13+00'),
  ('sys-014', 'Describe a meal, a place, or a moment you never want to forget.',                           true, 'system', '2026-01-01 00:00:14+00'),
  ('sys-015', 'What made you laugh more than anything else in your life?',                                 true, 'system', '2026-01-01 00:00:15+00')
ON CONFLICT (id) DO NOTHING;

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

-- ─────────────────────────────────────────────
-- Migration: Storyteller user accounts
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS storyteller_users (
  id                     TEXT PRIMARY KEY,
  email                  TEXT NOT NULL UNIQUE,
  first_name             TEXT NOT NULL DEFAULT '',
  last_name              TEXT NOT NULL DEFAULT '',
  password_salt          TEXT NOT NULL,
  password_hash          TEXT NOT NULL,
  signup_code            TEXT REFERENCES promo_codes(code),
  password_reset_token   TEXT,
  password_reset_expires TIMESTAMPTZ,
  created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add name columns to existing tables
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS first_name TEXT NOT NULL DEFAULT '';
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS last_name TEXT NOT NULL DEFAULT '';

CREATE INDEX IF NOT EXISTS storyteller_users_email_idx ON storyteller_users(email);

-- Link recordings to accounts (nullable for pre-auth recordings)
ALTER TABLE story_recordings ADD COLUMN IF NOT EXISTS storyteller_user_id TEXT REFERENCES storyteller_users(id);

-- Migration: allow recordings without a promo code (users who signed up directly)
ALTER TABLE story_recordings ALTER COLUMN promo_code DROP NOT NULL;

-- Monthly usage tracking for AI Companion (D-tier)
CREATE TABLE IF NOT EXISTS usage_tracking (
  id          TEXT PRIMARY KEY,
  user_email  TEXT NOT NULL REFERENCES users(email) ON DELETE CASCADE,
  month       TEXT NOT NULL,  -- "YYYY-MM"
  minutes     REAL NOT NULL DEFAULT 0,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_email, month)
);

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
