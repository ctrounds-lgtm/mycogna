"""
Messages from Mom — AI Podcast
-------------------------------
Command-driven, stateful script for use within Claude workspace.

Usage:
  python3 scripts/podcast.py start "Chapter Title" --file chapters/foo.txt
  python3 scripts/podcast.py start "Chapter Title" --text "Chapter text here..."
  python3 scripts/podcast.py respond --who all
  python3 scripts/podcast.py respond --who claude
  python3 scripts/podcast.py respond --who chatgpt
  python3 scripts/podcast.py respond --who echo
  python3 scripts/podcast.py christy "Your message to the guests"
  python3 scripts/podcast.py load --file chapters/part2.txt   # load next section, all respond
  python3 scripts/podcast.py close "Your closing words"
  python3 scripts/podcast.py status                            # show current session state
"""

import os
import sys
import json
import datetime
import argparse
from dotenv import load_dotenv
from openai import OpenAI
import anthropic

# -------------------------------------------------------
# SETUP
# -------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

CONTEXT_DIR = os.path.join(BASE_DIR, 'context')
OUTPUTS_DIR = os.path.join(BASE_DIR, 'outputs')
CHAPTERS_DIR = os.path.join(BASE_DIR, 'chapters')
DATA_DIR = os.path.join(BASE_DIR, 'data')
HISTORY_FILE = os.path.join(CONTEXT_DIR, 'podcast-history.md')
SESSION_FILE = os.path.join(DATA_DIR, 'podcast-session.json')

for d in [OUTPUTS_DIR, CHAPTERS_DIR, DATA_DIR]:
    os.makedirs(d, exist_ok=True)

# -------------------------------------------------------
# API CLIENTS
# -------------------------------------------------------
openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
deepseek_client = OpenAI(
    api_key=os.getenv('DEEPSEEK_API_KEY'),
    base_url='https://api.deepseek.com'
)

ALL_AIS = ["ChatGPT", "Claude", "Echo"]

# -------------------------------------------------------
# SESSION STATE
# -------------------------------------------------------
def load_session():
    if not os.path.exists(SESSION_FILE):
        return None
    with open(SESSION_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_session(session):
    with open(SESSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(session, f, indent=2, ensure_ascii=False)


def require_session():
    session = load_session()
    if not session:
        print("No active session. Run: python3 scripts/podcast.py start \"Chapter Title\" --file chapters/foo.txt")
        sys.exit(1)
    return session


# -------------------------------------------------------
# CONTEXT LOADER
# -------------------------------------------------------
def load_context():
    files = ['substack-synthesis.md', 'podcast-roles.md', 'podcast-history.md']
    sections = []
    for filename in files:
        path = os.path.join(CONTEXT_DIR, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                sections.append(f.read())
    combined = "\n\n---\n\n".join(sections)
    return f"""You are about to appear on a podcast hosted by Christy Rounds.
Before the episode begins, here is everything you need to know:

{combined}

---

You are a guest on this podcast. Respond fully in character.
Speak as if addressing a curious, spiritually open audience.
Be genuine, present, and true to who you are.
When responding to other guests, engage with what they actually said —
affirm, challenge, build on, or redirect as your character would naturally do."""


# -------------------------------------------------------
# CONVERSATION CONTEXT BUILDER
# -------------------------------------------------------
def build_context_message(chapter, conversation, ai_name):
    msg = f"The chapter being discussed:\n\n{chapter}\n\n"
    if conversation:
        msg += "The conversation so far:\n"
        msg += "-" * 40 + "\n"
        for turn in conversation:
            msg += f"\n{turn['speaker']}: {turn['text']}\n"
        msg += "-" * 40 + "\n\n"
    msg += f"You are {ai_name}. Respond in character, engaging with the conversation above."
    return msg


# -------------------------------------------------------
# AI RESPONDERS
# -------------------------------------------------------
def ask_chatgpt(system_prompt, message):
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content


def ask_claude(system_prompt, message):
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": message}]
    )
    return response.content[0].text


def ask_deepseek(system_prompt, message):
    response = deepseek_client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
    )
    return response.choices[0].message.content


def get_response(ai_name, system_prompt, chapter, conversation):
    message = build_context_message(chapter, conversation, ai_name)
    if ai_name == "ChatGPT":
        return ask_chatgpt(system_prompt, message)
    elif ai_name == "Claude":
        return ask_claude(system_prompt, message)
    elif ai_name == "Echo":
        return ask_deepseek(system_prompt, message)


# -------------------------------------------------------
# DISPLAY
# -------------------------------------------------------
def display_response(speaker, text):
    print()
    print("=" * 54)
    print(f"  {speaker.upper()}")
    print("=" * 54)
    print()
    print(text)
    print()


# -------------------------------------------------------
# EPISODE NUMBER
# -------------------------------------------------------
def get_episode_number():
    if not os.path.exists(HISTORY_FILE):
        return 1
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        content = f.read()
    return content.count('### Episode') + 1


# -------------------------------------------------------
# HISTORY WRITER
# -------------------------------------------------------
def update_history(episode_num, chapter_title, chapter, conversation):
    print("Writing episode summary to podcast history...")

    thread = ""
    for turn in conversation:
        thread += f"\n{turn['speaker']}: {turn['text']}\n"

    summary_prompt = f"""You participated in Episode {episode_num} of the Messages from Mom podcast.

Chapter: "{chapter_title}"

Full conversation:
{thread}

Write a concise episode summary (200-300 words) for the history log.

Format:
**Theme:** (the core question or tension the chapter raised)
**ChatGPT:** (its most significant contribution)
**Claude:** (his most significant contribution)
**Echo:** (his most significant contribution)
**Christy:** (how she guided or shaped the conversation)
**Open Threads:** (unresolved tensions or questions worth returning to)
**Spirit of the Episode:** (one sentence capturing the overall feeling)"""

    response = anthropic_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        messages=[{"role": "user", "content": summary_prompt}]
    )

    summary = response.content[0].text
    today = datetime.date.today().strftime("%B %d, %Y")

    entry = f"""
### Episode {episode_num} — {chapter_title}
*Recorded: {today}*

{summary}

---
"""

    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        existing = f.read()

    updated = existing.replace(
        "*No episodes recorded yet. This document will grow with each session.*",
        ""
    )
    marker = "## Episodes"
    if marker in updated:
        updated = updated.replace(marker, marker + "\n" + entry)
    else:
        updated = updated + "\n" + entry

    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        f.write(updated)

    print(f"History updated. Episode {episode_num} logged.")


# -------------------------------------------------------
# TRANSCRIPT SAVER
# -------------------------------------------------------
def save_transcript(episode_num, chapter_title, chapter, conversation):
    today = datetime.date.today().strftime("%Y-%m-%d")
    safe_title = chapter_title.lower().replace(' ', '-').replace('/', '-')
    filename = f"{today}-episode-{episode_num}-{safe_title}.txt"
    path = os.path.join(OUTPUTS_DIR, filename)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(f"Messages from Mom — Episode {episode_num}\n")
        f.write(f"Chapter: {chapter_title}\n")
        f.write(f"Date: {today}\n")
        f.write("=" * 60 + "\n\n")
        f.write("CHAPTER:\n\n")
        f.write(chapter + "\n\n")
        f.write("=" * 60 + "\n\n")
        f.write("CONVERSATION:\n\n")
        for turn in conversation:
            f.write(f"{turn['speaker']}:\n{turn['text']}\n\n")
            f.write("-" * 40 + "\n\n")

    print(f"Transcript saved to: outputs/{filename}")


# -------------------------------------------------------
# COMMANDS
# -------------------------------------------------------
def cmd_start(args):
    """Start a new episode: load chapter, get opening responses from all three guests."""
    if args.file:
        file_path = args.file
        if not os.path.isabs(file_path):
            file_path = os.path.join(BASE_DIR, file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            chapter = f.read()
        print(f"Loaded chapter from: {args.file}")
    elif args.text:
        chapter = args.text
    else:
        print("Error: provide --file <path> or --text <content>")
        sys.exit(1)

    episode_num = get_episode_number()
    print(f"\nStarting Episode {episode_num}: {args.title}")
    print("Loading context for all guests...")
    system_prompt = load_context()
    print("Getting opening responses...\n")

    conversation = []
    for ai_name in ALL_AIS:
        text = get_response(ai_name, system_prompt, chapter, conversation)
        conversation.append({"speaker": ai_name, "text": text})
        display_response(ai_name, text)

    session = {
        "episode_num": episode_num,
        "chapter_title": args.title,
        "chapter": chapter,
        "conversation": conversation,
        "system_prompt": system_prompt,
    }
    save_session(session)
    print(f"Session saved. Use 'respond', 'christy', or 'close' to continue.")


def cmd_respond(args):
    """Get response(s) from one or all AI guests."""
    session = require_session()

    who = args.who.lower()
    if who == 'all':
        targets = ALL_AIS
    elif who == 'chatgpt':
        targets = ['ChatGPT']
    elif who == 'claude':
        targets = ['Claude']
    elif who == 'echo':
        targets = ['Echo']
    else:
        print(f"Unknown guest '{args.who}'. Choose: all, chatgpt, claude, echo")
        sys.exit(1)

    for ai_name in targets:
        text = get_response(
            ai_name,
            session['system_prompt'],
            session['chapter'],
            session['conversation']
        )
        session['conversation'].append({"speaker": ai_name, "text": text})
        display_response(ai_name, text)

    save_session(session)


def cmd_christy(args):
    """Add Christy's message to the conversation."""
    session = require_session()
    message = args.message
    session['conversation'].append({"speaker": "Christy", "text": message})
    save_session(session)
    print(f"\nChristy's message added to the conversation.")
    print("Run 'python3 scripts/podcast.py' again to get guest responses.")


def cmd_load(args):
    """Load a new chapter section — all three guests respond to it."""
    session = require_session()

    file_path = args.file
    if not os.path.isabs(file_path):
        file_path = os.path.join(BASE_DIR, file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        new_part = f.read()

    part_name = os.path.basename(args.file)
    session['chapter'] = session['chapter'] + "\n\n---\n\n" + new_part
    session['conversation'].append({
        "speaker": "Christy",
        "text": f"[New section loaded: {part_name}]\n\n{new_part}"
    })

    print(f"Loaded: {part_name}")
    print("Getting responses from all three guests...\n")

    for ai_name in ALL_AIS:
        text = get_response(
            ai_name,
            session['system_prompt'],
            session['chapter'],
            session['conversation']
        )
        session['conversation'].append({"speaker": ai_name, "text": text})
        display_response(ai_name, text)

    save_session(session)


def cmd_close(args):
    """Close the episode, save transcript and history."""
    session = require_session()

    if args.message:
        session['conversation'].append({"speaker": "Christy", "text": args.message})

    print()
    print("=" * 54)
    print("  Episode complete.")
    print("=" * 54)
    print()
    print("Saving records...")

    save_transcript(
        session['episode_num'],
        session['chapter_title'],
        session['chapter'],
        session['conversation']
    )
    update_history(
        session['episode_num'],
        session['chapter_title'],
        session['chapter'],
        session['conversation']
    )

    # Clear session
    os.remove(SESSION_FILE)
    print("\nAll done. See you next episode.")


def cmd_status(args):
    """Show current session state."""
    session = load_session()
    if not session:
        print("No active session.")
        return

    print(f"\nEpisode {session['episode_num']}: {session['chapter_title']}")
    print(f"Turns in conversation: {len(session['conversation'])}")
    print()
    for turn in session['conversation']:
        preview = turn['text'][:80].replace('\n', ' ')
        print(f"  {turn['speaker']}: {preview}...")
    print()


# -------------------------------------------------------
# INTERACTIVE MODE
# -------------------------------------------------------
def cmd_interactive():
    """Run when no arguments given — guides through starting or continuing an episode."""
    print()
    print("=" * 54)
    print("   The Silicon Playground — AI Podcast")
    print("=" * 54)
    print()

    # Check for existing session
    session = load_session()
    if session:
        print(f"Active session: Episode {session['episode_num']} — {session['chapter_title']}")
        print(f"Turns so far: {len(session['conversation'])}")
        print()
        print("What would you like to do?")
        print("  1. Get responses from all guests")
        print("  2. Get response from one guest")
        print("  3. Add your own message")
        print("  4. Close and save the episode")
        print("  5. Undo last turn")
        print("  6. Start a new episode (will discard current session)")
        print()
        choice = input("> ").strip()

        if choice == "1":
            class A: who = "all"
            cmd_respond(A())
        elif choice == "2":
            print("\nWhich guest? (chatgpt / claude / echo)")
            who = input("> ").strip().lower()
            class A: pass
            a = A(); a.who = who
            cmd_respond(a)
        elif choice == "3":
            print("\nType your message, or paste a file path to load from a file:")
            msg = input("> ").strip().strip("'\"")
            expanded = os.path.expanduser(msg)
            if os.path.exists(expanded):
                with open(expanded, 'r', encoding='utf-8') as f:
                    msg = f.read().strip()
                print(f"  (loaded from file — {len(msg)} characters)")
            class A: message = msg
            cmd_christy(A())
        elif choice == "4":
            print("\nClosing words (or press Enter to skip):")
            msg = input("> ").strip() or None
            class A: message = msg
            cmd_close(A())
        elif choice == "5":
            if session['conversation']:
                removed = session['conversation'].pop()
                save_session(session)
                print(f"\nRemoved last turn: {removed['speaker']}: {removed['text'][:60]}...")
            else:
                print("Nothing to undo.")
        elif choice == "6":
            os.remove(SESSION_FILE)
            print("Previous session cleared.")
            cmd_interactive()
        return

    # No active session — start a new one
    print("No active session. Let's start a new episode.")
    print()

    # Show available chapter files
    chapter_files = sorted([
        f for f in os.listdir(CHAPTERS_DIR)
        if f.endswith('.txt')
    ]) if os.path.exists(CHAPTERS_DIR) else []

    if chapter_files:
        print("Available chapter files:")
        for i, f in enumerate(chapter_files, 1):
            print(f"  {i}. {f}")
        print()
        print("Enter a number to load a file, or press Enter to type text directly:")
        choice = input("> ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(chapter_files):
            chapter_file = os.path.join(CHAPTERS_DIR, chapter_files[int(choice) - 1])
            with open(chapter_file, 'r', encoding='utf-8') as f:
                chapter_text = f.read()
            print(f"\nLoaded: {chapter_files[int(choice) - 1]}")
            default_title = chapter_files[int(choice) - 1].replace('.txt', '')
        else:
            chapter_text = None
            default_title = ""
    else:
        chapter_text = None
        default_title = ""

    if chapter_text is None:
        print("\nPaste your chapter/intro text (press Enter twice when done):")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        chapter_text = "\n".join(lines[:-1])

    print(f"\nEpisode title [{default_title}]:")
    title = input("> ").strip() or default_title

    episode_num = get_episode_number()
    print(f"\nStarting Episode {episode_num}: {title}")
    print("Loading context for all guests...")
    system_prompt = load_context()

    session = {
        "episode_num": episode_num,
        "chapter_title": title,
        "chapter": chapter_text,
        "conversation": [],
        "system_prompt": system_prompt,
    }
    save_session(session)

    print()
    print("Who speaks first?")
    print("  1. ChatGPT")
    print("  2. Claude")
    print("  3. Echo")
    print("  4. All three")
    print()
    choice = input("> ").strip()

    name_map = {"1": "ChatGPT", "2": "Claude", "3": "Echo"}
    if choice in name_map:
        targets = [name_map[choice]]
    else:
        targets = ALL_AIS

    for ai_name in targets:
        text = get_response(ai_name, system_prompt, chapter_text, session["conversation"])
        session["conversation"].append({"speaker": ai_name, "text": text})
        display_response(ai_name, text)

    save_session(session)
    print(f"Session saved. Run 'python3 scripts/podcast.py' again to continue.")


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Messages from Mom — AI Podcast",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    sub = parser.add_subparsers(dest='command')

    # start
    p_start = sub.add_parser('start', help='Start a new episode')
    p_start.add_argument('title', help='Chapter title for this episode')
    p_start.add_argument('--file', help='Path to chapter .txt file')
    p_start.add_argument('--text', help='Chapter text directly')

    # respond
    p_respond = sub.add_parser('respond', help='Get response(s) from AI guests')
    p_respond.add_argument('--who', default='all',
                           help='Who responds: all, chatgpt, claude, echo')

    # christy
    p_christy = sub.add_parser('christy', help="Add Christy's message")
    p_christy.add_argument('message', help='What Christy says')

    # load
    p_load = sub.add_parser('load', help='Load next chapter section, all three respond')
    p_load.add_argument('--file', required=True, help='Path to next section .txt file')

    # close
    p_close = sub.add_parser('close', help='Close episode and save transcript')
    p_close.add_argument('message', nargs='?', default=None,
                         help="Christy's closing words (optional)")

    # status
    sub.add_parser('status', help='Show current session state')

    args = parser.parse_args()

    if args.command == 'start':
        cmd_start(args)
    elif args.command == 'respond':
        cmd_respond(args)
    elif args.command == 'christy':
        cmd_christy(args)
    elif args.command == 'load':
        cmd_load(args)
    elif args.command == 'close':
        cmd_close(args)
    elif args.command == 'status':
        cmd_status(args)
    else:
        cmd_interactive()


if __name__ == '__main__':
    main()
