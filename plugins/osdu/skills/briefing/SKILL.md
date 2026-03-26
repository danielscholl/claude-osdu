---
name: briefing
allowed-tools: Bash, Read, Write, Glob
description: >-
  Generate daily OSDU briefing notes by aggregating GitLab MRs, vault goals, and brain
  knowledge into an insightful daily note.
  Use when the user says "gm", "good morning", "briefing", "daily briefing", "morning
  standup", "what's on my plate", or "start my day".
  Not for: ad-hoc status checks or single-service queries.
---

# Daily Briefing

Generate a daily briefing note that aggregates live platform data with the brain's accumulated knowledge to produce an insightful, context-rich morning briefing.

## Quick Start

Check if the brain vault exists:
```bash
test -d "${OSDU_BRAIN:-$HOME/.osdu-brain}/00-inbox" && echo "vault: exists" || echo "vault: not found"
```

Then run the briefing script (always without `--dry-run` so the note is persisted):
```bash
uv run skills/briefing/scripts/daily-briefing.py
```

If the vault does not exist, the script falls back to stdout and suggests running `init brain`.

## Brain Vault Integration

The vault location is `$OSDU_BRAIN` if set, otherwise `~/.osdu-brain` (same fallback the script uses).

The briefing operates in two modes based on vault presence:

### Mode 1: No vault — lightweight briefing
- Script prints MR data and a quote to stdout (not persisted)
- No goals, projects, or knowledge context available
- Suggest: "Want me to set up the brain vault so briefings are saved?"

### Mode 2: Vault exists — full brain-aware briefing
The script gathers structured data (MRs, goals, projects) and writes it to `$VAULT/00-inbox/YYYY-MM-DD.md`. But the script output is only the **foundation**. Your job as the presenting agent is to **enrich it with brain knowledge** (see Synthesis Protocol below).

## Usage

```bash
# Generate today's briefing (writes to vault)
uv run skills/briefing/scripts/daily-briefing.py

# Preview without writing to vault
uv run skills/briefing/scripts/daily-briefing.py --dry-run

# Generate for a specific date
uv run skills/briefing/scripts/daily-briefing.py --date 2026-02-15
```

## Data Sources

| Source | Tool | What it gathers |
|--------|------|-----------------|
| GitLab upstream | `osdu-activity` CLI | Your MRs, all open MRs, pipeline status |
| Obsidian vault | File system | Goals (`01-goals/`), projects (`02-projects/`) |
| Brain knowledge | QMD or file scan | Reports, RCAs, decisions, architecture notes, strategy docs |
| Azure environment | `azd` / `az` CLI | CIMPL cluster health |
| GitHub | `gh` CLI | Issues assigned to you |

## Output

Writes a daily note to `$VAULT/00-inbox/YYYY-MM-DD.md` containing:
- Daily quote
- Goal progress (auto-measured from vault checkboxes)
- Per-project status with tasks and blockers
- CIMPL environment health
- GitLab MR tables (yours + recent)
- Rule-based recommendations, risks, and delegation routing
- Brain context section (agent-populated — see below)

---

## Synthesis Protocol — Brain-Aware Enrichment

This is what separates a mechanical status dump from an insightful briefing. After the script runs and writes the daily note, you enrich the presentation by reasoning over the brain's knowledge.

### Step 1: Gather brain context

If **QMD is available** (`which qmd`), use it for fast, targeted searches:
```bash
# Search for content related to today's MRs, goals, or projects
qmd query "pipeline failures partition service"
qmd query "venus milestone planning"
qmd query "dependency remediation CVE"
```

If **QMD is not available**, scan the vault directly:
```bash
# Recent reports (last 30 days)
find ${OSDU_BRAIN:-~/.osdu-brain}/04-reports -name "*.md" -mtime -30

# Knowledge and decisions
ls ${OSDU_BRAIN:-~/.osdu-brain}/03-knowledge/decisions/
ls ${OSDU_BRAIN:-~/.osdu-brain}/03-knowledge/*/
```

### Step 2: Connect knowledge to today's data

For each active area in today's briefing, look for relevant brain context:

| Today's data | Brain knowledge to search for |
|-------------|-------------------------------|
| Failing MR on service X | Past RCAs for that service (`04-reports/rca/`), known issues |
| Goal at 0% progress | Related project notes, blockers, strategy docs |
| CIMPL environment status | Deployment history, architecture decisions, audit findings |
| Dependency MRs | Dependency reports, CVE coordination plans |
| Venus-related activity | Venus strategy, milestone planning, gap analysis |
| Recent MRs from others | Any organizational context the brain surfaces (initiatives, strategy) |

### Step 3: Reason, don't just list

The value is in **connecting dots the user might miss**. Examples of good synthesis:

- "Your MR !849 on search-service is failing — the brain has an RCA from Feb 23 (`rca-master-search-azure-test`) that documented a similar test environment issue. That root cause may still apply."
- "The cimpl-parity goal is at 0%, but the cimpl-audit findings in `03-knowledge/cimpl-audit/` identified 4 specific gaps. Starting with the findings in `04-findings-recommendations` could give you a concrete path forward."
- "Venus M27 planning expects a 'defensible go/no-go scope matrix' — your open MRs on core services directly feed into that milestone's quality evidence chain."

Bad synthesis (avoid):
- Listing every file in the brain without connecting it to today's work
- Restating what the script already shows (MR counts, pipeline status)
- Speculating about things not in the brain or today's data

## Presentation Protocol

After the script runs and you've gathered brain context, present the briefing in the terminal. The structure below is a guide, not a rigid template — adapt based on what's actually relevant today.

```
Good morning. It's [Day], [Date].

"[Quote]"
   — [Attribution]

OSDU PLATFORM (GitLab upstream)
  YOUR MRs:
    > [!nnn](url) [service] — [Role] / [pipeline status] (Xd old)

  RECENT (last 21 days):
    > [!nnn](url) [service] @author — [pipeline status] (date)  [annotation if known]
    X open across Y services · Z failing

GOALS
  [goal]: [progress] — [1-line brain-informed context]

PROJECTS
  [project]: [phase/status] — [brain-informed insight if relevant]

BRAIN INSIGHTS
  [2-4 observations connecting today's data to brain knowledge]
  These should be actionable: "X relates to Y, which suggests Z"

WHAT I'D START
  1. [Action] → [self / @osdu / @cimpl]  — [why, informed by brain context]
  2. [Action] → [self / @osdu / @cimpl]  — [why]
```

End with: "Want me to kick off any of these?"

### Clickable links

The generated daily note contains full URLs for every MR. **Always use markdown links** when presenting MRs, issues, or pipelines so the user can click through directly from the terminal:
- MRs: `[!nnn](https://community.opengroup.org/.../merge_requests/nnn)`
- Pipelines: link to the MR (pipeline status is visible there)

The URLs are already in the daily note output — extract them from there.

### Recent MRs — show the landscape

The script generates a full table of recent non-merged MRs from other contributors (last 21 days). **Show this list** — it gives the user a picture of what's happening across the platform, not just their own work.

When presenting recent MRs, cross-reference them against brain knowledge discovered during Step 1. If the brain search surfaced organizational context (e.g., initiative tracking, roadmaps, workstream plans), use what you found to annotate MRs where the connection is clear:

```
  > [!562](url) rafs-ddms-services @valentin — ❌ Failed (Mar 20)
  > [!416](url) os-core-lib-azure @aasryan — ✅ Passing (Mar 20)  → [context if brain provided it]
  > [!389](url) search-service @chen — ❌ Failed (Mar 18)  → [context if brain provided it]
```

If multiple recent MRs cluster around the same area or initiative that the brain knows about, call that out in Brain Insights — it means that area is actively moving. Only annotate when the brain gave you clear context; leave MRs untagged when it didn't.

### Key principles for presentation:
- **Lead with what changed** — don't repeat yesterday's briefing verbatim
- **Connect, don't catalog** — brain insights should link today's work to accumulated knowledge
- **Show the landscape** — recent MRs give a pulse on what's moving across OSDU
- **Be specific** — reference actual vault notes and epics by name so the user can follow up
- **Stay grounded** — only surface insights that are backed by brain content or live data
- **Keep it scannable** — the user reads this in a terminal, not a document

## Requirements

- `osdu-activity` CLI installed (for GitLab data)
- Python >= 3.11 (via `uv run`)
- Optional: `qmd` CLI for fast brain knowledge search (falls back to file scan)
- Optional: `AZURE_OPENAI_ENDPOINT` + `AZURE_API_KEY` env vars for AI-generated quotes
