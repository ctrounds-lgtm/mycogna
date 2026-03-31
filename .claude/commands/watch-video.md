# Watch Video

> Analyze a video so Becca can "watch" it — extracting visual frames and speech transcription.

## Input

$ARGUMENTS — a local file path, YouTube URL, or other video URL

## Process

1. **Run the video analysis script:**

```
python3 scripts/watch-video.py "$ARGUMENTS"
```

This will:
- Download the video if it's a URL (using yt-dlp)
- Extract keyframes at smart intervals (auto-scales: 1s for short clips, up to 15s for long videos)
- Extract and transcribe all speech using Whisper
- Save everything to `outputs/video-analysis/<name>/`

2. **Read the summary file** from the output directory — it contains metadata, frame paths, and the full transcript.

3. **View the extracted frames** — use the Read tool to look at frames from the `frames/` subdirectory. For short videos, view all frames. For longer videos, sample frames spread across the timeline plus any that correspond to key moments in the transcript.

4. **Synthesize your understanding** and present to the user:
   - What the video shows visually (scenes, text on screen, people, actions)
   - What is said (key points from the transcript)
   - Overall summary of the video's content and purpose
   - Any specific observations relevant to what the user asked about

## Notes

- For YouTube videos, just paste the URL
- For local files, use the full path or path relative to the workspace
- Frame interval auto-adjusts to video length — override with `--interval SECONDS` if needed
- Short clips (<15s) capture every second, longer videos sample less frequently
- If transcription shows "(No speech detected)" the video may be music-only or silent

## Example Usage

```
/watch-video https://www.youtube.com/watch?v=example
/watch-video /path/to/local/video.mp4
/watch-video outputs/heygen/my-video.mp4
```
