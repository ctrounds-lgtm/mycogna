---
name: watch-video
description: "Watch and analyze video content by extracting visual frames and transcribing speech. Use when the user shares a video URL (YouTube, YouTube Shorts, or direct video link), a local video file path, or asks to watch/review/analyze any video. Triggers on: video URLs, 'watch this video', 'can you see this video', 'review this clip', 'what happens in this video', or any request involving video content understanding."
---

# Watch Video

Analyze videos by extracting keyframes and transcribing audio, enabling full visual + audio understanding of video content.

## Workflow

### 1. Run the extraction script

```bash
python3 scripts/watch-video.py "<video_path_or_url>"
```

Accepts:
- YouTube URLs (`youtube.com/watch?v=...`, `youtube.com/shorts/...`, `youtu.be/...`)
- Direct video URLs (`.mp4`, `.mov`, `.webm`, etc.)
- Local file paths

Optional: `--interval SECONDS` to override auto frame interval.

Output lands in `outputs/video-analysis/<name>/`.

### 2. Read the summary

Read `summary.txt` from the output directory — contains metadata, frame paths, and full transcript with timestamps.

### 3. View frames

Use the Read tool on frame images in the `frames/` subdirectory:
- **Short videos (<30s):** View all frames or every other frame
- **Medium videos (30s–5min):** Sample 8–12 frames spread across the timeline, plus frames near key transcript moments
- **Long videos (5min+):** Sample 10–15 frames at key intervals, prioritize frames near important transcript segments

### 4. Synthesize and present

Combine visual + audio understanding into a summary:
- What the video shows (scenes, on-screen text, people, actions, style)
- What is said (key points from transcript)
- Overall purpose and content type
- Observations relevant to the user's specific question

## Auto Frame Interval

| Video length | Frame interval |
|---|---|
| ≤15s | Every 1s |
| 15s–1min | Every 2s |
| 1–5min | Every 5s |
| 5–15min | Every 10s |
| 15min+ | Every 15s |

## Dependencies

- `ffmpeg` (system) — frame and audio extraction
- `whisper` (Python) — speech transcription
- `yt-dlp` (Python) — video downloads from URLs

## Scripts

- `scripts/watch-video.py` — Core pipeline: download → extract frames → extract audio → transcribe → structured output
