# Plan: Audience Landing Pages — /individual, /family, /legacy

**Created:** 2026-05-12
**Status:** Implemented
**Request:** Create three audience-specific landing pages and clean up index.html to match the new site structure.

---

## Overview

### What This Plan Accomplishes

Three new HTML pages (`individual.html`, `family.html`, `legacy.html`) serve MyCogna's three distinct audiences, each with its own hero, relevant content sections, and pricing. Content currently on index.html that belongs to a specific audience is moved to the appropriate sub-page, leaving index.html as a clean top-of-funnel page: hero, "Share Stories," the three-audience section, and "Why I built MyCogna."

### Why This Matters

The current index.html conflates all three audiences on one page — a self-storyteller, a family caregiver, and an institutional organizer have very different needs and motivations. Dedicated pages let each visitor quickly recognize themselves and find a clear path to signup. The main page becomes a lighter, faster introduction that routes people to the right place.

---

## Current State

### Relevant Existing Structure

- `apps/cogna/static/index.html` — 1,320 lines; contains hero, use-case cards, three-audience section (just added), AI Companion explainer, portal/organizer section, JAMA science section, pricing table, founder story, footer
- `apps/cogna/static/portal-signup.html` — plan selection + signup form; contains B/C/D (individual) and E/F (institutional) pricing cards
- `apps/cogna/static/portal.html` / `portal.js` / `portal.css` — portal app; CSS variables and design tokens are the reference
- `apps/cogna/server.py` — serves all static pages via `FileResponse`; new routes needed for three new pages
- `apps/cogna/static/vercel.json` — cache headers only; no rewrites needed

### Gaps or Problems Being Addressed

- `/individual`, `/family`, `/legacy` return 404 — the three-audience cards on the main page already link to them
- All pricing, product detail, and audience-specific copy lives on one page, creating a cluttered experience
- The JAMA science section and the portal/organizer section are only relevant to families/caregivers, not all visitors
- SECTION 2's use-case cards (Memory Keeper, Institutional Legacy, etc.) are now redundant given the three-audience section

---

## Proposed Changes

### Summary of Changes

- Create `individual.html`: hero + product cards + self-service pricing ($0–$15) + AI Companion explainer
- Create `family.html`: hero + organizer section + science/JAMA section + AI Companion explainer + B/C/D portal pricing
- Create `legacy.html`: hero + new Legacy Collection description + E/F portal pricing
- Update `index.html`: remove moved sections (companion explainer, organizer section, JAMA section, pricing table, use-case cards), update nav
- Update `server.py`: add three new route handlers

### New Files to Create

| File Path | Purpose |
| --- | --- |
| `apps/cogna/static/individual.html` | Landing page for self-storytellers; product cards + pricing |
| `apps/cogna/static/family.html` | Landing page for families/caregivers; organizer section + B/C/D pricing |
| `apps/cogna/static/legacy.html` | Landing page for organizations; Legacy Collection description + E/F pricing |

### Files to Modify

| File Path | Changes |
| --- | --- |
| `apps/cogna/static/index.html` | Remove 5 sections, update nav links, simplify hero CTAs |
| `apps/cogna/server.py` | Add `/individual`, `/family`, `/legacy` route handlers |

### Files to Delete

None.

---

## Design Decisions

### Key Decisions Made

1. **AI Companion explainer duplicated on both individual.html and family.html** — it's relevant to both audiences (someone building a companion for themselves, and a caregiver setting up a companion for a loved one). Keeping it on the main page too would bloat index.html; duplicating is cleaner than a shared include.

2. **Pricing on sub-pages is informational, not interactive** — the actual plan selection and signup happen on portal-signup.html. Sub-pages show pricing cards with a "Get started →" CTA that links to `/portal/signup`. No JS selectPlan logic needed on sub-pages.

3. **individual.html uses the self-service pricing** ($0/$5/$10/$15 from index.html SECTION 5) — these link to `/storyteller` (free tier) or `/signup` (paid individual). This is distinct from the guardian portal pricing on family.html.

4. **family.html uses B/C/D guardian portal pricing** ($5/$10/$15 from portal-signup.html) — these represent portal accounts set up by families for their loved ones, linking to `/portal/signup`.

5. **Use-case cards in SECTION 2 removed from index.html** — Memory Keeper, Institutional Legacy, Journal That Talks Back, Digital Imprint are now made redundant by the three-audience section. SECTION 2 becomes a header + tagline only.

6. **Sub-page nav** links to all three audience pages plus home, giving visitors easy navigation between audiences.

7. **New Legacy Collection copy** is written in this plan (see Step 4) so `/implement` can build the section without ambiguity.

### Alternatives Considered

- **Keep all content on index.html with anchor links per audience** — rejected because it keeps the page cluttered and doesn't give each audience a distinct, shareable URL.
- **Shared CSS file for sub-pages** — rejected in favor of inline `<style>` blocks matching the existing pattern across index.html, portal-signup.html, etc. All MyCogna pages are self-contained HTML files.

### Open Questions

None — all content and structure decisions are specified below.

---

## Step-by-Step Tasks

### Step 1: Add server routes

Add three `FileResponse` routes to `server.py`, following the exact pattern of existing routes.

**Actions:**
- After the `/login` route (line ~311), add:
```python
@app.get("/individual")
def individual_page():
    return FileResponse(ROOT / "static" / "individual.html")


@app.get("/family")
def family_page():
    return FileResponse(ROOT / "static" / "family.html")


@app.get("/legacy")
def legacy_page():
    return FileResponse(ROOT / "static" / "legacy.html")
```

**Files affected:**
- `apps/cogna/server.py`

---

### Step 2: Create individual.html

A self-contained HTML page for individual storytellers. Design tokens, fonts, nav, and footer follow index.html exactly.

**Sections (in order):**
1. Nav
2. Hero
3. Product cards (moved from index.html SECTION 3)
4. Pricing ($0–$15, moved from index.html SECTION 5)
5. AI Companion explainer (moved from index.html SECTION 3C)
6. Footer

**Nav:**
```html
<nav>
  <a href="/" class="nav-logo">MyCogna</a>
  <ul class="nav-links" id="navLinks">
    <li><a href="/individual">For Individuals</a></li>
    <li><a href="/family">For Families</a></li>
    <li><a href="/legacy">For Organizations</a></li>
    <li><a href="/login" class="nav-btn-outline">Login</a></li>
    <li><a href="#pricing" class="nav-cta">Sign up</a></li>
  </ul>
  <button class="nav-hamburger" id="hamburger" aria-label="Menu"
          onclick="document.getElementById('navLinks').classList.toggle('open')">
    <span></span><span></span><span></span>
  </button>
</nav>
```

**Hero copy:**
```
Eyebrow: For Individuals
H1: Your story,
    in your own voice.
Subhead: Start with one memory. MyCogna does the rest.
Body: You've always known there was a book inside you. MyCogna gives you thoughtful prompts, voice recording, and an AI assistant that asks the follow-up questions a good interviewer would — so you capture not just what happened, but what it meant.
CTAs: [Start recording free → /storyteller]  [See plans → #pricing]
Invite link: Have an invite code? Enter it here. → /storyteller
```

**Product cards section:** Copy the entire `<section id="products">` block verbatim from index.html (which currently contains the old products-grid — but wait, that section was already replaced with the audiences section). 

**Important:** The product cards HTML (Storyteller / Memoir Builder / AI Companion) was removed from index.html when we replaced SECTION 3 with the audience section. The product card HTML and all associated CSS (`.products-grid`, `.product-card`, `.product-badge`, `.product-tagline`, `.product-desc`, `.product-features`, `.product-link`) still exist in index.html and should be copied into individual.html before being removed from index.html in Step 5.

**Product cards section label/header:**
```
Section label: Products
H2: Three tools for
    telling your story
Subhead: Start free. Upgrade when you're ready.
```

**Pricing section:** Copy the entire `<section id="pricing">` block from index.html verbatim, including all four pricing cards ($0/$5/$10/$15). Remove the "Setting this up for a family member?" note at the bottom (or replace with a link to /family).

**AI Companion explainer section:** Copy the entire `<section id="companion-explainer">` block from index.html verbatim.

**Footer:** Same footer as index.html. Update Product nav to include `/individual`, `/family`, `/legacy`.

**CSS to include:** Copy all CSS from index.html that's needed: `:root` variables, `body`, `nav` styles, section styles, product card styles, pricing card styles, companion explainer styles, footer styles, responsive rules. (All sections that are included on this page.)

**Files affected:**
- `apps/cogna/static/individual.html` (create)

---

### Step 3: Create family.html

A self-contained HTML page for families and caregivers.

**Sections (in order):**
1. Nav (same pattern as individual.html)
2. Hero
3. "Setting up stories for someone else?" section (moved from index.html SECTION 3B)
4. "Story-telling isn't just meaningful. It's medicine." section (moved from index.html SECTION 4)
5. AI Companion explainer (duplicated from index.html SECTION 3C)
6. Pricing: B/C/D guardian portal tiers
7. Footer

**Nav:** Same as individual.html, with `/family` as the active link.

**Hero copy:**
```
Eyebrow: For Families & Caregivers
H1: Help someone you love
    tell their story.
Subhead: You design the questions. They just press record.
Body: Your parent has dementia and you want to capture their memories before they fade. Your grandparent has stories no one has ever thought to ask about. MyCogna's portal lets you become the organizer — creating questions, sharing a simple code, and preserving everything from your dashboard.
CTAs: [Set up a portal → /portal/signup]  [Learn how it works → #how-it-works]
```

**"Setting up stories for someone else?" section:** Copy `<section id="portal">` from index.html verbatim. Add `id="how-it-works"` to this section so the hero CTA anchor works.

**"It's medicine" section:** Copy `<section id="research">` from index.html verbatim.

**AI Companion explainer section:** Copy `<section id="companion-explainer">` from index.html verbatim.

**Pricing section — B/C/D tiers:**
```
Section label: For Families & Caregivers
H2: Simple, honest
    pricing
Subhead: One account. Full control. Cancel any time.
```

Show three pricing cards sourced from portal-signup.html (B/C/D), displayed statically:

```
Card 1 — Storyteller Unlimited ($5/mo)
  Tier label: Storyteller
  Name: Unlimited
  Price: $5/mo
  Features:
    - Unlimited story recordings
    - All story prompts
    - Voice recording & transcription
    - Shareable story archive
  CTA: Get started → /portal/signup

Card 2 — Storyteller + Memoir Builder ($10/mo) [featured]
  Tier label: AI Assisted
  Name: Storyteller + Memoir Builder
  Price: $10/mo
  Features:
    - Everything in Unlimited
    - AI follow-up questions
    - Intelligent story editing
    - Extended story sessions
  CTA: Get started → /portal/signup

Card 3 — AI Companion ($15/mo)
  Tier label: Full Access
  Name: AI Companion
  Price: $15/mo
  Features:
    - Everything in Storyteller + Memoir Builder
    - Unlimited Cogna companions
    - Custom voice per Cogna
    - Multi-voice conversations
    - Session transcripts saved
  CTA: Get started → /portal/signup
```

Use the same pricing card CSS from index.html (`.pricing-card`, `.pricing-tier`, `.pricing-name`, `.pricing-price`, `.pricing-period`, `.pricing-features`, `.pricing-btn`). Three-column grid.

**Footer:** Same as individual.html.

**Files affected:**
- `apps/cogna/static/family.html` (create)

---

### Step 4: Create legacy.html

A self-contained HTML page for organizations.

**Sections (in order):**
1. Nav (same pattern, `/legacy` as active)
2. Hero
3. Legacy Collection description (new copy — written below)
4. Pricing: E/F tiers
5. Footer

**Nav:** Same as individual.html, with `/legacy` as the active link.

**Hero copy:**
```
Eyebrow: For Organizations
H1: Preserve the voices
    that built something.
Subhead: One archive. Many storytellers. Stories that last.
Body: A nonprofit marking a milestone. A historical society collecting oral histories. A hospice offering guided reminiscence. A faith community preserving testimonies. MyCogna's Legacy Collection gives every storyteller their own recording space — and gives you the tools to shape it all into something lasting.
CTAs: [Start your collection → /portal/signup]  [See how it works → #how-it-works]
```

**Legacy Collection description section (new copy):**
```
Section label: How It Works
H2: One archive,
    many voices.
id="how-it-works"
```

Two-column layout. Left column: explanatory copy. Right column: three feature callouts.

Left column copy:
> MyCogna's Legacy Collection is built for organizations that need to gather stories from multiple contributors — not a single memoir, but a living archive that grows over time.
>
> You set up the project: write the questions, generate storyteller codes, and invite participants. Each storyteller receives a private link, records their responses at their own pace, and signs in without needing your help. Everything accumulates in your portal dashboard — ready to download, organize, or publish.

Right column callouts:
1. **Your questions, their voices** — Write the prompts that matter for your project. Each storyteller sees only your curated questions, not generic life-story prompts.
2. **Stories that accumulate over time** — Codes remain active permanently. Storytellers can return and add more whenever they're ready.
3. **A dashboard built for organizers** — View recordings by storyteller, download transcripts, and manage your entire collection from one place.

**Book Builder upgrade callout (below the two columns):**
A muted card (use `.onboarding-card` style from portal.css, or replicate it inline):
```
Eyebrow: Upgrade available
H3: Add the Book Builder
Body: The Book Builder upgrade adds two things: an AI 'Go Deeper' tool that prompts 
storytellers to explore their stories in more depth, and a book assembly tool that compiles 
all responses into a structured Legacy Archive — complete with thematic overview, 
chapter groupings, and an editing workspace.
```

**Pricing section — E/F tiers:**
```
Section label: Pricing
H2: Built for
    organizations
Subhead: Start with Legacy Collection. Upgrade to Book Builder when you're ready.
```

Two pricing cards (use same pricing card CSS, two-column centered grid):

```
Card 1 — Legacy Collection ($25/mo)
  Tier label: Story Collection
  Name: Legacy Collection
  Price: $25/mo
  Features:
    - 5 new storyteller codes per month
    - All codes remain active permanently
    - Stories accumulate over time
    - Curated question sets per project
    - Portal dashboard & transcripts
  CTA: Start your collection → /portal/signup

Card 2 — Legacy Collection + Book Builder ($50/mo) [featured]
  Tier label: AI-Assisted Book Builder
  Name: Legacy Collection + Book Builder
  Price: $50/mo
  Features:
    - Everything in Legacy Collection
    - AI deepening sessions for storytellers
    - Portal book assembly & editing
    - Structured Legacy Archive output
    - Ideal for oral history projects
  CTA: Start your collection → /portal/signup
```

**Footer:** Same as individual.html.

**Files affected:**
- `apps/cogna/static/legacy.html` (create)

---

### Step 5: Clean up index.html

Remove all sections that have moved to sub-pages. Update nav and hero.

**Sections to remove entirely:**
- `<section id="companion-explainer">` (SECTION 3C) — moved to individual.html and family.html
- `<section id="portal">` (SECTION 3B) — moved to family.html
- `<section id="research">` (SECTION 4) — moved to family.html
- `<section id="pricing">` (SECTION 5) — moved to individual.html
- The use-case cards grid inside `<section id="about">` (SECTION 2) — now redundant given the three-audience section. Keep the section header only: "Share Stories — Past, Present, and Future" + the tagline paragraph.

**Also remove from CSS:** All CSS classes that are only used by removed sections:
- Product card styles (`.products-grid`, `.product-card`, `.product-badge`, `.product-tagline`, `.product-desc`, `.product-features`, `.product-link`) — moving to individual.html
- Pricing styles (`.pricing-header`, `.pricing-grid`, `.pricing-card`, `.pricing-tier`, `.pricing-name`, `.pricing-price`, `.pricing-period`, `.pricing-divider`, `.pricing-features`, `.pricing-btn`, `.pricing-btn-fill`, `.pricing-btn-outline`) — moving to individual.html
- Companion explainer styles (`.callout-grid`) — moving to individual.html and family.html
- Portal section styles (`.portal-layout`, `.portal-use-cases`, `.portal-use-case`, `.portal-divider`, `.portal-cta-area`) — moving to family.html
- Research section styles (`.research-inner`, `.research-body`, `.pull-quote`, `.research-closing`) — moving to family.html
- Use-case card styles (`.use-cases-grid`, `.use-case-card`) — no longer needed

**Keep in CSS (still used by remaining sections):**
- All variables, body, nav, section, hero, footer styles
- Audience card styles (`.audience-grid`, `.audience-card`, etc.) — just added
- Story layout styles (`.story-layout`, `.story-text`, `.story-sidebar`, `.story-pull-quote`) — used by SECTION 6
- About header styles (`.about-header`) — still used by SECTION 2 header

**Update nav:**
```html
<ul class="nav-links" id="navLinks">
  <li><a href="/individual">For Individuals</a></li>
  <li><a href="/family">For Families</a></li>
  <li><a href="/legacy">For Organizations</a></li>
  <li><a href="#my-story">My Story</a></li>
  <li><a href="/login" class="nav-btn-outline">Login</a></li>
  <li><a href="/individual#pricing" class="nav-cta">Sign up</a></li>
</ul>
```

**Update hero CTAs:**
```html
<div class="hero-ctas">
  <a href="/individual" class="btn-primary">Tell My Story</a>
  <a href="/family" class="btn-outline">Help Someone Else</a>
</div>
<p class="hero-invite">
  <a href="/storyteller">Have an invite code? Enter it here.</a>
</p>
```

**Files affected:**
- `apps/cogna/static/index.html`

---

### Step 6: Update footer on all pages

The footer currently lists "Storyteller," "AI Companion," and "Pricing" under Product. Update it across all pages (index.html, individual.html, family.html, legacy.html) to reflect the new structure:

```html
<div class="footer-col">
  <h4>Who It's For</h4>
  <ul>
    <li><a href="/individual">For Individuals</a></li>
    <li><a href="/family">For Families</a></li>
    <li><a href="/legacy">For Organizations</a></li>
  </ul>
</div>
<div class="footer-col">
  <h4>Account</h4>
  <ul>
    <li><a href="/portal">Guardian Portal</a></li>
    <li><a href="/storyteller">Storyteller login</a></li>
  </ul>
</div>
<div class="footer-col">
  <h4>Company</h4>
  <ul>
    <li><a href="/#my-story">My Story</a></li>
    <li><a href="/privacy">Privacy Policy</a></li>
    <li><a href="/terms">Terms of Service</a></li>
  </ul>
</div>
```

**Files affected:**
- `apps/cogna/static/index.html`
- `apps/cogna/static/individual.html`
- `apps/cogna/static/family.html`
- `apps/cogna/static/legacy.html`

---

## Connections & Dependencies

### Files That Reference This Area

- `apps/cogna/static/index.html` — the three audience cards already link to `/individual`, `/family`, `/legacy`
- `apps/cogna/server.py` — must serve the new pages
- `apps/cogna/static/portal-signup.html` — pricing source for family.html and legacy.html; not modified by this plan

### Updates Needed for Consistency

- `CLAUDE.md` — update the MyCogna App section to mention the three landing pages
- Footer on all pages — updated in Step 6

### Impact on Existing Workflows

- The `/storyteller` and `/portal/signup` flows are unchanged
- The main pricing experience moves from index.html to individual.html (self-service) and family/legacy pages (portal)
- Old bookmarks to `/#pricing` will 404-anchor-gracefully (page still loads, just no section); the nav sign-up CTA now points to `/individual#pricing`

---

## Validation Checklist

- [ ] `/individual`, `/family`, `/legacy` all return 200 (server routes added)
- [ ] All three-audience links on index.html resolve correctly
- [ ] individual.html: product cards, pricing ($0–$15), and companion explainer all present
- [ ] family.html: organizer section, JAMA section, companion explainer, and B/C/D pricing all present
- [ ] legacy.html: Legacy Collection description section and E/F pricing present
- [ ] index.html: companion explainer, organizer section, JAMA section, and pricing table are gone
- [ ] index.html nav updated; hero CTAs updated
- [ ] No broken internal links on any of the four pages
- [ ] All four pages are mobile-responsive (check `@media (max-width: 900px)` rules)
- [ ] Footer updated consistently across all four pages
- [ ] `CLAUDE.md` updated to mention the three landing pages

---

## Success Criteria

1. A visitor landing on `/individual` sees a complete, standalone page with product cards, self-service pricing, and the AI Companion explainer — no 404s, no missing content.
2. A visitor landing on `/family` sees the organizer section, the JAMA science section, the companion explainer, and B/C/D pricing with CTAs to portal signup.
3. A visitor landing on `/legacy` sees the Legacy Collection description and E/F pricing with CTAs to portal signup.
4. `index.html` is noticeably leaner — hero, "Share Stories" header, three-audience section, "Why I Built MyCogna," footer — nothing else.

---

## Notes

- All three new pages are self-contained HTML files following the existing pattern (no external CSS file, all styles inline in `<style>` block). This is consistent with every other page in the project.
- The pricing CTAs on family.html and legacy.html link to `/portal/signup` without a tier pre-selected. A future enhancement could add `?tier=B` URL param support to portal-signup.html to pre-highlight the relevant plan.
- The `SECTION 2` use-case cards (Memory Keeper, Institutional Legacy, etc.) have been present since launch but are now fully superseded by the three-audience section. They are removed in Step 5 with no audience impact.
- The founder audio clip and headshot photo remain only on index.html — they're personal context, not product marketing.

---

## Implementation Notes

**Implemented:** 2026-05-12

### Summary

- Added `/individual`, `/family`, `/legacy` routes to `server.py`
- Created `individual.html` with hero, product cards (3), $0–$15 pricing (4 tiers), and AI Companion explainer
- Created `family.html` with hero, portal organizer section, JAMA research section, AI Companion explainer, and B/C/D pricing (3 tiers)
- Created `legacy.html` with hero, Legacy Collection two-column description with Book Builder card, and E/F pricing (2 tiers)
- Cleaned up `index.html`: removed sections 3B/3C/4/5, removed use-case cards from section 2, updated nav, updated hero CTAs, removed unused CSS, updated footer
- Updated `CLAUDE.md` to document the three landing pages
- All four pages share the updated footer with "Who It's For" / "Account" / "Company" columns

### Deviations from Plan

- Renamed `products-header` CSS class to `audience-header` in the audiences section of index.html since the `.products-header` class was correctly removed during CSS cleanup

### Issues Encountered

None
