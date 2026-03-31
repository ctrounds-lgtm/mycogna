"""
setup_hume.py

One-time setup script for Hume EVI integration with MyCogna.

What this does:
  1. Clones a Cogna's voice sample to a Hume custom voice
  2. Creates a Hume EVI config (language model: Claude, voice: cloned)
  3. Updates the Cogna record with the hume_voice_id
  4. Prints the HUME_CONFIG_ID to add to .env

Usage:
  python3 scripts/setup_hume.py --cogna-id cogna_f84405b488d0

Prerequisites:
  - HUME_API_KEY set in apps/cogna/.env
  - pip install hume httpx requests
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COGNA_DIR = ROOT / "apps" / "cogna"
DB_PATH = COGNA_DIR / "data" / "family_portal.json"

sys.path.insert(0, str(ROOT))

# Load env — root .env first, then apps/cogna/.env (same precedence as server)
from dotenv import load_dotenv
load_dotenv(dotenv_path=ROOT / ".env")
load_dotenv(dotenv_path=COGNA_DIR / ".env", override=False)

HUME_API_KEY = os.getenv("HUME_API_KEY", "")
if not HUME_API_KEY:
    print("ERROR: HUME_API_KEY not found.")
    print("Add it to either:")
    print(f"  {ROOT}/.env")
    print(f"  {COGNA_DIR}/.env")
    sys.exit(1)

HEADERS = {"X-Hume-Api-Key": HUME_API_KEY, "Content-Type": "application/json"}


def load_db():
    with open(DB_PATH) as f:
        return json.load(f)


def save_db(db):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2)


# ── Step 1: Clone voice ───────────────────────────────────────────────────────

def clone_voice(cogna: dict) -> str:
    """
    Upload the Cogna's voice sample to Hume and save it as a custom voice.
    Returns the Hume voice_id.
    """
    import requests

    voice_sample_rel = cogna.get("voice_sample")
    if not voice_sample_rel:
        print("ERROR: This Cogna has no voice_sample set.")
        sys.exit(1)

    voice_path = COGNA_DIR / voice_sample_rel
    if not voice_path.exists():
        print(f"ERROR: Voice sample not found: {voice_path}")
        sys.exit(1)

    print(f"\nStep 1: Cloning voice from {voice_path.name} ...")

    # ── 1a. Generate a TTS sample using the voice reference ──────────────────
    # Hume Octave TTS accepts a voice reference via the 'voice' parameter.
    # We use it to generate speech, which gives us a generation_id we can
    # save as a named custom voice.

    with open(voice_path, "rb") as f:
        audio_bytes = f.read()

    import base64
    audio_b64 = base64.b64encode(audio_bytes).decode()

    tts_payload = {
        "utterances": [
            {
                "text": "Hello. I am here for you.",
                "voice": {
                    "provider": "CUSTOM_VOICE",
                    "custom_voice": {
                        "name": f"temp_{cogna['id']}",
                        "base_voice": "ITO",
                        "parameter_model": "20241004-11parameter",
                        "parameters": {"gender": 95, "huskiness": 20},
                    }
                }
            }
        ],
        "format": {"type": "mp3"},
        "instant_mode": False,
    }

    # Try with the audio as a reference voice via the descriptions approach.
    # Hume voice cloning works through their TTS endpoint:
    # POST /v0/tts with a reference audio in the request.
    # The exact field name for voice reference files may require multipart upload.
    # See: https://dev.hume.ai/docs/voice/voice-cloning

    # ── Multipart approach ────────────────────────────────────────────────────
    tts_url = "https://api.hume.ai/v0/tts/file"
    headers_no_ct = {"X-Hume-Api-Key": HUME_API_KEY}  # no Content-Type for multipart

    # Determine MIME type
    suffix = voice_path.suffix.lower()
    mime = {"m4a": "audio/m4a", "mp3": "audio/mpeg", "wav": "audio/wav"}.get(suffix[1:], "audio/m4a")

    payload = {
        "utterances": json.dumps([{
            "text": "Hello, sweetheart. I love you so much and I'm always here for you.",
            "description": "Warm, maternal, gentle, loving female voice"
        }]),
        "format": json.dumps({"type": "wav"}),
    }

    files = {"sample": (voice_path.name, open(voice_path, "rb"), mime)}

    print("  Generating TTS with voice reference...")
    resp = requests.post(tts_url, headers=headers_no_ct, data=payload, files=files)

    if resp.status_code != 200:
        print(f"  TTS generation failed ({resp.status_code}): {resp.text[:300]}")
        print("\n  ALTERNATIVE: Clone your voice manually in the Hume dashboard at")
        print("  https://platform.hume.ai → Voices → + Add Voice")
        print("  Then add the voice_id to the Cogna via the portal.")
        sys.exit(1)

    # Extract generation_id from response headers or body
    generation_id = resp.headers.get("X-Hume-Generation-Id") or resp.headers.get("x-hume-generation-id")
    if not generation_id:
        # Try parsing from JSON if returned
        try:
            body = resp.json()
            generation_id = body.get("generation_id") or (body.get("generations") or [{}])[0].get("generation_id")
        except Exception:
            pass

    if not generation_id:
        print("  Could not extract generation_id from TTS response.")
        print(f"  Response headers: {dict(resp.headers)}")
        print(f"  Response body (first 500 chars): {resp.text[:500]}")
        print("\n  Please clone the voice manually at https://platform.hume.ai → Voices")
        sys.exit(1)

    print(f"  Generation ID: {generation_id}")

    # ── 1b. Save the generation as a named voice ──────────────────────────────
    voice_name = f"mycogna_{cogna['name'].lower().replace(' ', '_')}_{cogna['id'][-6:]}"
    print(f"  Saving as custom voice '{voice_name}'...")

    save_resp = requests.post(
        "https://api.hume.ai/v0/tts/voices",
        headers=HEADERS,
        json={"generation_id": generation_id, "name": voice_name},
    )

    if save_resp.status_code not in (200, 201):
        print(f"  Voice save failed ({save_resp.status_code}): {save_resp.text[:300]}")
        sys.exit(1)

    voice_id = save_resp.json().get("id")
    print(f"  Voice cloned successfully. voice_id: {voice_id}")
    return voice_id


# ── Step 2: Create EVI config ─────────────────────────────────────────────────

def create_evi_config(voice_id: str, cogna_name: str) -> str:
    """
    Create a Hume EVI configuration with Claude as the LLM and the cloned voice.
    Returns the config_id.
    """
    import requests

    print("\nStep 2: Creating EVI configuration...")

    config_payload = {
        "evi_version": "3",
        "name": f"MyCogna — {cogna_name}",
        "language_model": {
            "model_provider": "ANTHROPIC",
            "model_resource": "claude-sonnet-4-6",
        },
        "voice": {
            "provider": "CUSTOM_VOICE",
            "name": voice_id,
        },
    }

    resp = requests.post(
        "https://api.hume.ai/v0/evi/configs",
        headers=HEADERS,
        json=config_payload,
    )

    if resp.status_code not in (200, 201):
        print(f"  Config creation failed ({resp.status_code}): {resp.text[:400]}")
        sys.exit(1)

    config_id = resp.json().get("id")
    print(f"  EVI config created. config_id: {config_id}")
    return config_id


# ── Step 3: Update Cogna record ───────────────────────────────────────────────

def update_cogna(cogna_id: str, hume_voice_id: str):
    db = load_db()
    cogna = db["cognas"].get(cogna_id)
    if not cogna:
        print(f"ERROR: Cogna {cogna_id} not found in database.")
        sys.exit(1)
    cogna["hume_voice_id"] = hume_voice_id
    cogna["voice_backend"] = "hume"
    save_db(db)
    print(f"\nCogna '{cogna['name']}' updated with hume_voice_id.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Set up Hume EVI for a MyCogna Cogna")
    parser.add_argument("--cogna-id", required=True, help="Cogna ID from family_portal.json")
    args = parser.parse_args()

    db = load_db()
    cogna = db["cognas"].get(args.cogna_id)
    if not cogna:
        print(f"ERROR: Cogna '{args.cogna_id}' not found.")
        print("Available Cogna IDs:", list(db["cognas"].keys()))
        sys.exit(1)

    print(f"\nSetting up Hume EVI for Cogna: {cogna['name']} ({args.cogna_id})")
    print("=" * 60)

    voice_id = clone_voice(cogna)
    config_id = create_evi_config(voice_id, cogna["name"])
    update_cogna(args.cogna_id, voice_id)

    print("\n" + "=" * 60)
    print("SETUP COMPLETE")
    print("=" * 60)
    print(f"\nAdd this to apps/cogna/.env:")
    print(f"\n  HUME_CONFIG_ID={config_id}")
    print(f"\nThen restart the server.")
    print(f"\nVoice ID (stored in Cogna): {voice_id}")
    print(f"Config ID (add to .env):    {config_id}")


if __name__ == "__main__":
    main()
