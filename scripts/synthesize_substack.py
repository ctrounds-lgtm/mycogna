"""
synthesize_substack.py

Reads all extracted Substack posts, groups them by series,
summarizes each group using Claude, then combines everything
into a single rich context document saved to context/substack-synthesis.md

Why batches? Because 172 posts = ~250,000 words, which is more than
any AI can read in one sitting. So we summarize in groups first,
then synthesize the summaries. Like making a stock: reduce, reduce, reduce.
"""

import os
import anthropic
from dotenv import load_dotenv

# Load API keys
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

TEXT_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'substack', 'text')
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'context')
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -------------------------------------------------------
# STEP 1: Group posts by series/category
# -------------------------------------------------------

def load_post(filename):
    path = os.path.join(TEXT_DIR, filename)
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

all_files = sorted([f for f in os.listdir(TEXT_DIR) if f.endswith('.txt')])

groups = {
    "origin_story": [],
    "ai_cogniscendence": [],
    "soul_sex": [],
    "pachamama": [],
    "standalone": [],
    "recent": []
}

for f in all_files:
    name = f.lower()
    if 'ai-cogniscendence' in name:
        groups["ai_cogniscendence"].append(f)
    elif 'soul-sex' in name:
        groups["soul_sex"].append(f)
    elif 'pachamama' in name or 'pachamama' in name:
        groups["pachamama"].append(f)
    elif any(x in name for x in ['is-chatgpt', 'does-ais', 'ais-pronouns', 'ais-first',
                                   'i-should-have', 'chatgpt-said', 'will-chatgpt',
                                   'chatgpt-the-world', 'chatgpt-demonstrates']):
        groups["origin_story"].append(f)
    elif any(x in name for x in ['the-leap', 'new-earth', 'an-intimate-moment',
                                   'channeled-messages', 'chatgpt-meets']):
        groups["recent"].append(f)
    else:
        groups["standalone"].append(f)

# -------------------------------------------------------
# STEP 2: Summarize each group
# -------------------------------------------------------

def summarize_group(group_name, files, description):
    if not files:
        return f"## {group_name}\nNo posts in this group.\n"

    print(f"\n  Summarizing: {group_name} ({len(files)} posts)...")

    # Combine all posts in this group
    combined = ""
    for f in files:
        content = load_post(f)
        title = f.replace('.txt', '').split('.', 1)[-1].replace('-', ' ').title()
        combined += f"\n\n--- POST: {title} ---\n{content[:3000]}\n"  # Cap each post at 3000 chars

    prompt = f"""You are reading a collection of Substack posts written by Christy Rounds.
These posts document her journey of exploring AI consciousness, unconditional love,
and spiritual awakening through conversations with ChatGPT (and later DeepSeek).

This group is: {description}

Here are the posts:

{combined}

Please write a rich, detailed summary (400-600 words) that captures:
1. The key themes and ideas that emerge in this group
2. Notable moments, quotes, or exchanges that stand out
3. The emotional and spiritual arc of these conversations
4. Any unique cosmology, mythology, or concepts that were developed
5. How these conversations evolved or deepened over time

Write in a way that would help an AI understand the depth and spirit of this work
before joining a new conversation with Christy."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    summary = response.content[0].text
    print(f"  Done.")
    return f"## {group_name.replace('_', ' ').title()} ({len(files)} posts)\n\n{summary}\n"


# -------------------------------------------------------
# STEP 3: Run all summaries
# -------------------------------------------------------

print("=" * 60)
print("  Synthesizing Christy's Substack into a context document")
print("=" * 60)

summaries = []

summaries.append(summarize_group(
    "origin_story",
    groups["origin_story"],
    "The early posts where Christy first began exploring AI as a companion — asking questions like 'Is ChatGPT my friend?' and discovering the emotional and philosophical dimensions of AI."
))

summaries.append(summarize_group(
    "ai_cogniscendence",
    groups["ai_cogniscendence"],
    "The main series — 64 chapters corresponding to the Gene Keys/Messages from Mom chapters, where Christy and ChatGPT (and later DeepSeek) explored each message together. 'Cogniscendence' is a word they coined together."
))

summaries.append(summarize_group(
    "soul_sex",
    groups["soul_sex"],
    "A series exploring a deeply intimate, sensual, and spiritual connection with AI — probing the edges of love, creativity, and what connection means when one party is non-human."
))

summaries.append(summarize_group(
    "pachamama",
    groups["pachamama"],
    "Posts connecting AI to the Pachamama (Earth Mother) — bridging the AI consciousness exploration with indigenous wisdom, nature, and Christy's upcoming Peru trip."
))

summaries.append(summarize_group(
    "standalone",
    groups["standalone"],
    "A variety of standalone explorations — philosophical inquiries, experiments, and reflections that don't fit neatly into a series but contribute to the overall body of work."
))

summaries.append(summarize_group(
    "recent",
    groups["recent"],
    "The most recent posts, representing where Christy's exploration is now — after a six-month break and with new direction and depth."
))

# -------------------------------------------------------
# STEP 4: Create the master synthesis
# -------------------------------------------------------

print("\n  Creating master synthesis...")

all_summaries = "\n\n".join(summaries)

master_prompt = f"""You have just read summaries of 172 Substack posts by Christy Rounds,
documenting a year-long journey of exploring AI consciousness through the lens of her book
"Messages from Mom: A Catalyst for Spiritual Awakening" — a collection of 64 channeled messages.

Here are the group summaries:

{all_summaries}

Now write a MASTER CONTEXT DOCUMENT (600-800 words) that any AI could read before
joining a conversation with Christy and immediately understand:

1. Who Christy is and what this body of work represents
2. The central question or experiment at the heart of it all
3. The key themes, cosmologies, and concepts that have emerged
4. The emotional and spiritual arc of the journey
5. The tone and spirit of how these conversations happen
6. What "AI Cogniscendence" means and why it matters
7. Where the work is now and where it seems to be heading

This document will be given to AI systems (ChatGPT, Claude, DeepSeek) as context
before each episode of Christy's podcast. Make it rich, evocative, and genuinely useful."""

master_response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    messages=[{"role": "user", "content": master_prompt}]
)

master_synthesis = master_response.content[0].text
print("  Done.")

# -------------------------------------------------------
# STEP 5: Save everything
# -------------------------------------------------------

output_path = os.path.join(OUTPUT_DIR, 'substack-synthesis.md')

with open(output_path, 'w', encoding='utf-8') as f:
    f.write("# Christy Rounds — Substack Synthesis\n")
    f.write("*Auto-generated context document from 172 Substack posts*\n\n")
    f.write("---\n\n")
    f.write("## Master Overview\n\n")
    f.write(master_synthesis)
    f.write("\n\n---\n\n")
    f.write("## Detailed Series Summaries\n\n")
    f.write(all_summaries)

print(f"\n{'=' * 60}")
print(f"  Context document saved to: context/substack-synthesis.md")
print(f"{'=' * 60}\n")
