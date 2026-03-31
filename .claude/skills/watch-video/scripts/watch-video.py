#!/usr/bin/env python3
"""
watch-video.py — Video analysis tool for Becca (Claude Code agent)

Takes a video (local file or URL), extracts keyframes + audio,
transcribes speech, and produces a structured output that Becca
can read to understand the video's content.

Usage:
    python3 watch-video.py <video_path_or_url> [--interval SECONDS] [--output-dir DIR]

Output:
    Creates a directory with:
    - frames/        — keyframes extracted at regular intervals (JPG)
    - transcript.txt — full speech transcription with timestamps
    - summary.txt    — metadata + frame list + transcript for Becca to read
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# yt-dlp may be in a non-PATH location
YTDLP_PATH = shutil.which("yt-dlp") or "/Users/claudelab/Library/Python/3.9/bin/yt-dlp"

def is_url(path: str) -> bool:
    return path.startswith("http://") or path.startswith("https://")

def download_video(url: str, output_dir: str) -> str:
    """Download video from URL using yt-dlp with fallback strategies."""
    output_path = os.path.join(output_dir, "source_video.%(ext)s")

    # Try multiple strategies — YouTube frequently blocks certain clients
    strategies = [
        # Strategy 1: Android client (most reliable as of 2025-2026)
        [YTDLP_PATH, "--extractor-args", "youtube:player_client=android",
         "-f", "b[height<=720]/b", "--no-playlist", "-o", output_path, url],
        # Strategy 2: Default client, any format
        [YTDLP_PATH, "-f", "b[height<=720]/b", "--no-playlist",
         "-o", output_path, url],
        # Strategy 3: Absolute fallback — no format filter
        [YTDLP_PATH, "--no-playlist", "-o", output_path, url],
    ]

    print(f"Downloading video from: {url}")
    for i, cmd in enumerate(strategies):
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            break
        print(f"  Strategy {i+1} failed, trying next..." if i < len(strategies)-1 else "")

    if result.returncode != 0:
        print(f"yt-dlp stderr: {result.stderr}")
        raise RuntimeError(f"Failed to download video: {result.stderr}")

    # Find the downloaded file
    for f in os.listdir(output_dir):
        if f.startswith("source_video"):
            return os.path.join(output_dir, f)
    raise RuntimeError("Download completed but file not found")

def get_video_info(video_path: str) -> dict:
    """Get video metadata via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return {}
    return json.loads(result.stdout)

def extract_frames(video_path: str, output_dir: str, interval: float) -> list:
    """Extract keyframes at regular intervals."""
    frames_dir = os.path.join(output_dir, "frames")
    os.makedirs(frames_dir, exist_ok=True)

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps=1/{interval},scale=1280:-1",
        "-q:v", "2",  # high quality JPEGs
        "-vsync", "vfr",
        os.path.join(frames_dir, "frame_%04d.jpg"),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg frame extraction warning: {result.stderr[:500]}")

    frames = sorted([
        os.path.join(frames_dir, f)
        for f in os.listdir(frames_dir)
        if f.endswith(".jpg")
    ])
    print(f"Extracted {len(frames)} frames (1 every {interval}s)")
    return frames

def extract_audio(video_path: str, output_dir: str) -> str:
    """Extract audio track as WAV for Whisper."""
    audio_path = os.path.join(output_dir, "audio.wav")
    cmd = [
        "ffmpeg", "-i", video_path,
        "-vn",               # no video
        "-acodec", "pcm_s16le",
        "-ar", "16000",      # 16kHz for Whisper
        "-ac", "1",          # mono
        audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Audio extraction warning: {result.stderr[:500]}")
        return ""

    # Check if audio file is essentially empty/silent
    file_size = os.path.getsize(audio_path)
    if file_size < 10000:  # less than ~10KB = probably no real audio
        print("Audio track appears empty or very short — skipping transcription")
        return ""

    return audio_path

def transcribe_audio(audio_path: str) -> list:
    """Transcribe audio using Whisper."""
    if not audio_path or not os.path.exists(audio_path):
        return []

    print("Transcribing audio with Whisper (this may take a moment)...")
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, verbose=False)
        segments = []
        for seg in result.get("segments", []):
            segments.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"].strip(),
            })
        print(f"Transcribed {len(segments)} segments")
        return segments
    except Exception as e:
        print(f"Transcription failed: {e}")
        return []

def format_timestamp(seconds: float) -> str:
    """Format seconds to MM:SS."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

def build_output(video_path: str, output_dir: str, frames: list,
                 segments: list, info: dict, source: str, interval: float):
    """Build the structured output files Becca will read."""

    # Transcript file
    transcript_path = os.path.join(output_dir, "transcript.txt")
    with open(transcript_path, "w") as f:
        if segments:
            for seg in segments:
                ts = format_timestamp(seg["start"])
                f.write(f"[{ts}] {seg['text']}\n")
        else:
            f.write("(No speech detected or audio unavailable)\n")

    # Video metadata
    duration = "unknown"
    resolution = "unknown"
    if info:
        fmt = info.get("format", {})
        duration_s = float(fmt.get("duration", 0))
        duration = format_timestamp(duration_s) if duration_s else "unknown"
        for stream in info.get("streams", []):
            if stream.get("codec_type") == "video":
                w = stream.get("width", "?")
                h = stream.get("height", "?")
                resolution = f"{w}x{h}"
                break

    # Summary file — this is what Becca reads
    summary_path = os.path.join(output_dir, "summary.txt")
    with open(summary_path, "w") as f:
        f.write("=" * 60 + "\n")
        f.write("VIDEO ANALYSIS — Ready for Becca to review\n")
        f.write("=" * 60 + "\n\n")

        f.write(f"Source: {source}\n")
        f.write(f"Duration: {duration}\n")
        f.write(f"Resolution: {resolution}\n")
        f.write(f"Frames extracted: {len(frames)} (every {interval}s)\n")
        f.write(f"Transcript segments: {len(segments)}\n\n")

        f.write("-" * 60 + "\n")
        f.write("FRAMES (view these images to see what's happening visually):\n")
        f.write("-" * 60 + "\n")
        for i, frame in enumerate(frames):
            ts = format_timestamp(i * interval)
            f.write(f"  [{ts}] {frame}\n")
        f.write("\n")

        f.write("-" * 60 + "\n")
        f.write("TRANSCRIPT:\n")
        f.write("-" * 60 + "\n")
        if segments:
            for seg in segments:
                ts = format_timestamp(seg["start"])
                f.write(f"  [{ts}] {seg['text']}\n")
        else:
            f.write("  (No speech detected or audio unavailable)\n")
        f.write("\n")

        f.write("-" * 60 + "\n")
        f.write("HOW TO REVIEW:\n")
        f.write("-" * 60 + "\n")
        f.write("1. Read this summary for metadata and transcript\n")
        f.write("2. Use the Read tool on individual frame images to see visuals\n")
        f.write("3. Combine transcript + visuals for full understanding\n")
        f.write("=" * 60 + "\n")

    print(f"\nDone! Output saved to: {output_dir}")
    print(f"  Summary:    {summary_path}")
    print(f"  Transcript: {transcript_path}")
    print(f"  Frames:     {os.path.join(output_dir, 'frames/')}")

def main():
    parser = argparse.ArgumentParser(description="Analyze a video for Becca")
    parser.add_argument("video", help="Local file path or URL")
    parser.add_argument("--interval", type=float, default=0,
                        help="Seconds between frame captures (0 = auto)")
    parser.add_argument("--output-dir", default="",
                        help="Output directory (default: outputs/video-analysis/)")
    args = parser.parse_args()

    source = args.video
    workspace = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Set up output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        # Name it based on the video source
        if is_url(source):
            name = re.sub(r'[^\w\-]', '_', source.split("/")[-1].split("?")[0])[:50]
        else:
            name = Path(source).stem[:50]
        output_dir = os.path.join(workspace, "outputs", "video-analysis", name)

    os.makedirs(output_dir, exist_ok=True)

    # Step 1: Get the video file
    if is_url(source):
        video_path = download_video(source, output_dir)
    else:
        video_path = os.path.abspath(source)
        if not os.path.exists(video_path):
            print(f"Error: File not found: {video_path}")
            sys.exit(1)

    # Step 2: Get video info
    info = get_video_info(video_path)
    duration_s = float(info.get("format", {}).get("duration", 0)) if info else 0

    # Step 3: Auto-calculate frame interval if not specified
    interval = args.interval
    if interval <= 0:
        if duration_s <= 15:
            interval = 1        # short clips: every second
        elif duration_s <= 60:
            interval = 2        # under 1 min: every 2s
        elif duration_s <= 300:
            interval = 5        # under 5 min: every 5s
        elif duration_s <= 900:
            interval = 10       # under 15 min: every 10s
        else:
            interval = 15       # long videos: every 15s
        print(f"Auto frame interval: {interval}s (video is {format_timestamp(duration_s)})")

    # Step 4: Extract frames
    frames = extract_frames(video_path, output_dir, interval)

    # Step 5: Extract and transcribe audio
    audio_path = extract_audio(video_path, output_dir)
    segments = transcribe_audio(audio_path)

    # Step 6: Build structured output
    build_output(video_path, output_dir, frames, segments, info, source, interval)

    # Print the output dir for the calling command to pick up
    print(f"\nOUTPUT_DIR={output_dir}")

if __name__ == "__main__":
    main()
