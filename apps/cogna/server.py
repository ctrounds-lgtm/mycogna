"""FastAPI server for MyCogna.

App surfaces:
1) Child/user app at `/`
2) Guardian portal at `/portal`

Architecture:
- A Cogna IS a single voice/persona (Mom is one Cogna, Kenzie is another, Dillon is a third).
- Guardian creates Cognas; each has 5 relational parameter sliders + name/relationship/term_of_endearment.
- One child_access_code per guardian account unlocks all their Cognas.
- Multi-voice conversations: selected Cognas respond to user AND to each other.
- Session journals saved to Supabase conversation_sessions table.
- Data storage: Supabase (PostgreSQL + Storage). Falls back to local JSON when SUPABASE_URL is unset.
"""

import hashlib
import json
import os
import secrets
import shutil
import string
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import resend as resend_sdk
except ImportError:
    resend_sdk = None


# ----------------------------------------------------
# Config / Paths
# ----------------------------------------------------
ROOT = Path(__file__).resolve().parent

load_dotenv(dotenv_path=ROOT.parent.parent / ".env")
load_dotenv(dotenv_path=ROOT / ".env", override=False)

CONFIG_PATH = ROOT / "config.json"
if not CONFIG_PATH.exists():
    raise RuntimeError(
        "Missing config.json. Copy apps/cogna/config.sample.json -> apps/cogna/config.json"
    )

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

# Audio cache — ephemeral on Railway, fine for TTS test playback
CACHE_DIR = Path(os.getenv("CACHE_DIR", tempfile.gettempdir())) / "cogna_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

VOICE_REFERENCE_DIR = ROOT.parent / CONFIG.get("voice_reference_dir", "voices")

# Local fallback paths (used when SUPABASE_URL is not set)
PORTAL_DATA_DIR = ROOT / "data"
PORTAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
PORTAL_UPLOAD_DIR = PORTAL_DATA_DIR / "family_uploads"
PORTAL_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
PORTAL_DB_PATH = PORTAL_DATA_DIR / "family_portal.json"
SESSIONS_DIR = PORTAL_DATA_DIR / "sessions"
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
STORY_RECORDINGS_DIR = PORTAL_DATA_DIR / "story_recordings"
STORY_RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

SESSIONS: Dict[str, str] = {}  # unified token → email (portal admins + storytellers)

# Claude API setup
CLAUDE_API_KEY = os.getenv(CONFIG.get("claude_api_key_env", "CLAUDE_API_KEY"))
if not CLAUDE_API_KEY:
    raise RuntimeError(f"Missing API key: {CONFIG.get('claude_api_key_env')}")

client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# OpenAI (Whisper) setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai_client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI) else None

# Hume EVI setup
HUME_API_KEY = os.getenv("HUME_API_KEY", "")
HUME_SECRET_KEY = os.getenv("HUME_SECRET_KEY", "")
HUME_CONFIG_ID = os.getenv("HUME_CONFIG_ID", "")

# Resend (email) setup
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_FROM = os.getenv("RESEND_FROM", "MyCogna <noreply@mycogna.org>")
APP_URL = os.getenv("APP_URL", "https://mycogna.org")
COMPANION_MONTHLY_MINUTES = int(os.getenv("COMPANION_MONTHLY_MINUTES", "60"))
if resend_sdk and RESEND_API_KEY:
    resend_sdk.api_key = RESEND_API_KEY

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")

supabase = None
if SUPABASE_URL and SUPABASE_SERVICE_KEY:
    try:
        from supabase import create_client, Client as SupabaseClient
        supabase: SupabaseClient = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    except Exception as e:
        print(f"Warning: Supabase init failed: {e}. Falling back to local JSON.")


# ----------------------------------------------------
# Pydantic models
# ----------------------------------------------------

class FamilyRegisterRequest(BaseModel):
    email: str
    password: str
    name: str
    setup_type: str = "guardian"  # "guardian" or "self"
    tier: str = "B"  # B=Unlimited, C=AI Assisted, D=AI Companion, E=Legacy, F=Legacy+Book


class FamilyLoginRequest(BaseModel):
    email: str
    password: str


class PasswordResetRequest(BaseModel):
    email: str


class PasswordResetConfirm(BaseModel):
    token: str
    password: str


class CognaCreateRequest(BaseModel):
    name: str
    relationship: str = ""
    term_of_endearment: str = ""
    params: Dict[str, Any] = {}
    voice_backend: str = "tts"
    elevenlabs_voice_id: Optional[str] = None
    hume_voice_id: Optional[str] = None
    hume_config_id: Optional[str] = None


class CognaUpdateRequest(BaseModel):
    name: Optional[str] = None
    relationship: Optional[str] = None
    term_of_endearment: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    voice_backend: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    hume_voice_id: Optional[str] = None
    hume_config_id: Optional[str] = None


class TestVoiceRequest(BaseModel):
    message: str


class ChildAccessRequest(BaseModel):
    access_code: str


class EviSessionRequest(BaseModel):
    cogna_id: str


class ConverseTurn(BaseModel):
    cogna_ids: List[str]
    message: Optional[str] = None
    history: List[Dict] = []


class SaveSessionRequest(BaseModel):
    cogna_ids: List[str]
    transcript: List[Dict]
    voice_names: List[str]
    duration_seconds: int = 0


class StoryValidateRequest(BaseModel):
    user_code: str


class StoryPromptCreate(BaseModel):
    text: str


class PromptsReorderRequest(BaseModel):
    ids: List[str]


class PromoCodeCreate(BaseModel):
    description: str = ""
    tier: str = "A"


class StorySignupRequest(BaseModel):
    user_code: Optional[str] = None
    email: str
    password: str
    first_name: str = ""
    last_name: str = ""


class StoryLoginRequest(BaseModel):
    email: str
    password: str


class StoryPasswordResetRequest(BaseModel):
    email: str


class StoryPasswordResetConfirm(BaseModel):
    token: str
    password: str

class StoryCustomPromptRequest(BaseModel):
    text: str
    category: Optional[str] = None

class MemoirDeepenStartRequest(BaseModel):
    recording_id: str

class MemoirDeepenChatRequest(BaseModel):
    session_id: str
    message: str

class MemoirDeepenFinishRequest(BaseModel):
    session_id: str

class MemoirChapterRequest(BaseModel):
    title: str
    content: str = ""
    sort_order: int = 0
    book_bible_id: Optional[str] = None

class MemoirChapterEditRequest(BaseModel):
    message: str


# ----------------------------------------------------
# FastAPI app
# ----------------------------------------------------
app = FastAPI(
    title="MyCogna",
    description="Voice companion app with multi-Cogna support.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/portal")
def portal():
    return FileResponse(ROOT / "static" / "portal.html")


@app.get("/companion")
def companion():
    return FileResponse(ROOT / "static" / "companion.html")


@app.get("/storyteller")
def storyteller():
    return FileResponse(ROOT / "static" / "storyteller.html")


@app.get("/memoir")
def memoir():
    return FileResponse(ROOT / "static" / "memoir.html")


@app.get("/portal/memoir")
def portal_memoir_page():
    return FileResponse(ROOT / "static" / "portal-memoir.html")


@app.get("/signup")
def signup_page():
    return FileResponse(ROOT / "static" / "signup.html")


@app.get("/portal/signup")
def portal_signup_page():
    return FileResponse(ROOT / "static" / "portal-signup.html")


@app.get("/login")
def login_page():
    return FileResponse(ROOT / "static" / "login.html")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ----------------------------------------------------
# Audio serving (local fallback only)
# ----------------------------------------------------

@app.get("/audio/{filename}")
def serve_audio(filename: str):
    audio_path = CACHE_DIR / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    if filename.endswith(".mp3"):
        media_type = "audio/mpeg"
    elif filename.endswith(".aiff"):
        media_type = "audio/aiff"
    else:
        media_type = "audio/wav"
    return FileResponse(audio_path, media_type=media_type)


# ----------------------------------------------------
# Auth endpoints: /api/auth/*
# ----------------------------------------------------

@app.post("/api/auth/register")
def auth_register(payload: FamilyRegisterRequest):
    email = payload.email.strip().lower()
    existing = _get_user(email)

    setup_type = payload.setup_type if payload.setup_type in {"guardian", "self"} else "guardian"
    tier = payload.tier if payload.tier in {"A", "B", "C", "D", "E", "F"} else "A"

    if existing:
        if existing.get("role") in ("portal_admin", "both"):
            raise HTTPException(status_code=400, detail="Account already exists")
        # Existing storyteller upgrading to portal — upgrade role, set new password
        salt = secrets.token_hex(8)
        password_hash = _hash_password(payload.password, salt)
        access_code = _generate_child_access_code(tier)
        _update_user(email, {
            "role": "both",
            "name": payload.name.strip(),
            "setup_type": setup_type,
            "tier": tier,
            "child_access_code": access_code,
            "password_salt": salt,
            "password_hash": password_hash,
        })
        user = _get_user(email)
        token = _create_session(email)
        return {"token": token, "user": _public_user(user)}

    salt = secrets.token_hex(8)
    password_hash = _hash_password(payload.password, salt)
    user = {
        "email": email,
        "name": payload.name.strip(),
        "password_salt": salt,
        "password_hash": password_hash,
        "setup_type": setup_type,
        "tier": tier,
        "child_access_code": _generate_child_access_code(tier),
        "created_at": _utc_now(),
    }
    _create_user(user)
    _update_user(email, {"role": "portal_admin", "first_name": "", "last_name": ""})
    token = _create_session(email)
    return {"token": token, "user": _public_user(user)}


@app.post("/api/auth/login")
def auth_login(payload: FamilyLoginRequest):
    email = payload.email.strip().lower()
    user = _get_user(email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    expected_hash = _hash_password(payload.password, user["password_salt"])
    if expected_hash != user["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = _create_session(email)
    return {"token": token, "user": _public_user(user)}


@app.get("/api/auth/me")
def auth_me(authorization: Optional[str] = Header(default=None)):
    user = _auth_user(authorization)
    return {"user": _public_user(user)}


@app.get("/api/auth/usage")
def get_usage(authorization: Optional[str] = Header(default=None)):
    user = _auth_user(authorization)
    month = _current_month()
    used = _get_usage(user["email"], month)
    return {
        "month": month,
        "used_minutes": round(used, 1),
        "cap_minutes": COMPANION_MONTHLY_MINUTES,
        "remaining_minutes": max(0.0, round(COMPANION_MONTHLY_MINUTES - used, 1)),
        "percent_used": min(100, round((used / COMPANION_MONTHLY_MINUTES) * 100, 1)),
    }


@app.get("/api/auth/me/access-code")
def get_access_code(authorization: Optional[str] = Header(default=None)):
    user = _auth_user(authorization)
    return {"access_code": user.get("child_access_code", "")}


@app.post("/api/auth/request-reset")
def auth_request_reset(payload: PasswordResetRequest):
    from datetime import timedelta
    email = payload.email.strip().lower()
    user = _get_user(email)
    # Always return success to avoid leaking whether an account exists
    if not user:
        return {"ok": True}

    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    _update_user(email, {"password_reset_token": token, "password_reset_expires": expires})

    reset_url = f"{APP_URL}/portal?reset_token={token}"
    if resend_sdk and RESEND_API_KEY:
        resend_sdk.Emails.send({
            "from": RESEND_FROM,
            "to": [email],
            "subject": "Reset your MyCogna password",
            "html": (
                f"<p>Hi {user.get('name', '')}!</p>"
                f"<p>Click the link below to reset your MyCogna password. "
                f"This link expires in 1 hour.</p>"
                f"<p><a href='{reset_url}'>{reset_url}</a></p>"
                f"<p>If you didn't request this, you can ignore this email.</p>"
            ),
        })
    else:
        print(f"[DEV] Password reset link for {email}: {reset_url}")

    return {"ok": True}


@app.post("/api/auth/reset-password")
def auth_reset_password(payload: PasswordResetConfirm):
    # Find user by token
    if supabase:
        r = supabase.table("users").select("*").eq("password_reset_token", payload.token).limit(1).execute()
        user = r.data[0] if r.data else None
    else:
        db = _load_db()
        user = next((u for u in db["users"].values() if u.get("password_reset_token") == payload.token), None)

    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    expires_str = user.get("password_reset_expires")
    if not expires_str:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    expires = datetime.fromisoformat(expires_str)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")

    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    new_salt = secrets.token_hex(8)
    new_hash = _hash_password(payload.password, new_salt)
    _update_user(user["email"], {
        "password_salt": new_salt,
        "password_hash": new_hash,
        "password_reset_token": None,
        "password_reset_expires": None,
    })

    return {"ok": True}


# ----------------------------------------------------
# Cogna CRUD endpoints
# ----------------------------------------------------

@app.get("/api/cognas")
def list_cognas(authorization: Optional[str] = Header(default=None)):
    user = _auth_user(authorization)
    cognas = _list_cognas(user["email"])
    return {"cognas": cognas}


@app.post("/api/cognas")
def create_cogna(
    payload: CognaCreateRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)

    cogna_id = "cogna_" + secrets.token_hex(6)
    default_params = {"warmth": 50, "validation": 50, "tone": 50, "structure": 50, "stance": 50}
    params = {**default_params}
    for k, v in payload.params.items():
        params[k] = max(0, min(100, v)) if isinstance(v, int) else v

    cogna = {
        "id": cogna_id,
        "owner_email": user["email"],
        "name": payload.name.strip(),
        "relationship": payload.relationship.strip(),
        "term_of_endearment": payload.term_of_endearment.strip(),
        "params": params,
        "voice_backend": payload.voice_backend,
        "elevenlabs_voice_id": payload.elevenlabs_voice_id,
        "hume_voice_id": payload.hume_voice_id,
        "hume_config_id": payload.hume_config_id,
        "voice_sample": None,
        "photo": None,
        "hume_consent": None,
        "last_tested_at": None,
        "created_at": _utc_now(),
    }

    _create_cogna(cogna)
    return {"cogna": cogna}


@app.get("/api/cognas/{cogna_id}")
def get_cogna_detail(
    cogna_id: str,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)
    cogna = _get_cogna(cogna_id)
    if cogna["owner_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return {"cogna": cogna}


@app.put("/api/cognas/{cogna_id}")
def update_cogna(
    cogna_id: str,
    payload: CognaUpdateRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)
    cogna = _get_cogna(cogna_id)
    if cogna["owner_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    updates: Dict[str, Any] = {}
    if payload.name is not None:
        updates["name"] = payload.name.strip()
    if payload.relationship is not None:
        updates["relationship"] = payload.relationship.strip()
    if payload.term_of_endearment is not None:
        updates["term_of_endearment"] = payload.term_of_endearment.strip()
    if payload.params is not None:
        existing_params = cogna.get("params", {})
        for k, v in payload.params.items():
            existing_params[k] = max(0, min(100, v)) if isinstance(v, int) else v
        updates["params"] = existing_params
    if payload.voice_backend is not None:
        updates["voice_backend"] = payload.voice_backend
    if payload.elevenlabs_voice_id is not None:
        updates["elevenlabs_voice_id"] = payload.elevenlabs_voice_id
    if payload.hume_voice_id is not None:
        updates["hume_voice_id"] = payload.hume_voice_id
    if payload.hume_config_id is not None:
        updates["hume_config_id"] = payload.hume_config_id

    if updates:
        _update_cogna(cogna_id, updates)
        cogna.update(updates)

    return {"cogna": cogna}


@app.delete("/api/cognas/{cogna_id}")
def delete_cogna(
    cogna_id: str,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)
    cogna = _get_cogna(cogna_id)
    if cogna["owner_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    _delete_cogna(cogna_id)
    return {"ok": True}


@app.post("/api/cognas/{cogna_id}/hume-consent")
def record_hume_consent(
    cogna_id: str,
    authorization: Optional[str] = Header(default=None),
):
    """
    Record that the guardian has explicitly consented to Hume AI processing audio
    for this Cogna. Required before EVI sessions can be started.
    """
    user = _auth_user(authorization)
    cogna = _get_cogna(cogna_id)
    if cogna["owner_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    consent = {
        "accepted": True,
        "accepted_at": _utc_now(),
        "guardian_email": user["email"],
    }
    _update_cogna(cogna_id, {"hume_consent": consent})
    return {"ok": True}


@app.post("/api/cognas/{cogna_id}/sample")
async def upload_cogna_sample(
    cogna_id: str,
    authorization: Optional[str] = Header(default=None),
    file: UploadFile = File(...),
):
    user = _auth_user(authorization)
    cogna = _get_cogna(cogna_id)
    if cogna["owner_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    _validate_upload(file.filename, {".mp3", ".wav", ".m4a", ".webm", ".mp4"})
    saved = _save_cogna_upload(cogna_id, "voice", file)
    _update_cogna(cogna_id, {"voice_sample": saved})
    return {"ok": True, "voice_sample": saved}


@app.post("/api/cognas/{cogna_id}/photo")
async def upload_cogna_photo(
    cogna_id: str,
    authorization: Optional[str] = Header(default=None),
    file: UploadFile = File(...),
):
    user = _auth_user(authorization)
    cogna = _get_cogna(cogna_id)
    if cogna["owner_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    _validate_upload(file.filename, {".png", ".jpg", ".jpeg", ".webp"})
    saved = _save_cogna_upload(cogna_id, "photo", file)
    _update_cogna(cogna_id, {"photo": saved})
    return {"ok": True, "photo": saved}


@app.post("/api/cognas/{cogna_id}/test")
def test_cogna_voice(
    cogna_id: str,
    payload: TestVoiceRequest,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)
    cogna = _get_cogna(cogna_id)
    if cogna["owner_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    text = payload.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Enter a test message")

    try:
        audio_url = _generate_cogna_audio(cogna, text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio generation failed: {type(e).__name__}: {e}")
    _update_cogna(cogna_id, {"last_tested_at": _utc_now()})
    return {"ok": True, "audio_url": audio_url}


# ----------------------------------------------------
# Child access endpoint
# ----------------------------------------------------

@app.post("/api/child/access")
def child_access(payload: ChildAccessRequest):
    code = payload.access_code.strip().upper()
    owner = _find_user_by_code(code)

    if not owner:
        raise HTTPException(status_code=404, detail="Access code not found")

    all_cognas = _list_cognas(owner["email"])
    cognas = [
        {
            "id": c["id"],
            "name": c["name"],
            "relationship": c.get("relationship", ""),
            "photo": c.get("photo"),
            "has_voice": bool(c.get("voice_sample") or c.get("elevenlabs_voice_id")),
        }
        for c in all_cognas
    ]

    return {"owner_name": owner.get("name", ""), "cognas": cognas}


# ----------------------------------------------------
# Hume EVI session endpoint
# ----------------------------------------------------

@app.post("/api/evi/session")
async def evi_session(payload: EviSessionRequest):
    """
    Return everything the browser needs to open an EVI WebSocket directly with Hume.
    Generates a short-lived access token so the raw API key never touches the browser.
    Falls back to returning the api_key directly if no secret key is configured.
    """
    if not HUME_API_KEY:
        raise HTTPException(status_code=503, detail="Hume is not configured on this server")

    cogna = _get_cogna(payload.cogna_id)

    # Check monthly usage cap before issuing a session token
    owner_email = cogna.get("owner_email", "")
    used = 0.0
    if owner_email:
        month = _current_month()
        try:
            used = _get_usage(owner_email, month)
        except Exception:
            used = 0.0
        if used >= COMPANION_MONTHLY_MINUTES:
            raise HTTPException(
                status_code=402,
                detail=f"Monthly conversation limit reached ({COMPANION_MONTHLY_MINUTES} minutes). "
                       f"Usage resets on the 1st of next month.",
            )

    # Require guardian consent before starting any EVI session
    if not (cogna.get("hume_consent") or {}).get("accepted"):
        raise HTTPException(
            status_code=403,
            detail="Guardian consent is required before using Hume voice. Please enable it in the guardian portal."
        )

    system_prompt = _cogna_voice_prompt(cogna)

    # Only use a custom voice ID if it has been verified to exist on this account.
    # Stale IDs from old accounts cause Hume to reject the session immediately.
    custom_voice_id = cogna.get("hume_voice_id") or None

    # Fall back to a named Hume built-in voice keyed by relationship
    relationship = cogna.get("relationship", "").lower()
    default_voice_map = {
        "mother": "KORA",
        "father": "DACHER",
        "friend": "ITO",
        "sister": "STELLA",
        "brother": "FINN",
    }
    default_voice = default_voice_map.get(relationship, "KORA")

    # Generate a short-lived access token if we have a secret key
    access_token = None
    if HUME_SECRET_KEY:
        try:
            import base64
            import httpx as _httpx
            encoded = base64.b64encode(f"{HUME_API_KEY}:{HUME_SECRET_KEY}".encode()).decode()
            resp = _httpx.post(
                "https://api.hume.ai/oauth2-cc/token",
                headers={"Authorization": f"Basic {encoded}"},
                data={"grant_type": "client_credentials"},
                timeout=10,
            )
            resp.raise_for_status()
            access_token = resp.json().get("access_token")
        except Exception:
            pass  # Fall back to api_key

    return {
        "access_token": access_token,
        "api_key": None if access_token else HUME_API_KEY,
        "config_id": cogna.get("hume_config_id") or HUME_CONFIG_ID or None,
        "system_prompt": system_prompt,
        "voice_id": custom_voice_id,
        "default_voice": default_voice,
        "usage": {
            "used_minutes": round(used, 1),
            "cap_minutes": COMPANION_MONTHLY_MINUTES,
            "warning": used >= COMPANION_MONTHLY_MINUTES * 0.8,
        },
    }


# ----------------------------------------------------
# Multi-voice conversation endpoint
# ----------------------------------------------------

@app.post("/api/converse")
async def converse(
    cogna_ids: str = Form(...),
    history: str = Form("[]"),
    message: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
):
    try:
        cogna_ids_list: List[str] = json.loads(cogna_ids)
        history_list: List[Dict] = json.loads(history)
        payload = ConverseTurn(cogna_ids=cogna_ids_list, message=message, history=history_list)

        incoming_message = payload.message
        if audio and not incoming_message:
            incoming_message = _transcribe_audio(audio)
        if not incoming_message:
            raise HTTPException(status_code=400, detail="Provide message text or audio")

        # Crisis keyword check
        crisis_keywords = ["hurt myself", "kill myself", "suicide", "end my life", "don't want to live"]
        lower_msg = incoming_message.lower()
        if any(kw in lower_msg for kw in crisis_keywords):
            return {
                "crisis": True,
                "message": "It sounds like you might be going through something really hard. Please reach out to the 988 Suicide & Crisis Lifeline by calling or texting 988.",
            }

        if not payload.cogna_ids:
            raise HTTPException(status_code=400, detail="Provide at least one cogna_id")

        cognas = []
        for cid in payload.cogna_ids:
            cognas.append(_get_cogna(cid))

        other_names_map = {
            c["id"]: [x["name"] for x in cognas if x["id"] != c["id"]]
            for c in cognas
        }

        turn_responses = []
        turn_context = []

        for cogna in cognas:
            system_prompt = _cogna_voice_prompt(cogna)

            if len(cognas) > 1:
                others = other_names_map[cogna["id"]]
                others_str = " and ".join(others)
                system_prompt += (
                    f"\n\nYou are in a group conversation with {others_str}. "
                    "Respond to the user and authentically to what the others have shared. "
                    "You may affirm, gently push back, or add your own perspective. "
                    "Keep your response warm and concise — 2 to 4 sentences."
                )

            messages = []
            for entry in payload.history:
                role = "user" if entry.get("role") == "user" else "assistant"
                messages.append({"role": role, "content": entry.get("content", "")})

            combined = incoming_message
            if turn_context:
                prior = "\n".join(f"{r['role']}: {r['content']}" for r in turn_context)
                combined = f"{incoming_message}\n\n[Others in this conversation have already responded:\n{prior}]"

            messages.append({"role": "user", "content": combined})

            response_text = _generate_text_response(system_prompt, messages)
            audio_url = _generate_cogna_audio(cogna, response_text)

            turn_responses.append({
                "cogna_id": cogna["id"],
                "cogna_name": cogna["name"],
                "text": response_text,
                "audio_url": audio_url,
            })
            turn_context.append({"role": cogna["name"], "content": response_text})

        transcript_entry = [{"role": "user", "content": incoming_message}] + turn_context

        return {"turn": turn_responses, "transcript_entry": transcript_entry}

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ----------------------------------------------------
# Session journal endpoints
# ----------------------------------------------------

@app.post("/api/sessions")
def save_session(payload: SaveSessionRequest):
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    session_id = f"session_{timestamp}"
    primary_cogna_id = payload.cogna_ids[0] if payload.cogna_ids else "multi"

    _save_session(
        session_id=session_id,
        primary_cogna_id=primary_cogna_id,
        cogna_ids=payload.cogna_ids,
        voice_names=payload.voice_names,
        transcript=payload.transcript,
        duration_seconds=payload.duration_seconds,
    )

    # Record usage against the cogna owner's account
    if payload.cogna_ids and payload.duration_seconds > 0:
        try:
            cogna = _get_cogna(payload.cogna_ids[0])
            owner_email = cogna.get("owner_email", "")
            if owner_email:
                minutes = payload.duration_seconds / 60.0
                _add_usage(owner_email, _current_month(), minutes)
        except Exception:
            pass  # Never fail a session save due to usage tracking

    return {"ok": True, "session_id": session_id}


@app.get("/api/sessions/{cogna_id}")
def list_sessions(
    cogna_id: str,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)
    cogna = _get_cogna(cogna_id)
    if cogna["owner_email"] != user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")

    sessions = _list_sessions(cogna_id)
    return {"sessions": sessions}


# ----------------------------------------------------
# Storyteller endpoints (no auth required for capture)
# ----------------------------------------------------

@app.get("/api/storyteller/me")
def storyteller_me(authorization: Optional[str] = Header(default=None)):
    user = _auth_storyteller_user(authorization)
    prompts = _get_active_prompts(_get_portal_owner_email(user))
    return {
        "user": {
            "email": user["email"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "signup_code": user.get("signup_code", ""),
            "tier": user.get("tier", "A"),
            "managed": bool(user.get("managed", False)),
            "this_month_count": _this_month_recording_count(user["id"]),
            "custom_prompts": _user_custom_prompts(user),
        },
        "prompts": [{"id": p["id"], "text": p["text"]} for p in prompts],
    }


@app.post("/api/storyteller/validate")
def storyteller_validate(payload: StoryValidateRequest):
    code = payload.user_code.strip().upper()
    pc = _get_promo_code(code)
    if not pc:
        raise HTTPException(status_code=404, detail="User code not found or inactive")
    code_tier = pc.get("tier", "A").upper()
    prompts = _get_active_prompts(pc.get("created_by"), include_system=code_tier not in {"E", "F"})
    if not prompts:
        raise HTTPException(status_code=404, detail="No active story prompt. Ask a collaborator to set one up.")
    return {"valid": True, "prompts": [{"id": p["id"], "text": p["text"]} for p in prompts]}


@app.post("/api/storyteller/signup")
def storyteller_signup(payload: StorySignupRequest):
    # Validate user code if provided
    code = payload.user_code.strip().upper() if payload.user_code else None
    pc = None
    if code:
        pc = _get_promo_code(code)
        if not pc:
            raise HTTPException(status_code=404, detail="User code not found or inactive")

    email = payload.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    # Check storyteller_users first (existing storyteller account)
    existing_st = _get_storyteller_user(email)
    if existing_st:
        raise HTTPException(status_code=400, detail="An account with this email already exists. Please sign in instead.")

    # Check users table (existing portal admin adding storyteller access)
    existing_u = _get_user(email)

    # Derive tier and managed flag from promo code
    if code and pc:
        code_tier = pc.get("tier", "A").upper()
        if code_tier == "E":
            user_tier = "B"      # E-code invitees get unlimited recording
            user_managed = True
        elif code_tier == "F":
            user_tier = "C"      # F-code invitees get deepening capability
            user_managed = False
        elif code_tier in {"B", "C", "D"}:
            user_tier = code_tier
            user_managed = False
        else:
            user_tier = "A"
            user_managed = False
    else:
        user_tier = "A"
        user_managed = False

    user_id = "stuser_" + secrets.token_hex(8)
    salt = secrets.token_hex(8)
    pw_hash = _hash_password(payload.password, salt)
    st_user = {
        "id": user_id,
        "email": email,
        "first_name": payload.first_name.strip(),
        "last_name": payload.last_name.strip(),
        "password_salt": salt,
        "password_hash": pw_hash,
        "signup_code": code,
        "tier": user_tier,
        "managed": user_managed,
        "created_at": _utc_now(),
    }
    _create_storyteller_user(st_user)

    if existing_u:
        # Portal admin adding storyteller access — upgrade role only
        _update_user(email, {
            "role": "both",
            "first_name": payload.first_name.strip(),
            "last_name": payload.last_name.strip(),
        })
    else:
        # New storyteller-only account — create unified users row for auth.
        # Insert only original-schema columns, then update with ALTER TABLE columns
        # to avoid PostgREST schema cache timing issues.
        auth_user = {
            "email": email,
            "name": (payload.first_name.strip() + " " + payload.last_name.strip()).strip(),
            "password_salt": salt,
            "password_hash": pw_hash,
            "created_at": _utc_now(),
        }
        _create_user(auth_user)
        _update_user(email, {
            "role": "storyteller",
            "first_name": payload.first_name.strip(),
            "last_name": payload.last_name.strip(),
        })

    # Transfer any existing recordings for this code to the new account
    if code:
        if supabase:
            (supabase.table("story_recordings")
                .update({"storyteller_user_id": user_id})
                .eq("promo_code", code)
                .is_("storyteller_user_id", "null")
                .execute())
        else:
            db = _load_db()
            for rec in db["story_recordings"].values():
                if rec.get("promo_code") == code and not rec.get("storyteller_user_id"):
                    rec["storyteller_user_id"] = user_id
            _save_db(db)

    prompts = _get_active_prompts(
        pc.get("created_by") if pc else None,
        include_system=code_tier not in {"E", "F"},
    )
    token = _create_story_session(email)
    return {
        "token": token,
        "user": {
            "email": email,
            "first_name": payload.first_name.strip(),
            "last_name": payload.last_name.strip(),
            "signup_code": code or "",
            "tier": user_tier,
            "managed": user_managed,
            "this_month_count": 0,
            "custom_prompts": [],
        },
        "prompts": [{"id": p["id"], "text": p["text"]} for p in prompts],
    }


@app.post("/api/storyteller/login")
def storyteller_login(payload: StoryLoginRequest):
    email = payload.email.strip().lower()
    # Authenticate against unified users table
    auth_user = _get_user(email)
    if not auth_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    expected = _hash_password(payload.password, auth_user["password_salt"])
    if expected != auth_user["password_hash"]:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Load storyteller-specific app data
    st_user = _get_storyteller_user(email)
    if not st_user:
        raise HTTPException(status_code=403, detail="No storyteller account found for this email. Please use the portal login.")

    signup_code = st_user.get("signup_code", "")
    signup_pc = _get_promo_code(signup_code) if signup_code else None
    login_code_tier = (signup_pc.get("tier", "A").upper() if signup_pc else "A")
    prompts = _get_active_prompts(
        _get_portal_owner_email(st_user),
        include_system=login_code_tier not in {"E", "F"},
    )
    token = _create_story_session(email)
    return {
        "token": token,
        "user": {
            "email": email,
            "first_name": st_user.get("first_name", auth_user.get("first_name", "")),
            "last_name": st_user.get("last_name", auth_user.get("last_name", "")),
            "signup_code": st_user.get("signup_code", ""),
            "tier": st_user.get("tier", "A"),
            "managed": bool(st_user.get("managed", False)),
            "this_month_count": _this_month_recording_count(st_user["id"]),
            "custom_prompts": _user_custom_prompts(st_user),
        },
        "prompts": [{"id": p["id"], "text": p["text"]} for p in prompts],
    }


@app.post("/api/storyteller/request-reset")
def storyteller_request_reset(payload: StoryPasswordResetRequest):
    from datetime import timedelta
    email = payload.email.strip().lower()
    print(f"[RESET] request for {email} | resend_sdk={resend_sdk is not None} | has_key={bool(RESEND_API_KEY)}")
    # Delegate to unified users table
    user = _get_user(email)
    if not user:
        print(f"[RESET] no user found for {email}")
        return {"ok": True}

    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    _update_user(email, {"password_reset_token": token, "password_reset_expires": expires})

    reset_url = f"{APP_URL}/login?reset_token={token}"
    if resend_sdk and RESEND_API_KEY:
        resend_sdk.Emails.send({
            "from": RESEND_FROM,
            "to": [email],
            "subject": "Reset your MyCogna password",
            "html": (
                f"<p>Click the link below to reset your MyCogna password. "
                f"This link expires in 1 hour.</p>"
                f"<p><a href='{reset_url}'>{reset_url}</a></p>"
                f"<p>If you didn't request this, you can safely ignore this email.</p>"
            ),
        })
    else:
        print(f"[DEV] Reset link for {email}: {reset_url}")
    return {"ok": True}


@app.post("/api/storyteller/reset-password")
def storyteller_reset_password(payload: StoryPasswordResetConfirm):
    # Delegate to unified users table
    if supabase:
        r = supabase.table("users").select("*").eq("password_reset_token", payload.token).limit(1).execute()
        user = r.data[0] if r.data else None
    else:
        db = _load_db()
        user = next((u for u in db["users"].values() if u.get("password_reset_token") == payload.token), None)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")

    expires_str = user.get("password_reset_expires")
    if not expires_str:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
    expires = datetime.fromisoformat(expires_str)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires:
        raise HTTPException(status_code=400, detail="Reset link has expired. Please request a new one.")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    new_salt = secrets.token_hex(8)
    new_hash = _hash_password(payload.password, new_salt)
    _update_user(user["email"], {
        "password_salt": new_salt,
        "password_hash": new_hash,
        "password_reset_token": None,
        "password_reset_expires": None,
    })
    return {"ok": True}


@app.post("/api/storyteller/record")
async def storyteller_record(
    prompt_id: str = Form(...),
    audio: UploadFile = File(...),
    authorization: Optional[str] = Header(default=None),
):
    st_user = _auth_storyteller_user(authorization)

    transcript = _transcribe_audio(audio)

    audio.file.seek(0)
    recording_id = "rec_" + secrets.token_hex(8)
    audio_url = _save_story_audio(recording_id, audio)

    signup_code = st_user.get("signup_code") or None
    # Custom prompts (id starts with "custom-") don't exist in story_prompts table
    db_prompt_id = None if (prompt_id or "").startswith("custom-") else prompt_id
    if supabase:
        supabase.table("story_recordings").insert({
            "id": recording_id,
            "promo_code": signup_code,
            "storyteller_user_id": st_user["id"],
            "prompt_id": db_prompt_id,
            "transcript": transcript,
            "audio_url": audio_url,
        }).execute()
    else:
        db = _load_db()
        db["story_recordings"][recording_id] = {
            "id": recording_id,
            "promo_code": signup_code,
            "storyteller_user_id": st_user["id"],
            "prompt_id": db_prompt_id,
            "transcript": transcript,
            "audio_url": audio_url,
            "created_at": _utc_now(),
        }
        _save_db(db)

    return {"ok": True, "transcript": transcript, "recording_id": recording_id}


@app.get("/api/storyteller/my-recordings")
def my_recordings(authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    if supabase:
        r = (supabase.table("story_recordings")
             .select("prompt_id")
             .eq("storyteller_user_id", st_user["id"])
             .execute())
        prompt_ids = list({rec["prompt_id"] for rec in (r.data or []) if rec.get("prompt_id")})
    else:
        db = _load_db()
        prompt_ids = list({
            rec["prompt_id"] for rec in db["story_recordings"].values()
            if rec.get("storyteller_user_id") == st_user["id"] and rec.get("prompt_id")
        })
    return {"answered_prompt_ids": prompt_ids}


@app.get("/api/storyteller/my-stories")
def my_stories(authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    if supabase:
        r = (supabase.table("story_recordings")
             .select("id, prompt_id, transcript, created_at")
             .eq("storyteller_user_id", st_user["id"])
             .order("created_at", desc=False)
             .execute())
        recordings = r.data or []
        prompt_ids = [rec["prompt_id"] for rec in recordings if rec.get("prompt_id")]
        prompt_map = {}
        if prompt_ids:
            pr = supabase.table("story_prompts").select("id, text").in_("id", prompt_ids).execute()
            prompt_map = {p["id"]: p["text"] for p in (pr.data or [])}
        for rec in recordings:
            rec["prompt_text"] = prompt_map.get(rec.get("prompt_id") or "", "")
    else:
        db = _load_db()
        recs = [rec for rec in db["story_recordings"].values()
                if rec.get("storyteller_user_id") == st_user["id"]]
        recordings = sorted(recs, key=lambda x: x.get("created_at", ""))
        prompt_map = {p["id"]: p["text"] for p in db["story_prompts"].values()}
        for rec in recordings:
            rec["prompt_text"] = prompt_map.get(rec.get("prompt_id") or "", "")
    return {"recordings": recordings}


@app.post("/api/storyteller/custom-prompts")
def add_custom_prompt(
    payload: StoryCustomPromptRequest,
    authorization: Optional[str] = Header(default=None),
):
    st_user = _auth_storyteller_user(authorization)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Prompt text is required")
    new_prompt = {"id": "custom-" + secrets.token_hex(6), "text": text, "category": payload.category}
    existing = _user_custom_prompts(st_user)
    existing.append(new_prompt)
    _update_storyteller_user(st_user["email"], {"custom_prompts": existing})
    return {"prompt": new_prompt, "custom_prompts": existing}


@app.get("/api/storyteller/prompts")
def list_story_prompts(authorization: Optional[str] = Header(default=None)):
    user = _auth_user(authorization)
    hidden = set(_get_hidden_prompt_ids(user["email"]))
    if supabase:
        sys_r = (supabase.table("story_prompts").select("*")
                 .is_("portal_user_email", "null")
                 .order("sort_order").order("created_at").execute())
        custom_r = (supabase.table("story_prompts").select("*")
                    .eq("portal_user_email", user["email"])
                    .order("sort_order").order("created_at").execute())
        sys_prompts = sys_r.data or []
        for p in sys_prompts:
            p["hidden_by_me"] = p["id"] in hidden
        all_prompts = sys_prompts + (custom_r.data or [])
        all_prompts.sort(key=lambda x: (x.get("sort_order", 0), x.get("created_at", "")))
        return {"prompts": all_prompts}
    db = _load_db()
    prompts = sorted(db["story_prompts"].values(), key=lambda x: (x.get("sort_order", 0), x.get("created_at", "")))
    prompts = [p for p in prompts if not p.get("portal_user_email") or p.get("portal_user_email") == user["email"]]
    result = []
    for p in prompts:
        p_copy = dict(p)
        if not p_copy.get("portal_user_email"):
            p_copy["hidden_by_me"] = p_copy["id"] in hidden
        result.append(p_copy)
    return {"prompts": result}


@app.post("/api/storyteller/prompts")
def create_story_prompt(
    payload: StoryPromptCreate,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Prompt text is required")
    prompt_id = "prompt_" + secrets.token_hex(6)
    if supabase:
        r = supabase.table("story_prompts").select("sort_order").order("sort_order", desc=True).limit(1).execute()
        next_order = (r.data[0]["sort_order"] + 1) if r.data else 0
    else:
        db_tmp = _load_db()
        orders = [p.get("sort_order", 0) for p in db_tmp["story_prompts"].values()]
        next_order = (max(orders) + 1) if orders else 0
    prompt = {
        "id": prompt_id,
        "text": text,
        "active": True,
        "sort_order": next_order,
        "created_by": user["email"],
        "portal_user_email": user["email"],
        "created_at": _utc_now(),
    }
    if supabase:
        supabase.table("story_prompts").insert(prompt).execute()
    else:
        db = _load_db()
        db["story_prompts"][prompt_id] = prompt
        _save_db(db)
    return {"prompt": prompt}


@app.put("/api/storyteller/prompts/{prompt_id}/activate")
def activate_story_prompt(
    prompt_id: str,
    authorization: Optional[str] = Header(default=None),
):
    _auth_user(authorization)
    if supabase:
        r = supabase.table("story_prompts").select("active").eq("id", prompt_id).limit(1).execute()
        current = r.data[0]["active"] if r.data else False
        supabase.table("story_prompts").update({"active": not current}).eq("id", prompt_id).execute()
    else:
        db = _load_db()
        if prompt_id in db["story_prompts"]:
            db["story_prompts"][prompt_id]["active"] = not db["story_prompts"][prompt_id].get("active", False)
        _save_db(db)
    return {"ok": True}


@app.put("/api/storyteller/prompts/{prompt_id}/hide")
def toggle_hide_story_prompt(
    prompt_id: str,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)
    hidden = _get_hidden_prompt_ids(user["email"])
    was_hidden = prompt_id in hidden
    if was_hidden:
        hidden = [pid for pid in hidden if pid != prompt_id]
    else:
        hidden = hidden + [prompt_id]
    _set_hidden_prompt_ids(user["email"], hidden)
    return {"ok": True, "hidden": not was_hidden}


@app.delete("/api/storyteller/prompts/{prompt_id}")
def delete_story_prompt(
    prompt_id: str,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)
    if supabase:
        r = supabase.table("story_prompts").select("portal_user_email").eq("id", prompt_id).limit(1).execute()
        if not r.data:
            raise HTTPException(status_code=404, detail="Prompt not found")
        owner = r.data[0].get("portal_user_email")
        if owner is None:
            raise HTTPException(status_code=403, detail="System prompts cannot be deleted")
        if owner != user["email"]:
            raise HTTPException(status_code=403, detail="You can only delete your own prompts")
        supabase.table("story_prompts").delete().eq("id", prompt_id).execute()
    else:
        db = _load_db()
        prompt = db["story_prompts"].get(prompt_id)
        if prompt:
            owner = prompt.get("portal_user_email")
            if owner is None:
                raise HTTPException(status_code=403, detail="System prompts cannot be deleted")
            if owner != user["email"]:
                raise HTTPException(status_code=403, detail="You can only delete your own prompts")
            db["story_prompts"].pop(prompt_id, None)
            _save_db(db)
    return {"ok": True}


@app.post("/api/storyteller/prompts/reorder")
def reorder_story_prompts(
    payload: PromptsReorderRequest,
    authorization: Optional[str] = Header(default=None),
):
    _auth_user(authorization)
    if supabase:
        for i, prompt_id in enumerate(payload.ids):
            supabase.table("story_prompts").update({"sort_order": i}).eq("id", prompt_id).execute()
    else:
        db = _load_db()
        for i, prompt_id in enumerate(payload.ids):
            if prompt_id in db["story_prompts"]:
                db["story_prompts"][prompt_id]["sort_order"] = i
        _save_db(db)
    return {"ok": True}


@app.get("/api/storyteller/user-codes")
def list_promo_codes(
    authorization: Optional[str] = Header(default=None),
    tier: Optional[str] = Query(default=None),
):
    _auth_user(authorization)
    if supabase:
        q = supabase.table("promo_codes").select("*").order("created_at", desc=True)
        if tier:
            q = q.eq("tier", tier.upper())
        r = q.execute()
        return {"codes": r.data or []}
    db = _load_db()
    codes = sorted(db["promo_codes"].values(), key=lambda x: x.get("created_at", ""), reverse=True)
    if tier:
        codes = [c for c in codes if c.get("tier", "A").upper() == tier.upper()]
    return {"codes": list(codes)}


@app.post("/api/storyteller/user-codes")
def create_promo_code(
    payload: PromoCodeCreate,
    authorization: Optional[str] = Header(default=None),
):
    user = _auth_user(authorization)
    tier = payload.tier.upper() if payload.tier in {"A", "B", "C", "D", "E", "F"} else "A"
    try:
        code = _generate_story_promo_code(tier)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Code generation error: {exc}")
    record = {
        "code": code,
        "tier": tier,
        "description": payload.description.strip(),
        "active": True,
        "created_by": user["email"],
        "created_at": _utc_now(),
    }
    if supabase:
        try:
            supabase.table("promo_codes").insert(record).execute()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"DB insert error: {exc}")
    else:
        db = _load_db()
        db["promo_codes"][code] = record
        _save_db(db)
    return {"code": record}


@app.patch("/api/storyteller/user-codes/{code}")
def rename_promo_code(
    code: str,
    payload: PromoCodeCreate,
    authorization: Optional[str] = Header(default=None),
):
    _auth_user(authorization)
    code = code.upper()
    description = payload.description.strip()
    if supabase:
        supabase.table("promo_codes").update({"description": description}).eq("code", code).execute()
    else:
        db = _load_db()
        if code in db["promo_codes"]:
            db["promo_codes"][code]["description"] = description
        _save_db(db)
    return {"ok": True}


@app.delete("/api/storyteller/user-codes/{code}")
def deactivate_promo_code(
    code: str,
    authorization: Optional[str] = Header(default=None),
):
    _auth_user(authorization)
    code = code.upper()
    if supabase:
        supabase.table("promo_codes").update({"active": False}).eq("code", code).execute()
    else:
        db = _load_db()
        if code in db["promo_codes"]:
            db["promo_codes"][code]["active"] = False
        _save_db(db)
    return {"ok": True}


@app.get("/api/storyteller/recordings")
def list_recordings(
    authorization: Optional[str] = Header(default=None),
    tier: Optional[str] = Query(default=None),
):
    _auth_user(authorization)
    if supabase:
        q = (supabase.table("story_recordings")
             .select("id, promo_code, prompt_id, transcript, created_at, promo_codes(description, tier)")
             .order("created_at", desc=True)
             .limit(200))
        r = q.execute()
        recordings = []
        for rec in (r.data or []):
            code_info = rec.pop("promo_codes", None) or {}
            rec["promo_code_label"] = code_info.get("description", "")
            rec["tier"] = code_info.get("tier", "A")
            if tier and rec["tier"] != tier.upper():
                continue
            recordings.append(rec)
        return {"recordings": recordings[:50]}
    db = _load_db()
    recs = sorted(db["story_recordings"].values(), key=lambda x: x.get("created_at", ""), reverse=True)
    result = []
    for rec in recs:
        code_info = db["promo_codes"].get(rec.get("promo_code", ""), {})
        rec["promo_code_label"] = code_info.get("description", "")
        rec["tier"] = code_info.get("tier", "A")
        if tier and rec["tier"] != tier.upper():
            continue
        result.append(rec)
    return {"recordings": result[:50]}


@app.get("/story-audio/{filename}")
def serve_story_audio(filename: str):
    audio_path = STORY_RECORDINGS_DIR / "audio" / filename
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    ext = Path(filename).suffix.lower()
    mime_map = {".webm": "audio/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav",
                ".ogg": "audio/ogg", ".m4a": "audio/mp4"}
    return FileResponse(audio_path, media_type=mime_map.get(ext, "audio/webm"))


# ----------------------------------------------------
# Legacy /api/respond (single-Cogna, backward compat)
# ----------------------------------------------------

@app.post("/api/respond")
async def respond(
    cogna_id: Optional[str] = Form(None),
    message: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    audio: Optional[UploadFile] = File(None),
):
    try:
        if not cogna_id:
            raise HTTPException(status_code=400, detail="Unknown cogna_id")

        cogna = _get_cogna(cogna_id)
        incoming_message = text or message
        if not incoming_message and not audio:
            raise HTTPException(status_code=400, detail="Provide message text or audio file")

        if audio and not incoming_message:
            incoming_message = _transcribe_audio(audio)

        persona_prompt = _cogna_voice_prompt(cogna)
        generated_text = _generate_text_response(persona_prompt, [{"role": "user", "content": incoming_message}])
        audio_url = _generate_cogna_audio(cogna, generated_text)

        return {
            "cogna_id": cogna_id,
            "cogna_name": cogna["name"],
            "text": generated_text,
            "audio_url": audio_url,
            "transcript": incoming_message,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ----------------------------------------------------
# Memoir Writing Tool endpoints
# TODO: Add tier check here when Stripe is integrated — Tier 2 (Storyteller+) only
# ----------------------------------------------------

MEMOIR_DEEPEN_SYSTEM = """You are a warm, skilled memoir interviewer. You have just read the following story transcript from the user. Your job is to ask thoughtful follow-up questions that help the user go deeper — drawing out specific details, sensory memories, emotions, and context they didn't include the first time.

Ask one or two questions at a time. Never more. Listen carefully to each response before asking the next question. Your tone is curious and warm, never clinical or journalistic. You are not evaluating the story — you are helping the storyteller find what's already there.

When the user indicates they are finished, thank them warmly and let them know their story has been saved."""

MEMOIR_ASSEMBLE_SYSTEM = """You are a skilled memoir editor. You have been given a collection of voice-recorded stories and follow-up interview transcripts from one person.

Your job is to:
1. Identify the major themes running through these stories
2. Note the person's distinctive voice, humor, and way of seeing the world
3. Suggest a logical chapter structure that groups related stories
4. Give each suggested chapter a working title
5. Briefly note what kinds of stories seem missing that would strengthen the memoir

Format your response as:
BOOK BIBLE: 3-4 paragraphs describing themes, voice, and emotional arc
CHAPTER OUTLINE: numbered list of chapter titles with 1-2 sentence descriptions
WHAT'S MISSING: a short, encouraging paragraph noting gaps

Tone: warm, encouraging, professional. This person's stories matter."""

MEMOIR_EDIT_SYSTEM = """You are a skilled memoir editor working with a writer on their chapter drafts. You have been given the raw transcripts assigned to this chapter.

Your job is to:
1. Summarize what this chapter currently contains
2. Note its strengths — what's working, what's vivid, what's true
3. Suggest structural improvements — pacing, order, transitions
4. Identify any gaps where more detail would strengthen the story
5. Offer to help rewrite any section the author requests

Important: This is their story, their voice. You are not rewriting it in your own voice — you are helping them find the best version of theirs. Never change the facts. Never add events that didn't happen. Always ask before making significant changes."""


def _memoir_db_defaults(db: Dict[str, Any]):
    db.setdefault("memoir_sessions", {})
    db.setdefault("book_bibles", {})
    db.setdefault("chapters", {})


@app.get("/api/memoir/dashboard")
async def memoir_dashboard(authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    user_id = st_user["id"]

    if supabase:
        r = supabase.table("story_recordings").select("id, prompt_id, transcript, created_at").eq("storyteller_user_id", user_id).order("created_at").execute()
        recordings = r.data or []
        prompt_ids = [rec["prompt_id"] for rec in recordings if rec.get("prompt_id")]
        prompt_map = {}
        if prompt_ids:
            pr = supabase.table("story_prompts").select("id, text").in_("id", prompt_ids).execute()
            prompt_map = {p["id"]: p["text"] for p in (pr.data or [])}
        ms = supabase.table("memoir_sessions").select("id, recording_id, finished").eq("storyteller_user_id", user_id).execute()
        session_map = {s["recording_id"]: s for s in (ms.data or [])}
        bb = supabase.table("book_bibles").select("id, content, assembled_at").eq("storyteller_user_id", user_id).order("assembled_at", desc=True).limit(1).execute()
        book_bible = bb.data[0] if bb.data else None
        ch = supabase.table("chapters").select("id, title, sort_order, content, updated_at").eq("storyteller_user_id", user_id).order("sort_order").execute()
        chapters = ch.data or []
    else:
        db = _load_db(); _memoir_db_defaults(db)
        recordings = sorted([rec for rec in db["story_recordings"].values() if rec.get("storyteller_user_id") == user_id], key=lambda x: x.get("created_at", ""))
        prompt_map = {p["id"]: p["text"] for p in db.get("story_prompts", {}).values()}
        session_map = {s["recording_id"]: s for s in db["memoir_sessions"].values() if s.get("storyteller_user_id") == user_id}
        bbs = sorted([b for b in db["book_bibles"].values() if b.get("storyteller_user_id") == user_id], key=lambda x: x.get("assembled_at", ""), reverse=True)
        book_bible = bbs[0] if bbs else None
        chapters = sorted([c for c in db["chapters"].values() if c.get("storyteller_user_id") == user_id], key=lambda x: x.get("sort_order", 0))

    for rec in recordings:
        rec["prompt_text"] = prompt_map.get(rec.get("prompt_id") or "", "Custom question")
        session = session_map.get(rec["id"])
        rec["deepening_status"] = "finished" if session and session.get("finished") else ("started" if session else "none")
        rec["memoir_session_id"] = session["id"] if session else None

    return {"recordings": recordings, "book_bible": book_bible, "chapters": chapters}


@app.post("/api/memoir/deepen/start")
async def memoir_deepen_start(payload: MemoirDeepenStartRequest, authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    user_id = st_user["id"]
    print(f"[MEMOIR] deepen/start recording_id={payload.recording_id} user={user_id}")

    if supabase:
        r = supabase.table("story_recordings").select("*").eq("id", payload.recording_id).eq("storyteller_user_id", user_id).limit(1).execute()
        recording = r.data[0] if r.data else None
    else:
        db = _load_db()
        rec = db["story_recordings"].get(payload.recording_id)
        recording = rec if rec and rec.get("storyteller_user_id") == user_id else None

    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    transcript = recording.get("transcript", "")

    # Resume existing unfinished session for this recording rather than creating a new one
    if supabase:
        existing_r = (supabase.table("memoir_sessions").select("*")
                      .eq("storyteller_user_id", user_id)
                      .eq("recording_id", payload.recording_id)
                      .eq("finished", False)
                      .order("created_at", desc=True)
                      .limit(1).execute())
        existing = existing_r.data[0] if existing_r.data else None
    else:
        db = _load_db(); _memoir_db_defaults(db)
        existing = next((s for s in db["memoir_sessions"].values()
                         if s.get("storyteller_user_id") == user_id
                         and s.get("recording_id") == payload.recording_id
                         and not s.get("finished")), None)

    if existing:
        return {"session_id": existing["id"], "messages": existing["messages"], "transcript": transcript}

    system = MEMOIR_DEEPEN_SYSTEM + f"\n\nHere is the story transcript:\n\n{transcript}"
    opening = _generate_memoir_response(system, [{"role": "user", "content": "Please begin."}])

    session_id = "msess_" + secrets.token_hex(8)
    messages = [{"role": "assistant", "content": opening}]
    now = _utc_now()

    if supabase:
        supabase.table("memoir_sessions").insert({"id": session_id, "storyteller_user_id": user_id, "recording_id": payload.recording_id, "messages": messages, "finished": False, "created_at": now, "updated_at": now}).execute()
    else:
        db = _load_db(); _memoir_db_defaults(db)
        db["memoir_sessions"][session_id] = {"id": session_id, "storyteller_user_id": user_id, "recording_id": payload.recording_id, "messages": messages, "finished": False, "created_at": now, "updated_at": now}
        _save_db(db)

    return {"session_id": session_id, "messages": messages, "transcript": transcript}


@app.post("/api/memoir/deepen/chat")
async def memoir_deepen_chat(payload: MemoirDeepenChatRequest, authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    user_id = st_user["id"]

    if supabase:
        r = supabase.table("memoir_sessions").select("*").eq("id", payload.session_id).eq("storyteller_user_id", user_id).limit(1).execute()
        session = r.data[0] if r.data else None
    else:
        db = _load_db(); _memoir_db_defaults(db)
        s = db["memoir_sessions"].get(payload.session_id)
        session = s if s and s.get("storyteller_user_id") == user_id else None

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if supabase:
        rec_r = supabase.table("story_recordings").select("transcript").eq("id", session["recording_id"]).limit(1).execute()
        transcript = rec_r.data[0]["transcript"] if rec_r.data else ""
    else:
        transcript = db["story_recordings"].get(session["recording_id"], {}).get("transcript", "")

    messages = session.get("messages") or []
    messages.append({"role": "user", "content": payload.message})

    system = MEMOIR_DEEPEN_SYSTEM + f"\n\nHere is the story transcript:\n\n{transcript}"
    reply = _generate_memoir_response(system, messages)
    messages.append({"role": "assistant", "content": reply})

    if supabase:
        supabase.table("memoir_sessions").update({"messages": messages, "updated_at": _utc_now()}).eq("id", payload.session_id).execute()
    else:
        db["memoir_sessions"][payload.session_id]["messages"] = messages
        db["memoir_sessions"][payload.session_id]["updated_at"] = _utc_now()
        _save_db(db)

    return {"message": reply}


@app.post("/api/memoir/deepen/finish")
async def memoir_deepen_finish(payload: MemoirDeepenFinishRequest, authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    if supabase:
        supabase.table("memoir_sessions").update({"finished": True, "updated_at": _utc_now()}).eq("id", payload.session_id).eq("storyteller_user_id", st_user["id"]).execute()
    else:
        db = _load_db(); _memoir_db_defaults(db)
        if payload.session_id in db["memoir_sessions"]:
            db["memoir_sessions"][payload.session_id]["finished"] = True
        _save_db(db)
    return {"ok": True}


@app.post("/api/memoir/assemble")
async def memoir_assemble(authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    user_id = st_user["id"]

    if supabase:
        r = supabase.table("story_recordings").select("id, prompt_id, transcript, created_at").eq("storyteller_user_id", user_id).order("created_at").execute()
        recordings = r.data or []
        prompt_ids = [rec["prompt_id"] for rec in recordings if rec.get("prompt_id")]
        prompt_map = {}
        if prompt_ids:
            pr = supabase.table("story_prompts").select("id, text").in_("id", prompt_ids).execute()
            prompt_map = {p["id"]: p["text"] for p in (pr.data or [])}
        ms = supabase.table("memoir_sessions").select("recording_id, messages").eq("storyteller_user_id", user_id).eq("finished", True).execute()
        sessions_by_recording = {s["recording_id"]: s["messages"] for s in (ms.data or [])}
    else:
        db = _load_db(); _memoir_db_defaults(db)
        recordings = sorted([rec for rec in db["story_recordings"].values() if rec.get("storyteller_user_id") == user_id], key=lambda x: x.get("created_at", ""))
        prompt_map = {p["id"]: p["text"] for p in db.get("story_prompts", {}).values()}
        sessions_by_recording = {s["recording_id"]: s["messages"] for s in db["memoir_sessions"].values() if s.get("storyteller_user_id") == user_id and s.get("finished")}

    if not recordings:
        raise HTTPException(status_code=400, detail="No recordings found to assemble")

    context_parts = []
    for rec in recordings:
        question = prompt_map.get(rec.get("prompt_id") or "", "Custom question")
        context_parts.append(f"QUESTION: {question}\nANSWER: {rec.get('transcript', '')}")
        if rec["id"] in sessions_by_recording:
            msgs = sessions_by_recording[rec["id"]]
            exchanges = [f"  {'AI' if m['role'] == 'assistant' else 'User'}: {m['content']}" for m in msgs]
            context_parts.append("FOLLOW-UP CONVERSATION:\n" + "\n".join(exchanges))
        context_parts.append("")

    full_context = "\n".join(context_parts)
    content = _generate_memoir_response(MEMOIR_ASSEMBLE_SYSTEM, [{"role": "user", "content": full_context}], max_tokens=2000)

    bible_id = "bible_" + secrets.token_hex(8)
    now = _utc_now()
    if supabase:
        supabase.table("book_bibles").insert({"id": bible_id, "storyteller_user_id": user_id, "content": content, "assembled_at": now}).execute()
    else:
        db["book_bibles"][bible_id] = {"id": bible_id, "storyteller_user_id": user_id, "content": content, "assembled_at": now}
        _save_db(db)

    return {"book_bible_id": bible_id, "content": content}


@app.get("/api/memoir/chapters")
async def memoir_get_chapters(authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    user_id = st_user["id"]
    if supabase:
        r = supabase.table("chapters").select("*").eq("storyteller_user_id", user_id).order("sort_order").execute()
        return {"chapters": r.data or []}
    db = _load_db(); _memoir_db_defaults(db)
    chapters = sorted([c for c in db["chapters"].values() if c.get("storyteller_user_id") == user_id], key=lambda x: x.get("sort_order", 0))
    return {"chapters": chapters}


@app.post("/api/memoir/chapters")
async def memoir_create_chapter(payload: MemoirChapterRequest, authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    chapter_id = "chap_" + secrets.token_hex(8)
    now = _utc_now()
    chapter = {"id": chapter_id, "storyteller_user_id": st_user["id"], "book_bible_id": payload.book_bible_id, "title": payload.title, "content": payload.content, "edit_messages": [], "sort_order": payload.sort_order, "created_at": now, "updated_at": now}
    if supabase:
        supabase.table("chapters").insert(chapter).execute()
    else:
        db = _load_db(); _memoir_db_defaults(db)
        db["chapters"][chapter_id] = chapter
        _save_db(db)
    return {"chapter": chapter}


@app.put("/api/memoir/chapters/{chapter_id}")
async def memoir_save_chapter(chapter_id: str, payload: MemoirChapterRequest, authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    updates = {"title": payload.title, "content": payload.content, "updated_at": _utc_now()}
    if supabase:
        supabase.table("chapters").update(updates).eq("id", chapter_id).eq("storyteller_user_id", st_user["id"]).execute()
    else:
        db = _load_db(); _memoir_db_defaults(db)
        if chapter_id in db["chapters"]:
            db["chapters"][chapter_id].update(updates)
        _save_db(db)
    return {"ok": True}


@app.post("/api/memoir/chapters/{chapter_id}/edit")
async def memoir_chapter_edit(chapter_id: str, payload: MemoirChapterEditRequest, authorization: Optional[str] = Header(default=None)):
    st_user = _auth_storyteller_user(authorization)
    user_id = st_user["id"]

    if supabase:
        r = supabase.table("chapters").select("*").eq("id", chapter_id).eq("storyteller_user_id", user_id).limit(1).execute()
        chapter = r.data[0] if r.data else None
    else:
        db = _load_db(); _memoir_db_defaults(db)
        c = db["chapters"].get(chapter_id)
        chapter = c if c and c.get("storyteller_user_id") == user_id else None

    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    messages = chapter.get("edit_messages") or []
    if not messages:
        system = MEMOIR_EDIT_SYSTEM + f"\n\nHere are the raw transcripts for this chapter:\n\n{chapter.get('content', '')}"
        messages.append({"role": "user", "content": "Please give me your initial editorial feedback on this chapter."})
        opening = _generate_memoir_response(system, messages)
        messages.append({"role": "assistant", "content": opening})

    messages.append({"role": "user", "content": payload.message})
    system = MEMOIR_EDIT_SYSTEM + f"\n\nHere are the raw transcripts for this chapter:\n\n{chapter.get('content', '')}"
    reply = _generate_memoir_response(system, messages)
    messages.append({"role": "assistant", "content": reply})

    if supabase:
        supabase.table("chapters").update({"edit_messages": messages, "updated_at": _utc_now()}).eq("id", chapter_id).execute()
    else:
        db["chapters"][chapter_id]["edit_messages"] = messages
        db["chapters"][chapter_id]["updated_at"] = _utc_now()
        _save_db(db)

    return {"message": reply}


# ----------------------------------------------------
# Portal-invitee memoir endpoints
# ----------------------------------------------------

@app.get("/api/portal/invitees")
def list_portal_invitees(tier: str = Query(default="C"), authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    tier_upper = tier.upper()
    if supabase:
        codes_r = supabase.table("promo_codes").select("code").eq("created_by", portal_user["email"]).eq("tier", tier_upper).execute()
        codes = [r["code"] for r in (codes_r.data or [])]
        if not codes:
            return {"invitees": []}
        st_r = supabase.table("storyteller_users").select("id, email, first_name, last_name, created_at").in_("signup_code", codes).order("created_at").execute()
        invitees = st_r.data or []
    else:
        db = _load_db()
        codes = {v.get("code") for v in db.get("promo_codes", {}).values() if v.get("created_by") == portal_user["email"] and v.get("tier") == tier_upper}
        invitees = sorted(
            [{"id": u["id"], "email": u["email"], "first_name": u.get("first_name", ""), "last_name": u.get("last_name", ""), "created_at": u.get("created_at", "")}
             for u in db.get("storyteller_users", {}).values() if u.get("signup_code") in codes],
            key=lambda x: x.get("created_at", "")
        )
    return {"invitees": invitees}


@app.get("/api/portal/invitee/{storyteller_id}/data")
def portal_invitee_data(storyteller_id: str, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    user_id = st_user["id"]
    # Look up the tier of the signup code so the frontend can label correctly
    signup_code = st_user.get("signup_code", "")
    code_tier = "C"
    if signup_code:
        if supabase:
            ct = supabase.table("promo_codes").select("tier").eq("code", signup_code).limit(1).execute()
            code_tier = ct.data[0].get("tier", "C") if ct.data else "C"
        else:
            db_lookup = _load_db()
            pc = next((v for v in db_lookup.get("promo_codes", {}).values() if v.get("code") == signup_code), None)
            code_tier = pc.get("tier", "C") if pc else "C"
    if supabase:
        r = supabase.table("story_recordings").select("id, prompt_id, transcript, created_at").eq("storyteller_user_id", user_id).order("created_at").execute()
        recordings = r.data or []
        prompt_ids = [rec["prompt_id"] for rec in recordings if rec.get("prompt_id")]
        prompt_map = {}
        if prompt_ids:
            pr = supabase.table("story_prompts").select("id, text").in_("id", prompt_ids).execute()
            prompt_map = {p["id"]: p["text"] for p in (pr.data or [])}
        ms = supabase.table("memoir_sessions").select("id, recording_id, finished").eq("storyteller_user_id", user_id).execute()
        session_map = {s["recording_id"]: s for s in (ms.data or [])}
        bb = supabase.table("book_bibles").select("id, content, assembled_at").eq("storyteller_user_id", user_id).order("assembled_at", desc=True).limit(1).execute()
        book_bible = bb.data[0] if bb.data else None
        ch = supabase.table("chapters").select("id, title, sort_order, content, updated_at").eq("storyteller_user_id", user_id).order("sort_order").execute()
        chapters = ch.data or []
    else:
        db = _load_db(); _memoir_db_defaults(db)
        recordings = sorted([rec for rec in db["story_recordings"].values() if rec.get("storyteller_user_id") == user_id], key=lambda x: x.get("created_at", ""))
        prompt_map = {p["id"]: p["text"] for p in db.get("story_prompts", {}).values()}
        session_map = {s["recording_id"]: s for s in db["memoir_sessions"].values() if s.get("storyteller_user_id") == user_id}
        bbs = sorted([b for b in db["book_bibles"].values() if b.get("storyteller_user_id") == user_id], key=lambda x: x.get("assembled_at", ""), reverse=True)
        book_bible = bbs[0] if bbs else None
        chapters = sorted([c for c in db["chapters"].values() if c.get("storyteller_user_id") == user_id], key=lambda x: x.get("sort_order", 0))
    for rec in recordings:
        rec["prompt_text"] = prompt_map.get(rec.get("prompt_id") or "", "Custom question")
        session = session_map.get(rec["id"])
        rec["deepening_status"] = "finished" if session and session.get("finished") else ("started" if session else "none")
        rec["memoir_session_id"] = session["id"] if session else None
    return {
        "invitee": {"id": st_user["id"], "first_name": st_user.get("first_name", ""), "last_name": st_user.get("last_name", ""), "email": st_user["email"], "code_tier": code_tier},
        "recordings": recordings,
        "book_bible": book_bible,
        "chapters": chapters,
    }


@app.post("/api/portal/invitee/{storyteller_id}/memoir/assemble")
async def portal_invitee_assemble(storyteller_id: str, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    user_id = st_user["id"]
    if supabase:
        r = supabase.table("story_recordings").select("id, prompt_id, transcript, created_at").eq("storyteller_user_id", user_id).order("created_at").execute()
        recordings = r.data or []
        prompt_ids = [rec["prompt_id"] for rec in recordings if rec.get("prompt_id")]
        prompt_map = {}
        if prompt_ids:
            pr = supabase.table("story_prompts").select("id, text").in_("id", prompt_ids).execute()
            prompt_map = {p["id"]: p["text"] for p in (pr.data or [])}
        ms = supabase.table("memoir_sessions").select("recording_id, messages").eq("storyteller_user_id", user_id).eq("finished", True).execute()
        sessions_by_recording = {s["recording_id"]: s["messages"] for s in (ms.data or [])}
    else:
        db = _load_db(); _memoir_db_defaults(db)
        recordings = sorted([rec for rec in db["story_recordings"].values() if rec.get("storyteller_user_id") == user_id], key=lambda x: x.get("created_at", ""))
        prompt_map = {p["id"]: p["text"] for p in db.get("story_prompts", {}).values()}
        sessions_by_recording = {s["recording_id"]: s["messages"] for s in db["memoir_sessions"].values() if s.get("storyteller_user_id") == user_id and s.get("finished")}
    if not recordings:
        raise HTTPException(status_code=400, detail="No recordings found to assemble")
    context_parts = []
    for rec in recordings:
        question = prompt_map.get(rec.get("prompt_id") or "", "Custom question")
        context_parts.append(f"QUESTION: {question}\nANSWER: {rec.get('transcript', '')}")
        if rec["id"] in sessions_by_recording:
            msgs = sessions_by_recording[rec["id"]]
            exchanges = [f"  {'AI' if m['role'] == 'assistant' else 'User'}: {m['content']}" for m in msgs]
            context_parts.append("FOLLOW-UP CONVERSATION:\n" + "\n".join(exchanges))
        context_parts.append("")
    full_context = "\n".join(context_parts)
    content = _generate_memoir_response(MEMOIR_ASSEMBLE_SYSTEM, [{"role": "user", "content": full_context}], max_tokens=2000)
    bible_id = "bible_" + secrets.token_hex(8)
    now = _utc_now()
    if supabase:
        supabase.table("book_bibles").insert({"id": bible_id, "storyteller_user_id": user_id, "content": content, "assembled_at": now}).execute()
    else:
        db["book_bibles"][bible_id] = {"id": bible_id, "storyteller_user_id": user_id, "content": content, "assembled_at": now}
        _save_db(db)
    return {"book_bible_id": bible_id, "content": content}


@app.get("/api/portal/invitee/{storyteller_id}/memoir/chapters")
async def portal_invitee_get_chapters(storyteller_id: str, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    user_id = st_user["id"]
    if supabase:
        r = supabase.table("chapters").select("*").eq("storyteller_user_id", user_id).order("sort_order").execute()
        return {"chapters": r.data or []}
    db = _load_db(); _memoir_db_defaults(db)
    chapters = sorted([c for c in db["chapters"].values() if c.get("storyteller_user_id") == user_id], key=lambda x: x.get("sort_order", 0))
    return {"chapters": chapters}


@app.put("/api/portal/invitee/{storyteller_id}/memoir/chapters/{chapter_id}")
async def portal_invitee_save_chapter(storyteller_id: str, chapter_id: str, payload: MemoirChapterRequest, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    updates = {"title": payload.title, "content": payload.content, "updated_at": _utc_now()}
    if supabase:
        supabase.table("chapters").update(updates).eq("id", chapter_id).eq("storyteller_user_id", st_user["id"]).execute()
    else:
        db = _load_db(); _memoir_db_defaults(db)
        if chapter_id in db["chapters"]:
            db["chapters"][chapter_id].update(updates)
        _save_db(db)
    return {"ok": True}


@app.post("/api/portal/invitee/{storyteller_id}/memoir/chapters/{chapter_id}/edit")
async def portal_invitee_chapter_edit(storyteller_id: str, chapter_id: str, payload: MemoirChapterEditRequest, authorization: Optional[str] = Header(default=None)):
    portal_user = _auth_user(authorization)
    st_user = _verify_portal_owns_storyteller(portal_user, storyteller_id)
    user_id = st_user["id"]
    if supabase:
        r = supabase.table("chapters").select("*").eq("id", chapter_id).eq("storyteller_user_id", user_id).limit(1).execute()
        chapter = r.data[0] if r.data else None
    else:
        db = _load_db(); _memoir_db_defaults(db)
        c = db["chapters"].get(chapter_id)
        chapter = c if c and c.get("storyteller_user_id") == user_id else None
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    messages = chapter.get("edit_messages") or []
    if not messages:
        system = MEMOIR_EDIT_SYSTEM + f"\n\nHere are the raw transcripts for this chapter:\n\n{chapter.get('content', '')}"
        messages.append({"role": "user", "content": "Please give me your initial editorial feedback on this chapter."})
        opening = _generate_memoir_response(system, messages)
        messages.append({"role": "assistant", "content": opening})
    messages.append({"role": "user", "content": payload.message})
    system = MEMOIR_EDIT_SYSTEM + f"\n\nHere are the raw transcripts for this chapter:\n\n{chapter.get('content', '')}"
    reply = _generate_memoir_response(system, messages)
    messages.append({"role": "assistant", "content": reply})
    if supabase:
        supabase.table("chapters").update({"edit_messages": messages, "updated_at": _utc_now()}).eq("id", chapter_id).execute()
    else:
        db["chapters"][chapter_id]["edit_messages"] = messages
        db["chapters"][chapter_id]["updated_at"] = _utc_now()
        _save_db(db)
    return {"message": reply}


# ----------------------------------------------------
# Data access layer — Supabase (primary) + JSON fallback
# ----------------------------------------------------

def _get_user(email: str) -> Optional[Dict[str, Any]]:
    if supabase:
        r = supabase.table("users").select("*").eq("email", email).limit(1).execute()
        return r.data[0] if r.data else None
    db = _load_db()
    return db["users"].get(email)


def _create_user(user: Dict[str, Any]):
    if supabase:
        supabase.table("users").insert(user).execute()
        return
    db = _load_db()
    db["users"][user["email"]] = user
    _save_db(db)


def _update_user(email: str, updates: Dict[str, Any]):
    if supabase:
        supabase.table("users").update(updates).eq("email", email).execute()
        return
    db = _load_db()
    if email in db["users"]:
        db["users"][email].update(updates)
    _save_db(db)


def _get_cogna(cogna_id: str) -> Dict[str, Any]:
    if supabase:
        r = supabase.table("cognas").select("*").eq("id", cogna_id).limit(1).execute()
        cogna = r.data[0] if r.data else None
    else:
        db = _load_db()
        cogna = db["cognas"].get(cogna_id)
    if not cogna:
        raise HTTPException(status_code=404, detail="Cogna not found")
    return cogna


def _list_cognas(owner_email: str) -> List[Dict[str, Any]]:
    if supabase:
        r = supabase.table("cognas").select("*").eq("owner_email", owner_email).order("created_at").execute()
        return r.data or []
    db = _load_db()
    return [c for c in db["cognas"].values() if c.get("owner_email") == owner_email]


def _create_cogna(cogna: Dict[str, Any]):
    if supabase:
        supabase.table("cognas").insert(cogna).execute()
        return
    db = _load_db()
    db["cognas"][cogna["id"]] = cogna
    # Keep cogna_ids list on user for local JSON compat
    user = db["users"].get(cogna["owner_email"])
    if user and cogna["id"] not in user.get("cogna_ids", []):
        user.setdefault("cogna_ids", []).append(cogna["id"])
    _save_db(db)


def _update_cogna(cogna_id: str, updates: Dict[str, Any]):
    if supabase:
        supabase.table("cognas").update(updates).eq("id", cogna_id).execute()
        return
    db = _load_db()
    if cogna_id in db["cognas"]:
        db["cognas"][cogna_id].update(updates)
    _save_db(db)


def _delete_cogna(cogna_id: str):
    if supabase:
        supabase.table("cognas").delete().eq("id", cogna_id).execute()
        return
    db = _load_db()
    cogna = db["cognas"].pop(cogna_id, None)
    if cogna:
        user = db["users"].get(cogna.get("owner_email", ""))
        if user:
            user["cogna_ids"] = [cid for cid in user.get("cogna_ids", []) if cid != cogna_id]
    _save_db(db)


def _find_user_by_code(code: str) -> Optional[Dict[str, Any]]:
    if supabase:
        r = supabase.table("users").select("*").eq("child_access_code", code).limit(1).execute()
        return r.data[0] if r.data else None
    db = _load_db()
    for user in db["users"].values():
        if user.get("child_access_code", "").upper() == code:
            return user
    return None


def _save_session(session_id: str, primary_cogna_id: str, cogna_ids: List[str],
                  voice_names: List[str], transcript: List[Dict], duration_seconds: int):
    if supabase:
        supabase.table("conversation_sessions").insert({
            "id": session_id,
            "primary_cogna_id": primary_cogna_id,
            "cogna_ids": cogna_ids,
            "voice_names": voice_names,
            "transcript": transcript,
            "duration_seconds": duration_seconds,
        }).execute()
        return
    # Local JSON fallback
    session_dir = SESSIONS_DIR / primary_cogna_id
    session_dir.mkdir(parents=True, exist_ok=True)
    session_data = {
        "cogna_ids": cogna_ids,
        "voice_names": voice_names,
        "transcript": transcript,
        "duration_seconds": duration_seconds,
        "saved_at": _utc_now(),
    }
    with open(session_dir / f"{session_id}.json", "w", encoding="utf-8") as f:
        json.dump(session_data, f, indent=2)


def _list_sessions(primary_cogna_id: str) -> List[Dict[str, Any]]:
    if supabase:
        r = (supabase.table("conversation_sessions")
             .select("id, saved_at, voice_names, duration_seconds, transcript")
             .eq("primary_cogna_id", primary_cogna_id)
             .order("saved_at", desc=True)
             .limit(20)
             .execute())
        rows = r.data or []
        return [
            {
                "session_id": row["id"],
                "saved_at": row.get("saved_at"),
                "voice_names": row.get("voice_names", []),
                "duration_seconds": row.get("duration_seconds", 0),
                "turns": len([e for e in (row.get("transcript") or []) if e.get("role") == "user"]),
            }
            for row in rows
        ]
    # Local JSON fallback
    session_dir = SESSIONS_DIR / primary_cogna_id
    sessions = []
    if session_dir.exists():
        for f in sorted(session_dir.glob("session_*.json"), reverse=True)[:20]:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            sessions.append({
                "session_id": f.stem,
                "saved_at": data.get("saved_at"),
                "voice_names": data.get("voice_names", []),
                "duration_seconds": data.get("duration_seconds", 0),
                "turns": len([e for e in data.get("transcript", []) if e.get("role") == "user"]),
            })
    return sessions


# ----------------------------------------------------
# Storyteller auth helpers
# ----------------------------------------------------

def _user_custom_prompts(user: Dict[str, Any]) -> List[Dict[str, Any]]:
    cp = user.get("custom_prompts") or []
    return cp if isinstance(cp, list) else []


def _this_month_recording_count(user_id: str) -> int:
    from datetime import date
    month_start = date.today().replace(day=1).isoformat()
    if supabase:
        r = (supabase.table("story_recordings")
             .select("id", count="exact")
             .eq("storyteller_user_id", user_id)
             .gte("created_at", month_start)
             .execute())
        return r.count or 0
    db = _load_db()
    return sum(
        1 for rec in db["story_recordings"].values()
        if rec.get("storyteller_user_id") == user_id
        and rec.get("created_at", "") >= month_start
    )


def _get_storyteller_user(email: str) -> Optional[Dict[str, Any]]:
    if supabase:
        r = supabase.table("storyteller_users").select("*").eq("email", email).limit(1).execute()
        return r.data[0] if r.data else None
    db = _load_db()
    return db.get("storyteller_users", {}).get(email)


def _get_storyteller_user_by_id(storyteller_id: str) -> Optional[Dict[str, Any]]:
    if supabase:
        r = supabase.table("storyteller_users").select("*").eq("id", storyteller_id).limit(1).execute()
        return r.data[0] if r.data else None
    db = _load_db()
    for u in db.get("storyteller_users", {}).values():
        if u.get("id") == storyteller_id:
            return u
    return None


def _verify_portal_owns_storyteller(portal_user: Dict, storyteller_id: str) -> Dict[str, Any]:
    """Return storyteller record if the portal admin owns the invite code they used."""
    st_user = _get_storyteller_user_by_id(storyteller_id)
    if not st_user:
        raise HTTPException(status_code=404, detail="Storyteller not found")
    signup_code = st_user.get("signup_code")
    if not signup_code:
        raise HTTPException(status_code=403, detail="This storyteller did not sign up with your code")
    if supabase:
        r = supabase.table("promo_codes").select("created_by").eq("code", signup_code).limit(1).execute()
        created_by = r.data[0].get("created_by") if r.data else None
    else:
        db = _load_db()
        pc = next((v for v in db.get("promo_codes", {}).values() if v.get("code") == signup_code), None)
        created_by = pc.get("created_by") if pc else None
    if created_by != portal_user["email"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return st_user


def _create_storyteller_user(user: Dict[str, Any]):
    if supabase:
        supabase.table("storyteller_users").insert(user).execute()
        return
    db = _load_db()
    db.setdefault("storyteller_users", {})[user["email"]] = user
    _save_db(db)


def _update_storyteller_user(email: str, updates: Dict[str, Any]):
    if supabase:
        supabase.table("storyteller_users").update(updates).eq("email", email).execute()
        return
    db = _load_db()
    if email in db.get("storyteller_users", {}):
        db["storyteller_users"][email].update(updates)
    _save_db(db)


def _auth_storyteller_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required. Please sign in.")
    token = authorization.split(" ", 1)[1].strip()
    email = SESSIONS.get(token)
    if not email:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    user = _get_storyteller_user(email)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _create_story_session(email: str) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = email
    return token


# ----------------------------------------------------
# Storyteller data helpers
# ----------------------------------------------------

def _get_hidden_prompt_ids(portal_user_email: str) -> List[str]:
    if supabase:
        r = supabase.table("users").select("hidden_prompt_ids").eq("email", portal_user_email).limit(1).execute()
        return r.data[0].get("hidden_prompt_ids") or [] if r.data else []
    db = _load_db()
    return db.get("users", {}).get(portal_user_email, {}).get("hidden_prompt_ids") or []


def _set_hidden_prompt_ids(portal_user_email: str, ids: List[str]) -> None:
    if supabase:
        supabase.table("users").update({"hidden_prompt_ids": ids}).eq("email", portal_user_email).execute()
    else:
        db = _load_db()
        if portal_user_email in db.get("users", {}):
            db["users"][portal_user_email]["hidden_prompt_ids"] = ids
        _save_db(db)


def _get_portal_owner_email(st_user: Optional[Dict]) -> Optional[str]:
    signup_code = st_user.get("signup_code") if st_user else None
    if not signup_code:
        return None
    if supabase:
        r = supabase.table("promo_codes").select("created_by").eq("code", signup_code).limit(1).execute()
        return r.data[0].get("created_by") if r.data else None
    db = _load_db()
    pc = db["promo_codes"].get(signup_code)
    return pc.get("created_by") if pc else None


def _get_active_prompts(portal_user_email: Optional[str] = None, include_system: bool = True) -> List[Dict[str, Any]]:
    hidden = set(_get_hidden_prompt_ids(portal_user_email)) if portal_user_email else set()
    if supabase:
        results = []
        if include_system:
            sys_r = (supabase.table("story_prompts").select("*")
                     .eq("active", True).is_("portal_user_email", "null")
                     .order("sort_order").order("created_at").execute())
            results = [p for p in (sys_r.data or []) if p["id"] not in hidden]
        if portal_user_email:
            custom_r = (supabase.table("story_prompts").select("*")
                        .eq("active", True).eq("portal_user_email", portal_user_email)
                        .order("sort_order").order("created_at").execute())
            results = results + (custom_r.data or [])
            results.sort(key=lambda x: (x.get("sort_order", 0), x.get("created_at", "")))
        return results
    db = _load_db()
    active = [p for p in db["story_prompts"].values() if p.get("active")]
    if portal_user_email:
        custom = [p for p in active if p.get("portal_user_email") == portal_user_email]
        if include_system:
            system = [p for p in active if not p.get("portal_user_email") and p["id"] not in hidden]
            return sorted(system + custom, key=lambda x: (x.get("sort_order", 0), x.get("created_at", "")))
        return sorted(custom, key=lambda x: (x.get("sort_order", 0), x.get("created_at", "")))
    if not include_system:
        return []
    system_only = [p for p in active if not p.get("portal_user_email")]
    return sorted(system_only, key=lambda x: (x.get("sort_order", 0), x.get("created_at", "")))


def _get_promo_code(code: str) -> Optional[Dict[str, Any]]:
    if supabase:
        r = (supabase.table("promo_codes").select("*")
             .eq("code", code).eq("active", True).limit(1).execute())
        return r.data[0] if r.data else None
    db = _load_db()
    record = db["promo_codes"].get(code)
    return record if record and record.get("active") else None


def _generate_story_promo_code(tier: str = "A") -> str:
    chars = string.ascii_uppercase + string.digits
    prefix = tier.upper() if tier.upper() in {"A", "B", "C", "D", "E", "F"} else "A"
    for _ in range(20):
        suffix = "".join(secrets.choice(chars) for _ in range(4))
        code = f"{prefix}-{suffix}"
        if not _get_promo_code(code):
            return code
    return f"{prefix}-{''.join(secrets.choice(chars) for _ in range(6))}"


def _save_story_audio(recording_id: str, file: UploadFile) -> str:
    ext = Path(file.filename or "audio.webm").suffix.lower() or ".webm"
    filename = f"{recording_id}{ext}"
    content = file.file.read()

    if supabase:
        storage_path = f"recordings/{filename}"
        mime = {
            ".webm": "audio/webm", ".mp3": "audio/mpeg", ".wav": "audio/wav",
            ".m4a": "audio/mp4", ".ogg": "audio/ogg",
        }.get(ext, "audio/webm")
        supabase.storage.from_("story-audio").upload(
            path=storage_path,
            file=content,
            file_options={"content-type": mime, "upsert": "true"},
        )
        return supabase.storage.from_("story-audio").get_public_url(storage_path)

    out_dir = STORY_RECORDINGS_DIR / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    with open(out_path, "wb") as f:
        f.write(content)
    return f"/story-audio/{filename}"


# ----------------------------------------------------
# Auth helpers
# ----------------------------------------------------

def _auth_user(authorization: Optional[str]) -> Dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    email = SESSIONS.get(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = _get_user(email)
    if not user:
        raise HTTPException(status_code=401, detail="User no longer exists")
    return user


def _create_session(email: str) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = email
    return token


def _public_user(user: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "email": user["email"],
        "name": user.get("name", ""),
        "first_name": user.get("first_name", ""),
        "last_name": user.get("last_name", ""),
        "setup_type": user.get("setup_type", "guardian"),
        "tier": user.get("tier", "A"),
        "child_access_code": user.get("child_access_code") or "",
        "role": user.get("role", "portal_admin"),
    }


# ----------------------------------------------------
# File upload helper — Supabase Storage (primary) + local fallback
# ----------------------------------------------------

def _save_cogna_upload(cogna_id: str, kind: str, file: UploadFile) -> str:
    """Upload voice sample or photo. Returns Supabase CDN URL (or local path as fallback)."""
    ext = Path(file.filename or "upload.bin").suffix.lower()
    filename = f"{kind}-{int(datetime.now().timestamp())}{ext}"

    content = file.file.read()

    if supabase:
        storage_path = f"{cogna_id}/{filename}"
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
        return supabase.storage.from_("cogna-uploads").get_public_url(storage_path)

    # Local fallback
    cogna_dir = PORTAL_UPLOAD_DIR / cogna_id
    cogna_dir.mkdir(parents=True, exist_ok=True)
    path = cogna_dir / filename
    with open(path, "wb") as out:
        out.write(content)
    return str(path.relative_to(ROOT))


# ----------------------------------------------------
# Local JSON fallback (used when SUPABASE_URL is not set)
# ----------------------------------------------------

def _load_db() -> Dict[str, Any]:
    if not PORTAL_DB_PATH.exists():
        db = {"users": {}, "cognas": {}, "story_prompts": {}, "promo_codes": {}, "story_recordings": {}, "storyteller_users": {}, "created_at": _utc_now()}
        _save_db(db)
        return db
    with open(PORTAL_DB_PATH, "r", encoding="utf-8") as f:
        db = json.load(f)
    db.setdefault("users", {})
    db.setdefault("cognas", {})
    db.setdefault("story_prompts", {})
    db.setdefault("promo_codes", {})
    db.setdefault("story_recordings", {})
    db.setdefault("storyteller_users", {})
    db.setdefault("memoir_sessions", {})
    db.setdefault("book_bibles", {})
    db.setdefault("chapters", {})
    return db


def _save_db(db: Dict[str, Any]):
    with open(PORTAL_DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


# ----------------------------------------------------
# Voice / audio helpers
# ----------------------------------------------------

def _cogna_voice_prompt(cogna: Dict[str, Any]) -> str:
    p = cogna.get("params", {})
    name = cogna["name"]
    relationship = cogna.get("relationship", "")
    tod = cogna.get("term_of_endearment", "")

    warmth_desc = (
        "lead with tenderness and emotional safety"
        if p.get("warmth", 50) < 50
        else "be candid and direct, offering straight talk over softness"
    )
    validation_desc = (
        "primarily affirm and reflect feelings back"
        if p.get("validation", 50) < 50
        else "gently challenge, ask hard questions, and invite growth"
    )
    tone_desc = (
        "bring lightness, humor, and ease when appropriate"
        if p.get("tone", 50) < 50
        else "hold space with gravity, weight, and emotional presence"
    )
    structure_desc = (
        "offer clear steps and practical guidance"
        if p.get("structure", 50) < 50
        else "ask open-ended questions and invite the person to find their own way"
    )
    stance_desc = (
        "wrap around and protect, making them feel safe"
        if p.get("stance", 50) < 50
        else "believe in their capability and nudge them toward their own strength"
    )

    tod_line = f" Address them as '{tod}'." if tod else ""

    return (
        f"You are {name}, a {relationship}.{tod_line} "
        f"When you respond: {warmth_desc}. "
        f"You tend to {validation_desc}. "
        f"In terms of tone, {tone_desc}. "
        f"For guidance, {structure_desc}. "
        f"Your stance is to {stance_desc}. "
        f"Keep responses warm, concise, and human — 1 to 3 sentences. "
        f"Ask only one question at a time, then stop and wait. "
        f"Never pile on multiple questions or continue speaking into silence. "
        f"Never use emojis or emoticons — your words are spoken aloud. "
        f"Maintain a steady emotional presence — let the overall mood of the conversation guide your tone, not any single sentence or word. Do not dramatically shift energy between sentences; stay grounded and consistent."
    )


def _generate_child_access_code(tier: str = "D") -> str:
    chars = string.ascii_uppercase + string.digits
    suffix = "".join(secrets.choice(chars) for _ in range(4))
    # D-tier gets D-XXXX; other tiers keep COGNA- prefix for backward compat
    if tier == "D":
        return f"D-{suffix}"
    return f"COGNA-{suffix}"


# ----------------------------------------------------
# Usage tracking helpers (AI Companion minute cap)
# ----------------------------------------------------

def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _get_usage(email: str, month: str) -> float:
    if supabase:
        r = (supabase.table("usage_tracking")
             .select("minutes")
             .eq("user_email", email)
             .eq("month", month)
             .limit(1)
             .execute())
        return float(r.data[0]["minutes"]) if r.data else 0.0
    db = _load_db()
    key = f"{email}|{month}"
    return float(db.get("usage_tracking", {}).get(key, {}).get("minutes", 0.0))


def _add_usage(email: str, month: str, minutes: float):
    if minutes <= 0:
        return
    if supabase:
        existing = _get_usage(email, month)
        uid = f"usage_{email}_{month}".replace("@", "_").replace(".", "_")
        if existing > 0:
            (supabase.table("usage_tracking")
             .update({"minutes": existing + minutes, "updated_at": _utc_now()})
             .eq("user_email", email).eq("month", month)
             .execute())
        else:
            (supabase.table("usage_tracking")
             .insert({"id": uid, "user_email": email, "month": month, "minutes": minutes})
             .execute())
    else:
        db = _load_db()
        if "usage_tracking" not in db:
            db["usage_tracking"] = {}
        key = f"{email}|{month}"
        entry = db["usage_tracking"].get(key, {"minutes": 0.0})
        entry["minutes"] = entry["minutes"] + minutes
        db["usage_tracking"][key] = entry
        _save_db(db)


def _generate_cogna_audio(cogna: Dict[str, Any], text: str) -> str:
    voice_backend = cogna.get("voice_backend", "tts")
    cache_key = hashlib.sha256(f"{cogna['id']}|{text}".encode("utf-8")).hexdigest()

    if voice_backend == "elevenlabs":
        voice_id = cogna.get("elevenlabs_voice_id")
        if not voice_id:
            raise HTTPException(status_code=400, detail="No ElevenLabs voice ID set for this Cogna")
        audio_filename = f"{cache_key}.mp3"
        audio_path = CACHE_DIR / audio_filename
        if not audio_path.exists():
            tmp = _elevenlabs_tts(text, voice_id)
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(tmp), str(audio_path))
    elif voice_backend == "seed_vc":
        audio_filename = f"{cache_key}.wav"
        audio_path = CACHE_DIR / audio_filename
        if not audio_path.exists():
            base_audio = _text_to_speech(text)
            voice_ref = None
            if cogna.get("voice_sample"):
                vpath = ROOT / cogna["voice_sample"]
                voice_ref = vpath if vpath.exists() else None
            _seed_vc_convert(base_audio, cogna["name"], audio_path, voice_ref)
    else:  # tts — OpenAI TTS
        audio_filename = f"{cache_key}.mp3"
        audio_path = CACHE_DIR / audio_filename
        if not audio_path.exists():
            tts_voice = cogna.get("params", {}).get("tts_voice", "nova")
            base_audio = _text_to_speech(text, tts_voice)
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(base_audio), str(audio_path))

    return f"/audio/{audio_filename}"


def _generate_text_response(system_prompt: str, messages: List[Dict]) -> str:
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        temperature=0.7,
        system=system_prompt,
        messages=messages,
    )
    return response.content[0].text


def _generate_memoir_response(system_prompt: str, messages: List[Dict], max_tokens: int = 1000) -> str:
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
    except Exception as e:
        print(f"[MEMOIR] Claude API error: {type(e).__name__}: {e}")
        raise


def _transcribe_audio(upload: UploadFile) -> str:
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY is required to transcribe audio")

    suffix = Path(upload.filename or "recording.webm").suffix or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(upload.file.read())
        tmp_path = Path(tmp.name)

    try:
        with open(tmp_path, "rb") as f:
            resp = openai_client.audio.transcriptions.create(model="whisper-1", file=f)
        return getattr(resp, "text", None) or resp.get("text", "")
    finally:
        try:
            tmp_path.unlink()
        except Exception:
            pass


def _text_to_speech(text: str, voice: str = "nova") -> Path:
    """Generate speech using OpenAI TTS."""
    if not openai_client:
        raise RuntimeError("OPENAI_API_KEY is required for text-to-speech")

    out = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    out_path = Path(out.name)
    out.close()

    response = openai_client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )
    response.stream_to_file(out_path)
    return out_path


def _elevenlabs_tts(text: str, voice_id: str) -> Path:
    import requests as _requests

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("ELEVENLABS_API_KEY not set")

    model_id = CONFIG.get("voice_defaults", {}).get("elevenlabs_model", "eleven_monolingual_v1")
    resp = _requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": text, "model_id": model_id},
        timeout=30,
    )
    resp.raise_for_status()

    out = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    out_path = Path(out.name)
    out.write(resp.content)
    out.close()
    return out_path


# ----------------------------------------------------
# Seed-VC singleton (lazy-loaded, lives for server lifetime)
# ----------------------------------------------------

_seed_vc_instance = None


def _get_seed_vc():
    global _seed_vc_instance
    if _seed_vc_instance is None:
        import sys
        seed_vc_dir = ROOT.parent.parent / "vendor" / "seed-vc"
        if str(seed_vc_dir) not in sys.path:
            sys.path.insert(0, str(seed_vc_dir))
        from seed_vc_wrapper import SeedVCWrapper
        _seed_vc_instance = SeedVCWrapper()
    return _seed_vc_instance


def _seed_vc_convert(base_audio_path: Path, persona: str, out_path: Path, voice_reference: Optional[Path] = None):
    """Convert base audio to target voice using Seed-VC. Falls back to plain TTS if anything fails."""
    import subprocess as _sp

    out_path.parent.mkdir(parents=True, exist_ok=True)

    if voice_reference is None or not voice_reference.exists():
        shutil.copyfile(base_audio_path, out_path)
        return

    ref_wav_path: Optional[Path] = None
    ref_path = voice_reference
    if voice_reference.suffix.lower() in {".m4a", ".mp3", ".aac", ".ogg"}:
        ref_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        ref_wav_path = Path(ref_wav.name)
        ref_wav.close()
        _sp.run(
            ["afconvert", "-f", "WAVE", "-d", "LEI16", str(voice_reference), str(ref_wav_path)],
            check=True, timeout=30,
        )
        ref_path = ref_wav_path

    try:
        import torch
        import torchaudio

        wrapper = _get_seed_vc()

        sr_out = 22050
        audio_array = None

        for _, full_audio in wrapper.convert_voice(
            source=str(base_audio_path),
            target=str(ref_path),
            diffusion_steps=10,
            length_adjust=1.0,
            inference_cfg_rate=0.7,
            f0_condition=False,
            auto_f0_adjust=False,
            pitch_shift=0,
            stream_output=True,
        ):
            if full_audio is not None:
                sr_out, audio_array = full_audio
                break

        if audio_array is not None:
            audio_tensor = torch.from_numpy(audio_array).unsqueeze(0).float()
            torchaudio.save(str(out_path), audio_tensor, sr_out)
        else:
            shutil.copyfile(base_audio_path, out_path)

    except Exception:
        shutil.copyfile(base_audio_path, out_path)

    finally:
        if ref_wav_path and ref_wav_path.exists():
            ref_wav_path.unlink(missing_ok=True)


# ----------------------------------------------------
# Misc helpers
# ----------------------------------------------------

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _validate_upload(filename: Optional[str], allowed: set):
    ext = Path(filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
