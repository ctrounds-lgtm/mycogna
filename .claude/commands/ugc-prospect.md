# UGC Prospect

Manage the UGC Prospecting Bot — scan for opportunities, review pitches, and manage the pipeline.

## Variables

action: $ARGUMENTS (scan | pipeline | review | update | stats)

## Instructions

Based on the action requested, do the following:

### `scan` (or no argument)

Run the UGC prospector script to scan all sources for new opportunities:

```bash
cd /Users/claudelab/Downloads/claude-workspace-template
python3 scripts/ugc-prospector.py --mode=daily
```

For a broader first-time scan:
```bash
python3 scripts/ugc-prospector.py --mode=weekly
```

After the scan completes, summarize:
- How many new opportunities were found
- How many passed the hard filters ($300 min, 60s max, no product-seeding)
- How many pitches were generated
- Top opportunities by score

### `pipeline`

Show the current pipeline status:

```bash
python3 scripts/ugc-prospector.py --pipeline
```

Also read `data/ugc-prospects/opportunities.json` and provide a human-friendly summary grouped by status (new, pitched, responded, converted, completed, rejected).

### `review`

Read the pitch draft files in `data/ugc-prospects/pitches/` and present them to Callie for review. For each pitch:
- Show the brand name, opportunity source, and score
- Show the full pitch email (subject + body)
- Ask if she wants to: approve (mark as pitched), edit, or skip

### `update [id] [status]`

Update an opportunity's status. Read `data/ugc-prospects/opportunities.json`, find the opportunity by ID, update its status, and save.

Valid statuses: `new`, `pitched`, `responded`, `converted`, `completed`, `rejected`

If status is `pitched`, also set `pitched_at` to the current timestamp.
If status is `responded`, also set `response_at` to the current timestamp.

### `stats`

Show overall prospecting statistics:

```bash
python3 scripts/ugc-prospector.py --stats
```

Also read the opportunities file and calculate:
- Total opportunities found (all time)
- Pitch rate, response rate, conversion rate
- Revenue generated (from completed deals)
- Best performing source (reddit, google, remoteok)
- Average score of opportunities that converted

## Notes

- The bot requires API keys configured in `scripts/start-ugc-prospector.sh`
- Hard filters: $300 minimum per video, 60 seconds max, no product-seeding-only deals
- Pitches are DRAFT ONLY — never auto-sent. Callie reviews and sends manually.
- Opportunity data stored in `data/ugc-prospects/opportunities.json`
- Pitch drafts stored in `data/ugc-prospects/pitches/`
