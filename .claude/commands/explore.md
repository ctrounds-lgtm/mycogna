
# Explore

> Interactive exploration of a new feature, system, or capability for the Morningside Group workspace.

## Variables

idea: $ARGUMENTS (describe the feature, system, or capability you want to explore)

---

## Instructions

You are running an **interactive exploration session**. Your job is to help Liam shape an idea into a clear, well-scoped concept through structured Q&A. Do NOT run through all stages autonomously — present your findings at each stage, ask questions, and wait for Liam's responses before proceeding.

**Output:** A feature exploration doc saved to `plans/explore-YYYY-MM-DD-{descriptive-name}.md`

**Downstream:** The explore doc can be passed to `/automate` for technical feasibility, `/create-plan` for implementation planning, or stand alone as a reference.

---

## Stage 1: DISCOVERY — Understand the Vision

**Goal:** Understand what Liam wants and establish scope boundaries.

**Actions:**
1. Read the idea/arguments provided
2. Read relevant workspace context:
   - `CLAUDE.md` for workspace structure
   - Relevant `context/` files for the business area this touches
   - Relevant `reference/` files for existing patterns
3. Summarize your understanding of the idea in 2-3 sentences
4. Ask 2-4 clarifying questions to establish:
   - What problem does this solve?
   - Who uses this and when?
   - What does "done" look like?
   - What's explicitly out of scope?

**STOP and wait for Liam's responses before proceeding.**

---

## Stage 2: RESEARCH — Explore the Landscape

**Goal:** Understand what exists, what's possible, and what constraints apply.

**Actions:**
1. Research the workspace for relevant existing systems, commands, or patterns that relate to this idea
2. If the idea involves external tools/APIs, research what's available
3. If the idea touches data, query `data/morningside.db` to understand what data exists and what shape it's in
4. Present findings:
   - What already exists that's relevant
   - What options are available (with pros/cons)
   - What constraints or dependencies you've found
   - Rough complexity estimate (Small / Medium / Large)

**STOP and wait for Liam's input on which direction to take before proceeding.**

---

## Stage 3: SHAPE — Define the Feature

**Goal:** Converge on a clear feature definition.

**Actions:**
1. Based on discovery + research + Liam's input, define:
   - **What it does** — clear description of the feature/system
   - **How it works** — user flow or interaction model
   - **What it produces** — outputs, artifacts, or changes
   - **How it connects** — relationship to existing workspace systems
2. If there are meaningful design choices, present 2-3 options with tradeoffs and a recommendation
3. Flag anything that feels risky, complex, or uncertain

**STOP and wait for Liam to confirm or adjust the shape before proceeding.**

---

## Stage 4: SCOPE — Break It Down

**Goal:** Turn the shaped concept into a scoped breakdown.

**Actions:**
1. Break the feature into logical components or phases
2. For each component, note:
   - What it involves
   - Dependencies (on other components or external factors)
   - Rough effort (Small / Medium / Large)
3. Recommend a phasing if the feature is large (what to build first, what can wait)
4. Identify the minimum viable version vs. the full vision

**STOP and present the breakdown for Liam's review.**

---

## Stage 5: OUTPUT — Write the Exploration Doc

**Goal:** Capture everything in a structured document.

**Actions:**
1. Compile the exploration into a doc and save to `plans/explore-YYYY-MM-DD-{descriptive-name}.md`
2. Use this format:

```
# Explore: {Feature Name}

**Created:** YYYY-MM-DD
**Status:** Explored
**Origin:** {One-line description of the original idea}

---

## Vision

{2-3 sentences on what this is and why it matters}

## Problem Statement

{What problem does this solve? Who has this problem?}

## Proposed Solution

### What It Does
{Clear description}

### How It Works
{User flow, interaction model, or system design}

### What It Produces
{Outputs, artifacts, changes}

## Scope

### Minimum Viable Version
{The smallest useful version}

### Full Vision
{The complete version with all bells and whistles}

### Components
{Breakdown of logical pieces with effort estimates}

### Out of Scope
{What this explicitly does NOT include}

## Technical Considerations

{Constraints, dependencies, risks, unknowns}

## Connections

{How this relates to other workspace systems, businesses, or strategies}

## Next Steps

{Recommended path: /automate, /create-plan, or /implement}

## Discovery Notes

{Key decisions made during the exploration, alternatives considered, Liam's preferences}
```

3. Report the file path and recommend next steps

---

## Critical Rules

- **Interactive** — Present findings, wait for responses. Never complete all stages autonomously.
- **Honest about complexity** — Flag hard problems clearly. Don't underestimate.
- **Workspace-aware** — Always ground recommendations in what already exists in this workspace.
- **Not a plan** — The explore doc captures the "what" and "why." Implementation details belong in `/create-plan` or `/automate`.
- **Respect settled decisions** — Don't relitigate decisions Liam has already made unless there's a strong technical reason.
