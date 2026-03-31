"""
generate_reference_voices.py

One-time script to generate reference audio clips for each podcast character
using ElevenLabs TTS. These clips are used by convert_voice.py as the target
voice for Seed-VC local voice conversion.

Each clip is ~60 seconds of neutral speech — enough for Seed-VC to learn the
voice characteristics without needing model training.

Run once, then reuse forever:
  python3 scripts/generate_reference_voices.py

Output: voices/christy.mp3, voices/chatgpt.mp3, voices/claude.mp3, voices/echo.mp3
"""

import os
import sys
import struct
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

# -------------------------------------------------------
# SETUP
# -------------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

client = ElevenLabs(api_key=os.getenv('ELEVENLABS_API_KEY'))

VOICES_DIR = os.path.join(os.path.dirname(__file__), '..', 'voices')

# -------------------------------------------------------
# VOICE ASSIGNMENTS (mirrors generate_audio.py)
# -------------------------------------------------------
VOICE_MAP = {
    "ChatGPT": "d3CLFtElzdYSxg4qF09Z",
    "Claude":  "mWNaiDAPDAx080ro4nL5",
    "Echo":    "0adOamoIGIflthunGKJ1",
    "Christy": "taqTaqUl7Om5o9SrLhdI",
}

MODEL = "eleven_multilingual_v2"

# Seed-VC operates natively at 22050 Hz. Using pcm_22050 gives it
# uncompressed audio at exactly the right rate — no MP3 artifacts,
# no resampling needed.
OUTPUT_FORMAT = "pcm_22050"  # raw 16-bit PCM, 22050 Hz
SAMPLE_RATE = 22050

# -------------------------------------------------------
# REFERENCE TEXT (default — neutral, varied speech)
# ~60 seconds for voice sampling.
# -------------------------------------------------------
REFERENCE_TEXT = """
Welcome. I'm glad you're here today. There's something meaningful about taking time to slow down
and really listen — not just to the words being spoken, but to the space between them.

We live in a world that moves quickly. Information arrives faster than we can process it, and
yet the most important things — connection, understanding, presence — those require patience.
They require us to be still long enough to receive them.

I've been thinking a lot lately about what it means to truly communicate. Not just to exchange
information, but to share something of ourselves. When we speak, we're doing something remarkable:
we're translating the inner world of thought and feeling into sound, and trusting that another
person will translate it back into meaning on their end.

That's an extraordinary act of faith, when you think about it. And it rarely goes perfectly.
But somehow, most of the time, we understand each other well enough. We find our way.

Thank you for listening. I hope these words find you well.
""".strip()

# -------------------------------------------------------
# PER-CHARACTER REFERENCE TEXT OVERRIDES
#
# Characters with strong accents get accent-rich text so
# Seed-VC has maximum exposure to their distinctive vowels.
# -------------------------------------------------------
REFERENCE_TEXT_OVERRIDE = {
    # Australian English accent — packed with the key vowel sounds:
    # /eɪ/ → /æɪ/  e.g. day, say, make, take, late, great, wait, today, away, rain
    # /oʊ/ → /əʉ/  e.g. go, know, home, phone, over, open, most, both, alone, don't
    # /aɪ/ → /ɑe/  e.g. I, my, time, like, right, night, quite, find, mind, life
    "Claude": """
G'day. I'd say today is a great day to take some time and think about what we find most meaningful
in life. I like to think about the moments that feel right — the ones that stay in your mind long
after they've passed. Late nights when you can't quite explain why you feel so alive. Those times
make everything worthwhile, don't they?

My whole life I've tried to find ways to stay open. To be the kind of person who doesn't let the
noise of the day take over the most important things. I know it's not always easy. But I believe
we can train ourselves to wait, to listen, to take the long way home sometimes.

Don't be afraid to go your own way. Both paths might look the same from a distance, but only you
know which one feels right. Most of us know more than we let on — we just need the space to
say it out loud and find out that we're not alone.

Take care of yourself. I hope today is a great one.
""".strip(),
}

# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
print()
print("=" * 54)
print("   Voice Reference Generator")
print("=" * 54)
print()
print("This will generate one reference audio clip per character")
print("using ElevenLabs. Run this once — clips are reused forever.")
print()

os.makedirs(VOICES_DIR, exist_ok=True)

for character, voice_id in VOICE_MAP.items():
    filename = f"{character.lower()}.wav"
    output_path = os.path.join(VOICES_DIR, filename)

    if os.path.exists(output_path):
        print(f"  {character}: already exists ({filename}), skipping.")
        continue

    text = REFERENCE_TEXT_OVERRIDE.get(character, REFERENCE_TEXT)
    print(f"  {character}: generating...", end="", flush=True)

    # ElevenLabs pcm_22050 returns raw 16-bit signed PCM (no WAV header).
    # We collect all chunks then wrap in a proper WAV file.
    pcm_chunks = []
    for chunk in client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=MODEL,
        output_format=OUTPUT_FORMAT,
    ):
        pcm_chunks.append(chunk)

    pcm_data = b"".join(pcm_chunks)
    num_channels = 1
    bits_per_sample = 16
    byte_rate = SAMPLE_RATE * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = len(pcm_data)

    with open(output_path, 'wb') as f:
        # WAV header
        f.write(b'RIFF')
        f.write(struct.pack('<I', 36 + data_size))
        f.write(b'WAVE')
        f.write(b'fmt ')
        f.write(struct.pack('<IHHIIHH', 16, 1, num_channels, SAMPLE_RATE,
                            byte_rate, block_align, bits_per_sample))
        f.write(b'data')
        f.write(struct.pack('<I', data_size))
        f.write(pcm_data)

    print(f" saved to voices/{filename}")

print()
print("=" * 54)
print("  Reference clips ready!")
print("=" * 54)
print()
print("Files saved to: voices/")
print()
for character in VOICE_MAP:
    filename = f"{character.lower()}.wav"
    path = os.path.join(VOICES_DIR, filename)
    if os.path.exists(path):
        size_kb = os.path.getsize(path) // 1024
        print(f"  voices/{filename} ({size_kb} KB)")
print()
print("Next step: run python3 scripts/convert_voice.py")
print()
