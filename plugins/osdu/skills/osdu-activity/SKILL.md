---
name: osdu-activity
allowed-tools: Bash, Read
description: >-
  OSDU platform monitoring across 30+ GitLab services using the `osdu-activity` CLI — the only way to query OSDU MRs, pipelines, and issues in bulk.
  Use when the user asks about open MRs across OSDU services, OSDU pipeline failures, OSDU CI status, failed jobs by cloud provider, milestone progress (M25/M26), or issue tracking across the platform.
  Not for: glab CLI syntax help, actions on a single non-OSDU repo (creating/merging MRs in cimpl-azure-provisioning), contributor rankings (use osdu-engagement), or test flakiness (use osdu-quality).
---

# OSDU Activity Skill

Track GitLab activity (MRs, pipelines, issues) across OSDU platform projects using the `osdu-activity` CLI.

For installation, authentication, output formats, and common troubleshooting, see the
[shared CLI reference](../../reference/osdu-cli-reference.md).

## Quick Start

Before first use, verify the tool is available:
```bash
osdu-activity --version
```
If the command is not found, **stop and use the `setup` skill** to install missing dependencies.
Do NOT attempt to install tools yourself — the setup skill handles installation with the correct
sources, user approval, and verification.

If installed, skip exploration and go straight to the intent detection table below.

## When to Use This Skill

- Open or pending merge requests across OSDU services
- Pipeline status or failures
- Failed jobs in CI/CD (filterable by provider)
- Open issues or ADR issues
- Milestone progress and release readiness triage

**Do NOT use for:**
- Test pass rates or flaky tests → use `osdu-quality`
- Contributor rankings or team engagement → use `osdu-engagement`
- Single-repo GitLab operations (creating MRs, merging) → use `glab` directly
- glab CLI syntax help → use the `glab` skill

## Intent Detection

| User Query | Command |
|------------|---------|
| "open MRs", "pending reviews" | `osdu-activity mr --output markdown` |
| "pipeline status", "CI status" | `osdu-activity pipeline --output markdown` |
| "failed jobs", "what's failing" | `osdu-activity pipeline --style list --output markdown` |
| "open issues", "bugs" | `osdu-activity issue --output markdown` |
| "ADR issues" | `osdu-activity issue --adr --output markdown` |
| "draft MRs", "WIP" | `osdu-activity mr --include-draft --output markdown` |
| "M26 milestone", "release triage" | `osdu-activity mr --milestone M26 --output markdown` |
| "MRs by johndoe" | `osdu-activity mr --author johndoe --output markdown` |
| "my MRs", "what's on my plate" | `osdu-activity mr --user <username> --output markdown` |
| "merged MRs" | `osdu-activity mr --state merged --output markdown` |

## Commands

| Command | Purpose | Key Filters |
|---------|---------|-------------|
| `osdu-activity mr` | Track merge requests | `--project`, `--milestone`, `--author`, `--user`, `--state`, `--include-draft` |
| `osdu-activity pipeline` | Track pipeline status | `--project`, `--provider`, `--style list` |
| `osdu-activity issue` | Track open issues | `--project`, `--adr`, `--style list` |

For full CLI options and JSON output structures, see [reference/commands.md](reference/commands.md).

## Output Handling

**Always pass `--output markdown`** for AI consumption. It produces token-optimized output
that's easy to summarize. Use `--output json` only when you need raw data for field extraction.
**Never omit the flag** — the default is `tty` which outputs ANSI codes that break parsing.

## Workflow Examples

### "What MRs are open across the platform?"

```bash
osdu-activity mr --output markdown
```

Lead with the key finding ("Storage has 3 MRs waiting, indexer has 5"). Highlight any
with failing pipelines. Note stale MRs (open > 14 days with no updates).

### "What's failing in CI?"

```bash
osdu-activity pipeline --style list --output markdown
```

Group failures by pattern (same stage? same provider?). If failures cluster on one
provider, it's likely an environment issue, not a code bug.

### "Release triage for M26"

```bash
osdu-activity mr --milestone M26 --output markdown
osdu-activity mr --milestone M26 --state all --output markdown
```

Show open vs merged vs closed. Flag stale MRs. Identify blockers (failing pipelines,
no reviewers assigned).

### "What's on my plate?"

```bash
osdu-activity mr --user <username> --output markdown
```

Shows MRs where the user is author, assignee, or reviewer.

## Cross-Domain Queries

For comprehensive project health, combine with sibling skills:

```bash
# Full status for a service
osdu-activity mr --project partition --output markdown        # open MRs
osdu-activity pipeline --project partition --output markdown   # pipeline health
osdu-quality analyze --project partition --output markdown     # test reliability
osdu-engagement contribution --project partition --output markdown  # team engagement
```

Synthesize into a unified status report.

## Reference Documentation

- [reference/commands.md](reference/commands.md) — Full CLI options, JSON output structures
- [reference/troubleshooting.md](reference/troubleshooting.md) — Activity-specific issues
- [../../reference/osdu-cli-reference.md](../../reference/osdu-cli-reference.md) — Installation, auth, output formats, common errors
