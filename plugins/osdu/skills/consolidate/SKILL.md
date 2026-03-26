---
name: consolidate
allowed-tools: Bash, Read, Write, Glob, Grep
description: >-
  Scan the Obsidian vault for stale knowledge notes and contradictory decisions.
  Flags notes not verified in 90+ days, detects scope conflicts in decisions,
  and respects human-corrected notes that never decay.
  Use when the user says "consolidate", "clean up the vault", "check for stale notes",
  or during periodic vault hygiene.
  Not for: writing new notes or ingesting new knowledge (use brain or learn skills instead).
---

# Consolidate

Prune and maintain the knowledge vault by detecting stale notes and contradictions.

## When to Use

- Periodic vault hygiene (monthly or quarterly)
- Before a planning session — ensure decisions are current
- When you suspect outdated knowledge is influencing recommendations
- User says "consolidate", "clean up the vault", "check for stale notes"

## How It Works

The consolidation script scans `03-knowledge/` and `04-reports/` and flags:

1. **Stale notes** — not verified in >90 days (configurable via `--age-days`)
2. **Contradictions** — multiple active decisions with the same `scope` value
3. **Unknown dates** — notes with no `last-verified` field and no git history

### Decay Rules

- Notes with `source: human` in frontmatter **never decay** (human-corrected knowledge)
- All other notes use `last-verified` frontmatter field, falling back to `git log` date
- Default staleness threshold: 90 days

## Usage

```bash
# Preview stale notes (dry-run is the default)
# Preview stale notes (uses $OSDU_BRAIN or ~/.osdu-brain by default)
uv run skills/consolidate/scripts/consolidate.py --dry-run

# Custom age threshold
uv run skills/consolidate/scripts/consolidate.py --age-days 60

# Explicit path override
uv run skills/consolidate/scripts/consolidate.py --path /custom/vault
```

## Output

- **stderr:** Rich-formatted table for human review
- **stdout:** JSON with `stale_notes`, `contradictions`, and `config` keys

## Frontmatter Fields

The script relies on these optional frontmatter fields:

| Field | Type | Purpose |
|-------|------|---------|
| `last-verified` | `YYYY-MM-DD` | When the note was last confirmed accurate |
| `source` | string | `human` = never decays; other values = normal decay |

Add these to notes you want to protect or track. See the brain skill templates reference
for the full field schema.
