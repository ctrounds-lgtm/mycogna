-- MyCogna schema
-- Run once in Supabase SQL editor: https://app.supabase.com → SQL editor
--
-- Auth architecture (as of 2026-05-05):
--   users            — unified auth table for ALL users (portal admins + storytellers)
--                      role column: 'portal_admin', 'storyteller', or 'both'
--   storyteller_users — storyteller app-data table (tier, managed, custom_prompts, FK anchor
--                       for story_recordings / memoir_sessions / chapters / book_bibles)
--                       auth columns on this table are DEPRECATED — auth is handled by users table

-- User sessions (persisted so sessions survive Railway restarts)
CREATE TABLE IF NOT EXISTS user_sessions (
  token      TEXT PRIMARY KEY,
  email      TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS user_sessions_email_idx ON user_sessions(email);

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

-- Travel & Adventure and Significant Challenges prompts (migration — run once)
INSERT INTO story_prompts (id, text, active, created_by, created_at, sort_order) VALUES
  ('sys-016', 'Tell me about a place that changed how you see the world.',                                 true, 'system', '2026-01-01 00:00:16+00', 16),
  ('sys-017', 'What is the most memorable journey you''ve ever taken?',                                   true, 'system', '2026-01-01 00:00:17+00', 17),
  ('sys-018', 'Was there a trip that didn''t go as planned — and what happened?',                         true, 'system', '2026-01-01 00:00:18+00', 18),
  ('sys-019', 'Tell me about a person you met while traveling who stayed with you.',                       true, 'system', '2026-01-01 00:00:19+00', 19),
  ('sys-020', 'Tell me about a time you faced something difficult and found your way through it.',         true, 'system', '2026-01-01 00:00:20+00', 20),
  ('sys-021', 'Was there a moment in your life that required more courage than you knew you had?',         true, 'system', '2026-01-01 00:00:21+00', 21),
  ('sys-022', 'What''s something you lost that taught you something important?',                          true, 'system', '2026-01-01 00:00:22+00', 22),
  ('sys-023', 'Tell me about a time when things didn''t go the way you''d hoped — and what came next.',  true, 'system', '2026-01-01 00:00:23+00', 23)
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

-- Migration: persist custom prompts per storyteller user (cross-device support)
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS custom_prompts JSONB NOT NULL DEFAULT '[]';

-- ─────────────────────────────────────────────
-- Memoir Writing Tool (Storyteller+ / Tier 2)
-- ─────────────────────────────────────────────

-- AI deepening sessions — one per recording the user chooses to deepen
CREATE TABLE IF NOT EXISTS memoir_sessions (
  id                   TEXT PRIMARY KEY,
  storyteller_user_id  TEXT NOT NULL REFERENCES storyteller_users(id) ON DELETE CASCADE,
  recording_id         TEXT NOT NULL REFERENCES story_recordings(id) ON DELETE CASCADE,
  messages             JSONB NOT NULL DEFAULT '[]',
  finished             BOOLEAN NOT NULL DEFAULT false,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS memoir_sessions_user_idx ON memoir_sessions(storyteller_user_id);

-- Book Bibles — Claude's assembled memoir outline (latest overwrites previous)
CREATE TABLE IF NOT EXISTS book_bibles (
  id                   TEXT PRIMARY KEY,
  storyteller_user_id  TEXT NOT NULL REFERENCES storyteller_users(id) ON DELETE CASCADE,
  content              TEXT NOT NULL DEFAULT '',
  assembled_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS book_bibles_user_idx ON book_bibles(storyteller_user_id);

-- Chapters — one row per chapter from the outline, editable
CREATE TABLE IF NOT EXISTS chapters (
  id                   TEXT PRIMARY KEY,
  storyteller_user_id  TEXT NOT NULL REFERENCES storyteller_users(id) ON DELETE CASCADE,
  book_bible_id        TEXT REFERENCES book_bibles(id),
  title                TEXT NOT NULL DEFAULT '',
  content              TEXT NOT NULL DEFAULT '',
  edit_messages        JSONB NOT NULL DEFAULT '[]',
  sort_order           INTEGER NOT NULL DEFAULT 0,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS chapters_user_idx ON chapters(storyteller_user_id);

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

-- ─────────────────────────────────────────────
-- Migration: tier-based routing (2026-05-04)
-- ─────────────────────────────────────────────

-- Add tier and managed flag to storyteller user accounts
-- tier: 'A'=Free, 'B'=Storyteller, 'C'=Storyteller+AI, 'D'=AI Companion
--       E-code invitees are stored as tier 'B' with managed=true
-- managed: true = institutional invitee (no AI features, no upgrade prompts)
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'A';
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS managed BOOLEAN NOT NULL DEFAULT false;

-- ─────────────────────────────────────────────
-- Migration: unified auth (2026-05-05)
-- Run once in Supabase SQL editor.
-- ─────────────────────────────────────────────

-- Add unified fields to the users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'portal_admin';
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name TEXT NOT NULL DEFAULT '';

-- child_access_code is only for portal admins; storyteller-only users won't have one
ALTER TABLE users ALTER COLUMN child_access_code DROP NOT NULL;

-- Migrate storyteller_users credentials into users.
-- If the email already exists (portal admin who also signed up as storyteller),
-- upgrade their role to 'both'. Otherwise insert as role='storyteller'.
INSERT INTO users (
  email,
  name,
  first_name,
  last_name,
  password_salt,
  password_hash,
  password_reset_token,
  password_reset_expires,
  role,
  child_access_code,
  created_at
)
SELECT
  su.email,
  TRIM(COALESCE(NULLIF(su.first_name, ''), '') || ' ' || COALESCE(NULLIF(su.last_name, ''), '')),
  su.first_name,
  su.last_name,
  su.password_salt,
  su.password_hash,
  su.password_reset_token,
  su.password_reset_expires,
  'storyteller',
  NULL,
  su.created_at
FROM storyteller_users su
ON CONFLICT (email) DO UPDATE SET
  role = 'both',
  first_name = EXCLUDED.first_name,
  last_name = EXCLUDED.last_name;
-- Note: existing portal admin password is preserved on conflict (we don't overwrite password_hash)

-- ─────────────────────────────────────────────
-- Migration: per-account prompt ownership (2026-05-06)
-- Run once in Supabase SQL editor.
-- ─────────────────────────────────────────────

-- Add owner column: NULL = system prompt (shared, not deletable), email = portal user's custom prompt
ALTER TABLE story_prompts ADD COLUMN IF NOT EXISTS portal_user_email TEXT REFERENCES users(email) ON DELETE CASCADE;

-- ─────────────────────────────────────────────
-- Migration: per-user system prompt hiding (2026-05-06)
-- Run once in Supabase SQL editor.
-- ─────────────────────────────────────────────

-- Array of system prompt IDs the portal user has hidden from their storytellers
ALTER TABLE users ADD COLUMN IF NOT EXISTS hidden_prompt_ids JSONB NOT NULL DEFAULT '[]';

-- ─────────────────────────────────────────────
-- Migration: Stripe billing columns (2026-05-18)
-- Run once in Supabase SQL editor.
-- ─────────────────────────────────────────────

-- Stripe billing columns for individual storyteller subscriptions (B/C/D tiers)
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT;
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'none';
ALTER TABLE storyteller_users ADD COLUMN IF NOT EXISTS subscription_period_end TIMESTAMPTZ;

-- Stripe billing columns for portal admin subscriptions (D/E/F tiers)
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS stripe_seat_item_id TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'none';
ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_period_end TIMESTAMPTZ;

-- ─────────────────────────────────────────────
-- Migration: Collection book builder (2026-05-24)
-- Run once in Supabase SQL editor.
-- ─────────────────────────────────────────────

-- Collection-level book bibles (F-tier combined archive, keyed to portal user)
CREATE TABLE IF NOT EXISTS collection_book_bibles (
  id              TEXT PRIMARY KEY,
  portal_user_id  TEXT NOT NULL,
  content         TEXT,
  assembled_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS collection_book_bibles_user_idx ON collection_book_bibles(portal_user_id);

-- Collection-level chapters
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
CREATE INDEX IF NOT EXISTS collection_chapters_user_idx ON collection_chapters(portal_user_id);


-- Migration: Add chapter_outline and whats_missing to collection_book_bibles (2026-05-24)
-- Run once in Supabase SQL editor.
ALTER TABLE collection_book_bibles ADD COLUMN IF NOT EXISTS chapter_outline TEXT;
ALTER TABLE collection_book_bibles ADD COLUMN IF NOT EXISTS whats_missing TEXT;

-- Migration: Add chapter_outline and whats_missing to book_bibles (2026-05-24)
-- Run once in Supabase SQL editor.
ALTER TABLE book_bibles ADD COLUMN IF NOT EXISTS chapter_outline TEXT;
ALTER TABLE book_bibles ADD COLUMN IF NOT EXISTS whats_missing TEXT;

-- ─────────────────────────────────────────────
-- Migration: gift subscriptions (2026-06-01)
-- Run once in Supabase SQL editor.
-- ─────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gift_subscriptions (
  id                         TEXT PRIMARY KEY,
  code                       TEXT NOT NULL UNIQUE,
  tier                       TEXT NOT NULL,
  duration_months            INTEGER NOT NULL,
  price_paid_cents           INTEGER NOT NULL,
  purchaser_name             TEXT NOT NULL,
  purchaser_email            TEXT NOT NULL,
  recipient_name             TEXT,
  recipient_email            TEXT,
  stripe_payment_intent_id   TEXT,
  stripe_checkout_session_id TEXT,
  paid_at                    TIMESTAMPTZ,
  redeemed_by_email          TEXT,
  redeemed_at                TIMESTAMPTZ,
  created_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS gift_subscriptions_code_idx ON gift_subscriptions(code);
CREATE INDEX IF NOT EXISTS gift_subscriptions_purchaser_idx ON gift_subscriptions(purchaser_email);

-- Gift tracking columns on users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS gift_expires_at TIMESTAMPTZ;
ALTER TABLE users ADD COLUMN IF NOT EXISTS gift_code TEXT;
