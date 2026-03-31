# Deck Feedback

> Save deck feedback into the learning system so future decks improve.

## Instructions

When the user provides feedback about a pitch deck, do the following:

1. **Understand the feedback** — What's wrong with the current approach? What should change?

2. **Update the learnings file** — Add the new lesson to `reference/deck-feedback-learnings.md` in the appropriate section. If it's a new category of feedback, create a new section.

3. **Update the generator prompt** — If the feedback requires a change to `scripts/pitch-deck-generator.py`, update the prompt instructions to prevent the same issue in future decks.

4. **Confirm** — Tell the user what you saved and how it will affect future decks.

## Usage

`/deck-feedback [feedback text]`

If no feedback text is provided, ask the user what they'd like to change about the decks.

## Key Files

- `reference/deck-feedback-learnings.md` — Living document of all deck feedback and rules
- `scripts/pitch-deck-generator.py` — The generator prompt (function `generate_brand_deck_content`)
- `scripts/brand-pitch-template.html` — The HTML template
- `reference/campaign-portfolio.md` — Campaign details for credential references
