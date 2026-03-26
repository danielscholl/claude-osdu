---
name: osdu-engagement
allowed-tools: Bash, Read
description: >-
  Engineering contribution analysis for OSDU platform projects. Measures code contributions, reviews, and ADR engagement across teams.
  Use when analyzing contributors, commit activity, reviewer patterns, team engagement, ADR participation, or contribution trends.
  Not for: test reliability (use osdu-quality), pipeline status (use osdu-activity), or single-repo glab operations.
---

# OSDU Engagement Skill

Measure engineering involvement across OSDU platform projects using the `osdu-engagement` CLI.

For installation, authentication, output formats, and common troubleshooting, see the
[shared CLI reference](../../reference/osdu-cli-reference.md).

## Quick Start

Before first use, verify the tool is available:
```bash
osdu-engagement --version
```
If the command is not found, **stop and use the `setup` skill** to install missing dependencies.
Do NOT attempt to install tools yourself — the setup skill handles installation with the correct
sources, user approval, and verification.

If installed, skip exploration and go straight to the intent detection table below.

## When to Use This Skill

- Code contributions or commit activity
- Top contributors or active developers
- Review patterns or reviewer workload
- Architecture Decision Record (ADR) engagement
- Team participation metrics
- Contribution trends over time

**Do NOT use for:**
- Test reliability or flaky tests → use `osdu-quality`
- Open MRs, pipeline status, or issues → use `osdu-activity`
- Single-repo GitLab operations → use `glab` directly

## Intent Detection

| User Query | Command |
|------------|---------|
| "contributions", "commits", "who's active" | `osdu-engagement contribution --output markdown` |
| "top contributors", "rankings" | `osdu-engagement contribution --output markdown` |
| "trends", "monthly activity" | `osdu-engagement contribution trend --output markdown` |
| "ADR", "architecture decisions" | `osdu-engagement decision --output markdown` |
| "reviewers", "review activity" | `osdu-engagement contribution --output markdown` (includes review data) |

## Commands

| Command | Purpose | Key Filters |
|---------|---------|-------------|
| `osdu-engagement contribution` | Code contribution analysis | `--days`, `--project`, `--start-date/--end-date` |
| `osdu-engagement contribution trend` | Historical trend analysis | `--months` |
| `osdu-engagement decision` | ADR engagement analysis | `--days`, `--project` |

For full CLI options and JSON output structures, see [reference/commands.md](reference/commands.md).

## Output Handling

**Always pass `--output markdown`** for AI consumption. It produces token-optimized output
that's easy to summarize. Use `--output json` only when you need raw data for field extraction.
**Never omit the flag** — the default is `tty` which outputs ANSI codes that break parsing.

## Interpreting Results

**Healthy Patterns:**
- Multiple active contributors (not single-person dominance)
- Review load distributed across team (not one bottleneck reviewer)
- Consistent or growing activity trend
- ADRs getting engagement and discussion

**Warning Signs:**
- Single contributor dominance — bus factor risk
- Review bottleneck — few people doing all reviews
- Declining trend — team shrinking or disengaging
- ADRs with zero engagement — architecture decisions made without input

## Workflow Examples

### "Who's contributing most to partition?"

```bash
osdu-engagement contribution --project partition --output markdown
```

Highlight top contributors, their focus areas (MRs vs reviews vs comments), and whether
contribution is concentrated or distributed.

### "How engaged is the team overall?"

```bash
osdu-engagement contribution --days 30 --output markdown
osdu-engagement contribution trend --months 6 --output markdown
```

Combine current snapshot with trend to show whether engagement is growing, stable, or declining.

### "Are ADRs getting attention?"

```bash
osdu-engagement decision --days 90 --output markdown
```

Surface ADRs with low engagement (proposed but no discussion), stale ADRs, and which
projects are actively using the ADR process.

## Cross-Domain Queries

For comprehensive team health, combine with sibling skills:

```bash
# Full engagement picture
osdu-engagement contribution --project partition --output markdown  # who's contributing
osdu-quality analyze --project partition --output markdown           # test health
osdu-activity mr --project partition --output markdown               # open work
```

Synthesize: "Partition has 5 active contributors, tests are healthy at 95%, and 3 MRs
are pending review."

## Reference Documentation

- [reference/commands.md](reference/commands.md) — Full CLI options, JSON output structures
- [reference/troubleshooting.md](reference/troubleshooting.md) — Engagement-specific issues
- [../../reference/osdu-cli-reference.md](../../reference/osdu-cli-reference.md) — Installation, auth, output formats, common errors
