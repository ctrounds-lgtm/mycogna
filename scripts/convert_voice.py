"""
convert_voice.py

Episode builder for the AI podcast. Record one line at a time,
choose who speaks each turn, and build up a full episode locally
using Seed-VC voice conversion (free, runs on Apple Silicon).

Usage:
    python3 scripts/convert_voice.py

Output:
    outputs/episodes/episode-XX/
        01-echo.wav
        02-christy.wav
        03-claude.wav
        ...
        episode.txt   (running transcript / line list)

Prerequisites:
    - Reference clips in voices/ (run generate_reference_voices.py first)
    - pip install sounddevice soundfile torch torchaudio
"""

import os
import sys
import signal
import subprocess
import tempfile
import shutil
import time
import json
from datetime import datetime

# -------------------------------------------------------
# GRACEFUL INTERRUPT
# -------------------------------------------------------
_cleanup_paths = []

def _cleanup_and_exit(signum=None, frame=None):
    print("\n\nInterrupted. Cleaning up temp files...")
    for path in _cleanup_paths:
        if path and os.path.exists(path):
            os.unlink(path)
    print()
    sys.exit(0)

signal.signal(signal.SIGINT, _cleanup_and_exit)


# -------------------------------------------------------
# PATHS
# -------------------------------------------------------
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
WORKSPACE   = os.path.join(SCRIPT_DIR, '..')
VOICES_DIR  = os.path.join(WORKSPACE, 'voices')
EPISODES_DIR = os.path.join(WORKSPACE, 'outputs', 'episodes')
SEED_VC_DIR = os.path.join(WORKSPACE, 'vendor', 'seed-vc')

CHARACTERS = ["Christy", "ChatGPT", "Claude", "Echo"]


# -------------------------------------------------------
# SEED-VC SETUP
# -------------------------------------------------------
def ensure_seed_vc():
    if os.path.exists(os.path.join(SEED_VC_DIR, 'inference.py')):
        return

    print("Seed-VC not found. Setting up now (one-time, ~2–3 minutes)...")
    import zipfile

    vendor_dir = os.path.dirname(SEED_VC_DIR)
    os.makedirs(vendor_dir, exist_ok=True)

    zip_url = "https://github.com/Plachtaa/seed-vc/archive/refs/heads/main.zip"
    zip_path = os.path.join(vendor_dir, "seed-vc.zip")

    print("  Downloading Seed-VC repository...")
    subprocess.run(['curl', '-L', '-o', zip_path, zip_url], check=True)

    print("  Extracting...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(vendor_dir)
    os.unlink(zip_path)

    extracted = os.path.join(vendor_dir, "seed-vc-main")
    if os.path.exists(extracted):
        os.rename(extracted, SEED_VC_DIR)

    req_mac = os.path.join(SEED_VC_DIR, 'requirements-mac.txt')
    req_std = os.path.join(SEED_VC_DIR, 'requirements.txt')
    req_file = req_mac if os.path.exists(req_mac) else req_std

    print(f"  Installing dependencies...")
    subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', req_file], check=True)
    print("  Seed-VC ready.\n")


# -------------------------------------------------------
# EPISODE MANAGEMENT
# -------------------------------------------------------
def pick_episode():
    """Ask for episode number, return (episode_dir, episode_name, existing_lines)."""
    print("Episode number (e.g. 5):")
    ep_num = input("> ").strip()
    episode_name = f"episode-{ep_num.zfill(2)}"
    episode_dir = os.path.join(EPISODES_DIR, episode_name)
    os.makedirs(episode_dir, exist_ok=True)

    # Load existing lines if resuming
    transcript_path = os.path.join(episode_dir, 'episode.txt')
    existing_lines = []
    if os.path.exists(transcript_path):
        with open(transcript_path, 'r') as f:
            existing_lines = [l.strip() for l in f.readlines() if l.strip()]
        if existing_lines:
            print(f"\nResuming {episode_name} — {len(existing_lines)} line(s) already recorded:")
            for line in existing_lines:
                print(f"  {line}")

    return episode_dir, episode_name, existing_lines, transcript_path


def next_line_number(episode_dir):
    """Return the next sequential line number based on existing wav files."""
    existing = [
        f for f in os.listdir(episode_dir)
        if f.endswith('.wav') and f[:2].isdigit()
    ]
    return len(existing) + 1


def save_transcript_line(transcript_path, line_num, character, filename):
    with open(transcript_path, 'a') as f:
        f.write(f"{line_num:02d}  {character:<10}  {filename}\n")


# -------------------------------------------------------
# CHARACTER PICKER
# -------------------------------------------------------
def pick_character():
    print("\nWho speaks next?\n")
    for i, name in enumerate(CHARACTERS, 1):
        ref = os.path.join(VOICES_DIR, f"{name.lower()}.wav")
        status = "ready" if os.path.exists(ref) else "missing reference"
        print(f"  {i}. {name:<10} ({status})")
    print("  D. Done — finish episode")
    print("  U. Undo last line")
    print("  P. Play all lines so far")
    print()

    while True:
        choice = input("> ").strip().lower()
        if choice.isdigit() and 1 <= int(choice) <= len(CHARACTERS):
            return CHARACTERS[int(choice) - 1]
        if choice == 'd':
            return 'DONE'
        if choice == 'u':
            return 'UNDO'
        if choice == 'p':
            return 'PLAY'
        print("Enter 1–4, D, U, or P.")


# -------------------------------------------------------
# RECORDING
# -------------------------------------------------------
def record_from_mic():
    try:
        import sounddevice as sd
        import soundfile as sf
        import numpy as np
    except ImportError:
        print("\nsounddevice / soundfile required. Run: pip install sounddevice soundfile")
        sys.exit(1)

    SAMPLE_RATE = 22050

    print("\n  Get ready to speak...")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    print("\n  Recording now. Press Enter when you're done.\n")

    frames = []
    active = [True]

    def callback(indata, frame_count, time_info, status):
        if active[0]:
            frames.append(indata.copy())

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='float32', callback=callback)
    stream.start()
    input()
    active[0] = False
    stream.stop()
    stream.close()

    if not frames:
        print("No audio captured.")
        sys.exit(1)

    audio = np.concatenate(frames, axis=0)
    duration = len(audio) / SAMPLE_RATE
    print(f"  Captured {duration:.1f}s of audio.")

    peak = abs(audio).max()
    if peak > 0:
        audio = audio / peak * 0.7079

    tmp = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
    sf.write(tmp.name, audio, SAMPLE_RATE, subtype='PCM_16')
    _cleanup_paths.append(tmp.name)
    return tmp.name


def get_input_audio():
    print("\nInput:\n  1. Record from microphone\n  2. Load an existing file\n")
    while True:
        choice = input("> ").strip()
        if choice == "1":
            return record_from_mic(), True
        elif choice == "2":
            print("\n  Path to audio file:")
            path = input("  > ").strip().strip('"').strip("'")
            path = os.path.expanduser(path)
            if os.path.exists(path):
                return path, False
            print(f"  File not found: {path}")
        else:
            print("  Enter 1 or 2.")


# -------------------------------------------------------
# VOICE CONVERSION
# -------------------------------------------------------
def convert(source_path, reference_path, output_path):
    inference_script = os.path.join(SEED_VC_DIR, 'inference.py')

    with tempfile.TemporaryDirectory() as tmp_out:
        cmd = [
            sys.executable, inference_script,
            '--source',             source_path,
            '--target',             reference_path,
            '--output',             tmp_out,
            '--diffusion-steps',    '25',
            '--length-adjust',      '1.0',
            '--inference-cfg-rate', '0.7',
            '--f0-condition',       'False',
            '--auto-f0-adjust',     'False',
            '--semi-tone-shift',    '0',
            '--fp16',               'False',
        ]

        print("\n  Converting... (first run downloads ~1.2 GB of model weights)\n")

        result = subprocess.run(cmd, cwd=SEED_VC_DIR)

        if result.returncode != 0:
            print("\nConversion failed.")
            sys.exit(1)

        output_files = [
            os.path.join(tmp_out, f)
            for f in os.listdir(tmp_out)
            if f.lower().endswith(('.wav', '.mp3'))
        ]

        if not output_files:
            print("Conversion finished but no output file found.")
            sys.exit(1)

        shutil.move(output_files[0], output_path)


# -------------------------------------------------------
# EPISODE ACTIONS
# -------------------------------------------------------
def play_all(episode_dir):
    files = sorted([
        os.path.join(episode_dir, f)
        for f in os.listdir(episode_dir)
        if f.endswith('.wav') and f[:2].isdigit()
    ])
    if not files:
        print("  No lines recorded yet.")
        return
    print(f"\n  Playing {len(files)} line(s)...\n")
    for path in files:
        print(f"  ▶  {os.path.basename(path)}")
        subprocess.run(['afplay', path])
    print()


def undo_last(episode_dir, transcript_path, existing_lines):
    files = sorted([
        f for f in os.listdir(episode_dir)
        if f.endswith('.wav') and f[:2].isdigit()
    ])
    if not files:
        print("  Nothing to undo.")
        return existing_lines

    last_file = os.path.join(episode_dir, files[-1])
    print(f"\n  Removing: {files[-1]}")
    os.unlink(last_file)

    # Trim last line from transcript
    if existing_lines:
        existing_lines = existing_lines[:-1]
        with open(transcript_path, 'w') as f:
            for line in existing_lines:
                f.write(line + '\n')
        print("  Transcript updated.")

    return existing_lines


# -------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------
print()
print("=" * 54)
print("   AI Podcast  —  Episode Builder")
print("=" * 54)
print()

ensure_seed_vc()
os.makedirs(EPISODES_DIR, exist_ok=True)

episode_dir, episode_name, existing_lines, transcript_path = pick_episode()

print(f"\n{'─' * 54}")
print(f"  Building: {episode_name}")
print(f"  Output:   outputs/episodes/{episode_name}/")
print(f"{'─' * 54}")

while True:
    line_num = next_line_number(episode_dir)
    print(f"\n  [Line {line_num:02d}]")

    character = pick_character()

    if character == 'DONE':
        break

    if character == 'PLAY':
        play_all(episode_dir)
        continue

    if character == 'UNDO':
        existing_lines = undo_last(episode_dir, transcript_path, existing_lines)
        continue

    # Check reference clip exists
    reference_path = os.path.join(VOICES_DIR, f"{character.lower()}.wav")
    if not os.path.exists(reference_path):
        print(f"\n  No reference clip for {character}.")
        print("  Run: python3 scripts/generate_reference_voices.py")
        continue

    print(f"\n  Speaker: {character}")

    while True:
        source_path, is_temp = get_input_audio()

        output_filename = f"{line_num:02d}-{character.lower()}.wav"
        output_path = os.path.join(episode_dir, output_filename)
        _cleanup_paths.append(output_path)

        convert(source_path, reference_path, output_path)

        if is_temp:
            try:
                os.unlink(source_path)
                _cleanup_paths.remove(source_path)
            except Exception:
                pass

        # Play it back
        print(f"\n  ▶  Playing: {output_filename}")
        subprocess.run(['afplay', output_path])

        # Keep or redo
        print()
        answer = input("  Keep this take? (y = keep / n = redo / s = skip) > ").strip().lower()
        if answer == 'y':
            _cleanup_paths.remove(output_path)
            save_transcript_line(transcript_path, line_num, character, output_filename)
            existing_lines.append(f"{line_num:02d}  {character:<10}  {output_filename}")
            print(f"  Saved: {output_filename}")
            break
        elif answer == 's':
            os.unlink(output_path)
            _cleanup_paths.remove(output_path)
            print("  Skipped.")
            break
        else:
            os.unlink(output_path)
            _cleanup_paths.remove(output_path)
            print("\n  Re-recording...")

# -------------------------------------------------------
# WRAP UP
# -------------------------------------------------------
final_files = sorted([
    f for f in os.listdir(episode_dir)
    if f.endswith('.wav') and f[:2].isdigit()
])

print()
print("=" * 54)
print(f"  {episode_name}  —  {len(final_files)} line(s) recorded")
print("=" * 54)
for f in final_files:
    print(f"  {f}")
print(f"\n  Transcript: outputs/episodes/{episode_name}/episode.txt")
print()

if final_files:
    answer = input("Play the full episode now? (y/n) > ").strip().lower()
    if answer == 'y':
        play_all(episode_dir)
