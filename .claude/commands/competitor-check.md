# Competitor Check

> Flex Pass Watchdog — fetch current competitor data, compare against the last snapshot, and report changes.

---

## Step 1: Load Previous Snapshot

Read the most recent snapshot to understand what we already know:

- Read `data/competitor-snapshots/latest.json`
- Note the date of the last check
- Understand the current known state (pricing, studios, followers, positioning)

---

## Step 2: Fetch Current Flex Pass Data

Gather fresh data from all available public sources. Use WebFetch and WebSearch.

### Website

- WebFetch `https://www.flexpass.co.za` — extract:
  - Current pricing tiers (names, credit amounts, prices in ZAR)
  - List of partner studios
  - Tagline and key messaging
  - Any new features, pages, or offerings
  - B2B pitch / studio signup info

### Social & News

- WebSearch for `Flex Pass Cape Town flexpass.co.za` — look for:
  - Recent news, press coverage, or partnerships
  - Any new social media activity or campaigns
  - App store updates or reviews

- WebSearch for `flexpassza Instagram` — look for:
  - Current follower count
  - Recent post themes or content shifts
  - Any notable campaigns or announcements

### Important Rules for Fetching

- If a data point cannot be fetched, **carry forward the value from the previous snapshot** rather than leaving it blank
- Note which values are fresh vs carried forward in the source field
- Don't guess or fabricate numbers — only report what you can verify

---

## Step 3: Build New Snapshot

Construct a JSON object following this exact schema with all current data:

```json
{
  "date": "YYYY-MM-DD",
  "source": "competitor-check command — describe what was fetchable",
  "instagram": {
    "handle": "@flexpassza",
    "followers": <number>,
    "posts": <number>,
    "following": <number>,
    "bio": "<current bio text>",
    "highlights": ["<list of highlight names>"],
    "pinned_posts_summary": "<brief description of pinned content>"
  },
  "pricing": {
    "model": "<pricing model type>",
    "tiers": [
      {"name": "<tier name>", "credits": <number>, "price_zar": <number>}
    ]
  },
  "studios": {
    "count": "<number or estimate>",
    "known_names": ["<list of studio names>"]
  },
  "website": {
    "url": "flexpass.co.za",
    "tagline": "<current tagline>",
    "b2b_pitch": "<current B2B messaging>"
  },
  "positioning": {
    "branding": "<visual/brand description>",
    "key_claims": ["<list of positioning claims>"],
    "tiktok": "<tiktok handle>"
  },
  "contact": {
    "email": "<email>",
    "phone": "<phone>"
  }
}
```

---

## Step 4: Save and Diff

1. Save the new snapshot by running:

```bash
python3 scripts/competitor_snapshot.py save '<paste the JSON here>'
```

2. Then run the diff to see what changed:

```bash
python3 scripts/competitor_snapshot.py diff
```

---

## Step 5: Report

Present a clean summary to the user with:

1. **Header**: "Flex Pass Watchdog Report" with date range (last check → today)
2. **Changes**: List every change detected, grouped by category (pricing, studios, Instagram, website, positioning). For each change, briefly note the strategic implication if relevant.
3. **No Changes**: If nothing changed, say so — that's useful intel too (competitor is quiet).
4. **Carried Forward**: Note any data points that couldn't be refreshed and were carried from the previous snapshot.
5. **Strategic Takeaways**: 2-3 bullet points on what the changes (or lack thereof) might mean for Mova.

---

## Step 6: Update Context (If Significant)

If any of the following changed, update `context/current-data.md` with the new values:

- Pricing tiers or amounts
- Number of partner studios or new studio names
- Instagram follower count (update the comparison table)
- Major positioning or messaging shifts

Only update for meaningful changes — don't rewrite the file for minor shifts.
