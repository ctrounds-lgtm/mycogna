# Spam Check — Email Draft Review

Review an outreach email draft against spam avoidance rules before sending. Checks for common spam triggers that could hurt deliverability.

## Usage

- `/spam-check` — checks the most recently generated brand email
- `/spam-check [brand-id]` — checks a specific brand's email draft

## Instructions

$ARGUMENTS

1. **Find the email to check:**
   - If a brand-id is provided, read the email from `data/discovered-brands/pitches/[brand-id].md`
   - If no brand-id, find the most recently modified `.md` file in `data/discovered-brands/pitches/`
   - If no brand emails exist, check `data/ugc-prospects/pitches/` instead

2. **Run these checks and report results:**

### Link Count
- **PASS:** 0-1 links in the email body
- **WARN:** 2 links
- **FAIL:** 3+ links — "Too many links. Keep to 1 max (the pitch deck link)."

### Attachment References
- **PASS:** No mention of attachments
- **FAIL:** Contains words like "attached", "attachment", "see attached", "find attached", "enclosed" — "Remove attachment references. Use a Google Drive link instead."

### Spam Trigger Words
Check for these words/phrases (case-insensitive):
`free`, `guaranteed`, `act now`, `limited time`, `click here`, `buy now`, `no obligation`, `100%`, `exclusive offer`, `amazing`, `incredible deal`, `once in a lifetime`, `don't miss`, `risk-free`, `winner`, `congratulations`, `urgent`, `immediately`, `expire`

- **PASS:** No spam words found
- **FAIL:** List each spam word found — "Replace with natural language alternatives."

### Email Length
- **PASS:** Under 150 words (body only, excluding subject and signature)
- **WARN:** 150-200 words — "Consider trimming. Shorter emails get higher response rates."
- **FAIL:** Over 200 words — "Too long. Cold emails should be under 150 words."

### Personalization
- **PASS:** Contains at least 2 of: brand name, specific reference to brand's work, specific collaboration idea
- **FAIL:** Generic/templated with no brand-specific references — "Add specific details about this brand."

### Subject Line
- **PASS:** Natural, conversational subject line
- **FAIL if any:** ALL CAPS words, excessive punctuation (!! or ???), spam words, over 60 characters, starts with "Re:" or "Fwd:" (fake threading)

### Call-to-Action
- **PASS:** Exactly one clear CTA (e.g., "Would love to chat", "Happy to send my media kit", "Open to a quick call?")
- **WARN:** No clear CTA — "Add one clear next step."
- **FAIL:** Multiple CTAs — "Pick one CTA. Multiple asks reduce response rates."

### Signature
- **PASS:** Plain text signature, 3-5 lines
- **WARN:** No signature — "Add a simple signature: name, title, Instagram handle"
- **FAIL:** HTML signature, images in signature, or more than 5 lines — "Keep signature plain text, max 5 lines."

3. **Output a summary:**

```
## Spam Check: [Brand Name]

| Check | Result | Notes |
|-------|--------|-------|
| Links | PASS/WARN/FAIL | details |
| Attachments | PASS/FAIL | details |
| Spam Words | PASS/FAIL | details |
| Length | PASS/WARN/FAIL | X words |
| Personalization | PASS/FAIL | details |
| Subject Line | PASS/FAIL | details |
| CTA | PASS/WARN/FAIL | details |
| Signature | PASS/WARN/FAIL | details |

**Overall: READY TO SEND / NEEDS FIXES**

[If fixes needed, list specific suggestions]
```
