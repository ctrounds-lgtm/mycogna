# Cogna App (Support Companion)

This folder contains the code and configuration for the **Cogna support app** — a mobile/web companion that responds to a child in the voice and style of their family members (Mom/Dad/Callie/Gracie).

## Goals
- Use **Claude API** to create text responses in the style of a chosen family member.
- Use **local TTS** + **Seed-VC** to convert those responses into that family member's voice.
- Serve audio to a mobile/web client via a lightweight server.

## Structure
- `server.py` — example FastAPI server.
- `config.sample.json` — starter config for family member personality prompts and voice names.
- `requirements.txt` — dependencies required to run the server.

## Getting Started
1. Copy and customize the config:

```bash
cp apps/cogna/config.sample.json apps/cogna/config.json
```

2. Install dependencies (preferably in a virtualenv):

```bash
python -m pip install -r apps/cogna/requirements.txt
```

3. Run the server:

```bash
uvicorn apps.cogna.server:app --reload --port 8000
```

4. Visit:

- `http://localhost:8000/docs` for interactive API docs
- `http://localhost:8000/` for the basic landing page
