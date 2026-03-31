#!/usr/bin/env python3
"""
One-time migration: family_portal.json + local uploads → Supabase.

Usage (run from the apps/cogna/ directory):
  SUPABASE_URL=https://xxx.supabase.co SUPABASE_SERVICE_KEY=your-service-role-key python3 scripts/migrate_to_supabase.py

What it does:
  1. Reads data/family_portal.json
  2. Inserts all users into Supabase users table
  3. For each cogna, uploads voice sample + photo to cogna-uploads Storage bucket
  4. Inserts cognas with Supabase CDN URLs for voice_sample and photo

Safe to re-run — existing rows are skipped with a warning, not duplicated.
"""
import json
import os
from pathlib import Path

from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "family_portal.json"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    raise SystemExit(
        "Error: set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables before running."
    )

sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

if not DB_PATH.exists():
    raise SystemExit(f"Error: {DB_PATH} not found. Run from the apps/cogna/ directory.")

with open(DB_PATH) as f:
    db = json.load(f)

print(f"Found {len(db['users'])} users and {len(db['cognas'])} cognas.\n")

# ── Migrate users ──────────────────────────────────────────────────────────────
print("Migrating users...")
for email, user in db["users"].items():
    row = {k: user[k] for k in
           ("email", "name", "password_salt", "password_hash",
            "setup_type", "child_access_code", "created_at")
           if k in user}
    try:
        sb.table("users").insert(row).execute()
        print(f"  ✓ user: {email}")
    except Exception as e:
        print(f"  ⚠ SKIP user {email}: {e}")

# ── Migrate cognas + upload files ─────────────────────────────────────────────
print("\nMigrating cognas...")
for cogna_id, cogna in db["cognas"].items():
    row = {k: cogna.get(k) for k in
           ("id", "owner_email", "name", "relationship", "term_of_endearment",
            "params", "voice_backend", "elevenlabs_voice_id", "hume_voice_id",
            "hume_consent", "last_tested_at", "created_at")}

    # Upload voice sample if present
    voice_url = None
    if cogna.get("voice_sample"):
        local = ROOT / cogna["voice_sample"]
        if local.exists():
            storage_path = f"{cogna_id}/{local.name}"
            try:
                with open(local, "rb") as fh:
                    sb.storage.from_("cogna-uploads").upload(
                        storage_path, fh.read(),
                        {"content-type": "audio/mp4", "upsert": "true"}
                    )
                voice_url = sb.storage.from_("cogna-uploads").get_public_url(storage_path)
                print(f"    ↑ voice: {local.name}")
            except Exception as e:
                print(f"    ⚠ voice upload failed: {e}")
        else:
            print(f"    ⚠ voice file not found locally: {local}")

    # Upload photo if present
    photo_url = None
    if cogna.get("photo"):
        local = ROOT / cogna["photo"]
        if local.exists():
            ext = local.suffix.lower()
            mime = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                    ".png": "image/png", ".webp": "image/webp"}.get(ext, "image/jpeg")
            storage_path = f"{cogna_id}/{local.name}"
            try:
                with open(local, "rb") as fh:
                    sb.storage.from_("cogna-uploads").upload(
                        storage_path, fh.read(),
                        {"content-type": mime, "upsert": "true"}
                    )
                photo_url = sb.storage.from_("cogna-uploads").get_public_url(storage_path)
                print(f"    ↑ photo: {local.name}")
            except Exception as e:
                print(f"    ⚠ photo upload failed: {e}")
        else:
            print(f"    ⚠ photo file not found locally: {local}")

    row["voice_sample"] = voice_url
    row["photo"] = photo_url

    try:
        sb.table("cognas").insert(row).execute()
        print(f"  ✓ cogna: {cogna_id} ({cogna['name']})")
    except Exception as e:
        print(f"  ⚠ SKIP cogna {cogna_id}: {e}")

print("\nMigration complete.")
print("Verify data at: https://app.supabase.com → Table Editor")
