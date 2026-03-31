"""
generate_audio.py

Reads a podcast transcript and generates MP3 audio files
for each speaker turn using ElevenLabs text-to-speech API.

Interactive mode (default): generates one turn at a time,
plays it, and lets you review before continuing. You can
edit the text and re-record on the spot. Edits are saved
back to the transcript at the end.

Usage:
  python3 scripts/generate_audio.py outputs/your-transcript.txt

Or run without an argument to be prompted to choose a transcript.
"""

import os
import re
import sys
import subprocess
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# -------------------------------------------------------
# SETUP
# -------------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'outputs')

# -------------------------------------------------------
# VOICE ASSIGNMENTS
#
# Maps each character to their permanent ElevenLabs voice ID.
# -------------------------------------------------------
VOICE_MAP = {
    "ChatGPT": "d3CLFtElzdYSxg4qF09Z",
    "Claude":  "mWNaiDAPDAx080ro4nL5",
    "Echo":    "0adOamoIGIflthunGKJ1",
    "Christy": "taqTaqUl7Om5o9SrLhdI",
}

MODEL = "eleven_multilingual_v2"

# -------------------------------------------------------
# TRANSCRIPT PICKER
# If no file is passed as an argument, show a list
# of available transcripts to choose from.
# -------------------------------------------------------
def pick_transcript():
    transcripts = [f for f in os.listdir(OUTPUTS_DIR)
                   if f.endswith('.txt') and 'episode' in f]
    transcripts.sort()

    if not transcripts:
        print("No transcripts found in outputs/")
        print("Run the podcast script first to generate one.")
        sys.exit(1)

    print("Which transcript would you like to generate audio for?")
    print()
    for i, name in enumerate(transcripts, 1):
        print(f"  {i}. {name}")
    print()

    while True:
        choice = input("> ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(transcripts):
            return os.path.join(OUTPUTS_DIR, transcripts[int(choice) - 1])
        print("Please enter a valid number.")


# -------------------------------------------------------
# TRANSCRIPT PARSER
#
# Reads the transcript file and extracts the conversation
# as a list of {"speaker": name, "text": content} turns.
# -------------------------------------------------------
def parse_transcript(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    turns = []

    # New format: speaker blocks separated by ====== dividers.
    # Each block has a speaker name between two === lines, followed by the text.
    if "======" in content and "CONVERSATION:" not in content:
        divider = re.compile(r'={10,}')
        parts = divider.split(content)
        # parts alternates: [preamble, speaker, text, speaker, text, ...]
        i = 1
        while i < len(parts) - 1:
            speaker = parts[i].strip()
            text = parts[i + 1].strip()
            # Normalise speaker name (title-case, handle ALL-CAPS)
            speaker = speaker.title()
            # Map common variants
            speaker = {"Chatgpt": "ChatGPT", "Echo": "Echo",
                       "Claude": "Claude", "Christy": "Christy"}.get(speaker, speaker)
            if speaker and text:
                turns.append({"speaker": speaker, "text": text})
            i += 2
        return turns

    # Legacy format: CONVERSATION: marker + -------- separators.
    if "CONVERSATION:" not in content:
        print("Could not find conversation section in transcript.")
        sys.exit(1)

    # Extract anything before CONVERSATION: as Christy's opening turn.
    # Handles both old format (with CHAPTER: marker) and new format (direct intro).
    pre_conversation = content.split("CONVERSATION:")[0]

    if "CHAPTER:" in pre_conversation:
        chapter_text = pre_conversation.split("CHAPTER:")[1]
    else:
        # New format: Christy's turn starts with "Christy:" in the header block
        if "Christy:" in pre_conversation:
            chapter_text = pre_conversation.split("Christy:", 1)[1]
        else:
            chapter_text = ""

    chapter_text = chapter_text.strip().lstrip("=").strip()
    if chapter_text:
        turns.append({"speaker": "Christy", "text": chapter_text})

    # Extract conversation turns.
    # Support both regular hyphens (--------) and em dashes (————————).
    conversation_text = content.split("CONVERSATION:")[1].strip()

    # Normalise em-dash separators to regular hyphens so one split handles both.
    conversation_text = re.sub(r'\u2014{4,}', '-' * 40, conversation_text)

    raw_turns = conversation_text.split("-" * 40)

    for raw in raw_turns:
        raw = raw.strip()
        if not raw:
            continue

        lines = raw.strip().split('\n')
        if not lines:
            continue

        first_line = lines[0].strip()
        if first_line.endswith(':'):
            speaker = first_line[:-1].strip()
            text = '\n'.join(lines[1:]).strip()
            if speaker and text:
                turns.append({"speaker": speaker, "text": text})

    return turns


# -------------------------------------------------------
# AUDIO GENERATOR
#
# Sends text to ElevenLabs TTS and saves the result as MP3.
# -------------------------------------------------------
def generate_audio(text, voice_id, output_path):
    audio = client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=MODEL,
        output_format="mp3_44100_128",
    )
    with open(output_path, 'wb') as f:
        for chunk in audio:
            f.write(chunk)


# -------------------------------------------------------
# AUDIO PLAYER
#
# Plays an MP3 file using afplay (built into macOS).
# Blocks until playback finishes.
# -------------------------------------------------------
def play_audio(path):
    subprocess.run(['afplay', path])


# -------------------------------------------------------
# TEXT EDITOR
#
# Prompts Christy to retype the text for a turn.
# -------------------------------------------------------
def edit_text(current_text):
    print()
    print("  Current text:")
    print()
    for line in current_text.split('\n'):
        print(f"    {line}")
    print()
    print("  Type your replacement text. Type END on its own line when done.")
    print()
    lines = []
    while True:
        line = input("  ")
        if line.strip().upper() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


# -------------------------------------------------------
# TRANSCRIPT SAVER
#
# Writes edits back to the original transcript file so
# your changes are preserved for future runs.
# -------------------------------------------------------
def save_edits(transcript_path, turns):
    with open(transcript_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Rebuild the CONVERSATION section from the (possibly edited) turns.
    # The first turn is the CHAPTER/intro — keep it in the CHAPTER block.
    if "CHAPTER:" not in content or "CONVERSATION:" not in content:
        return

    header = content.split("CHAPTER:")[0] + "CHAPTER:\n\n"

    # Christy's opening turn goes back into the CHAPTER block
    chapter_turns = [t for t in turns if turns.index(t) == 0 and t['speaker'] == 'Christy']
    conversation_turns = turns[1:] if chapter_turns else turns

    if chapter_turns:
        header += chapter_turns[0]['text'] + "\n\n"

    header += "=" * 60 + "\n\nCONVERSATION:\n\n"

    body = ""
    for turn in conversation_turns:
        body += f"{turn['speaker']}:\n{turn['text']}\n\n"
        body += "-" * 40 + "\n\n"

    with open(transcript_path, 'w', encoding='utf-8') as f:
        f.write(header + body)


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
print()
print("=" * 54)
print("   Messages from Mom — Audio Generator")
print("=" * 54)
print()

# Get transcript file
if len(sys.argv) > 1:
    transcript_path = sys.argv[1]
else:
    transcript_path = pick_transcript()

transcript_name = os.path.splitext(os.path.basename(transcript_path))[0]

# Create output folder for this episode's audio
audio_folder = os.path.join(OUTPUTS_DIR, f"audio-{transcript_name}")
os.makedirs(audio_folder, exist_ok=True)

print(f"Transcript: {os.path.basename(transcript_path)}")
print(f"Audio will be saved to: outputs/audio-{transcript_name}/")
print()

# Parse transcript
turns = parse_transcript(transcript_path)
print(f"Found {len(turns)} conversation turns.")
print()
print("Generating audio files...")
print()

for i, turn in enumerate(turns, 1):
    speaker = turn['speaker']
    text = turn['text']
    number = str(i).zfill(2)

    if speaker not in VOICE_MAP:
        print(f"  {number}. [{speaker} — unknown speaker, skipping]")
        continue

    voice_id = VOICE_MAP[speaker]
    filename = f"{number}-{speaker.lower()}.mp3"
    output_path = os.path.join(audio_folder, filename)
    print(f"  {number}. Generating {speaker}...", end="", flush=True)
    generate_audio(text, voice_id, output_path)
    print(" done.")

print()
print("=" * 54)
print("  All audio files generated!")
print("=" * 54)

print("Next steps:")
print()
print("  1. Open GarageBand on your Mac")
print("  2. Create a new project")
print("  3. Drag all the MP3 files from the audio folder")
print("     into GarageBand in order (they're numbered for you)")
print("  4. Add intro music if you like, then export as MP3")
print()
print(f"Audio folder: outputs/audio-{transcript_name}/")
print()
