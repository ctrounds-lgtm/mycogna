I# HeyGen

> Interact with HeyGen's AI video generation API from the workspace.

## What This Does

This command helps you create AI-generated videos using HeyGen's free tier. You can:

- **Quick video**: Give a text prompt, get a video back (Video Agent — 2 credits/min)
- **Avatar video**: Pick a specific avatar + voice + script (1 credit/min)
- **Browse**: List available avatars and voices
- **Check status**: Poll video generation progress
- **Download**: Save completed videos to `outputs/heygen/`

## Setup (First Time)

If no API key is configured yet, run setup:

```bash
./scripts/heygen.sh setup
```

This will prompt for your API key from https://app.heygen.com/settings?nav=API

## Based on User Request: $ARGUMENTS

Read what the user wants to do and help them accomplish it using the HeyGen script at `scripts/heygen.sh`.

### If the user wants to browse or explore:
- Run `./scripts/heygen.sh avatars` to show available avatars
- Run `./scripts/heygen.sh voices` to show available voices
- Help them pick good options for their use case

### If the user wants to create a video:
1. Confirm the API key is set up (check if `.heygen-api-key` exists)
2. Help them craft the prompt or script
3. Run the appropriate command:
   - Quick (text→video): `./scripts/heygen.sh quick "<prompt>"`
   - Avatar video: `./scripts/heygen.sh create <avatar_id> <voice_id> "<script>" "[title]"`
4. Save the video_id and check status
5. Download when complete

### If the user wants to check on a video:
- Run `./scripts/heygen.sh status <video_id>`
- If complete, offer to download with `./scripts/heygen.sh download <video_id>`

## Credit Costs (Free Tier = ~10 credits)

| Operation | Cost |
|-----------|------|
| Video Agent (quick) | 2 credits/min |
| Public Avatar (Engine III) | 1 credit/min |
| Photo Avatar | 1 credit/min |
| Video Translation (fast) | 3 credits/min |
| Text-to-Speech only | 0.02 credits/min |

Keep videos short to stay within free tier limits!
