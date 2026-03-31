---
name: status
allowed-tools: Bash, Read, Glob, Grep
description: >-
  Cross-repository status aggregation for SPI service forks — issues, pull
  requests, workflow runs, and alerts across all fork repos in a single
  dashboard. Highlights cascade-blocked issues, human-required labels, failing
  workflows, and pending sync/template-sync PRs. Configurable org via SPI_ORG.
  Use when checking overall fork health, asking what's open across repos,
  looking for blocked cascades, pending reviews, needing a dashboard of all
  SPI fork activity, or monitoring the state of the engineering system.
  Trigger on "status", "dashboard", "what's open", "any blocked cascades",
  "pending PRs across forks", "fork health overview", "failing workflows",
  "issues across repos".
  Not for: triggering syncs or cascades (use forks skill), infrastructure
  health or cluster status (use health skill), deploying (use iac skill),
  tool installation (use setup skill).
---

# SPI Fork Status Dashboard

Cross-repository aggregation of issues, PRs, and workflows across all SPI
service fork repos.

## Quick Start

```bash
gh auth status
```
If `gh` is not found, **stop and use the `setup` skill**.

## Configuration

```bash
# Which GitHub org holds the fork repos (default: azure)
ORG="${SPI_ORG:-azure}"

# Services to monitor (space-separated)
SERVICES="partition entitlements legal schema file storage indexer search"
```

**Alerts** are items needing human attention: cascade-blocked issues, human-required
labels, failing workflows on main, and sync PRs open >24h without review.

Override the org for personal test forks:
```bash
export SPI_ORG=danielscholl-osdu
```

The service list can be overridden via `SPI_SERVICES` env var if needed.

---

## Full Dashboard

Collect data across all repos and present a summary table + alert callouts.

### Step 1: Collect Data

For each service, gather issues, PRs, and workflow status:

```bash
ORG="${SPI_ORG:-azure}"
SERVICES="${SPI_SERVICES:-partition entitlements legal schema file storage indexer search}"

for svc in $SERVICES; do
  REPO="$ORG/osdu-spi-$svc"

  # Issues (open, excluding PRs)
  ISSUES=$(gh issue list --repo "$REPO" --state open --json number,title,labels,assignees \
    --jq 'map(select(.title)) | length' 2>/dev/null || echo "?")

  # PRs (open)
  PRS=$(gh pr list --repo "$REPO" --state open --json number --jq 'length' 2>/dev/null || echo "?")

  # Sync PRs specifically
  SYNC_PRS=$(gh pr list --repo "$REPO" --state open --label "upstream-sync" --json number --jq 'length' 2>/dev/null || echo "0")

  # Latest workflow conclusion on main
  WORKFLOW=$(gh run list --repo "$REPO" --branch main --limit 1 --json conclusion \
    --jq '.[0].conclusion // "none"' 2>/dev/null || echo "?")

  # Alerts
  HUMAN=$(gh issue list --repo "$REPO" --label "human-required" --state open --json number --jq 'length' 2>/dev/null || echo "0")
  BLOCKED=$(gh issue list --repo "$REPO" --label "cascade-blocked" --state open --json number --jq 'length' 2>/dev/null || echo "0")

  echo "$svc|$ISSUES|$PRS|$SYNC_PRS|$WORKFLOW|$HUMAN|$BLOCKED"
done
```

### Step 2: Present Summary Table

Format the collected data as:

```
| Service      | Issues | PRs | Sync PRs | Workflows | Alerts           |
|-------------|--------|-----|----------|-----------|------------------|
| partition    | 0      | 2   | 1        | success   |                  |
| entitlements | 1      | 1   | 0        | failure   | human-required   |
| legal        | 0      | 0   | 0        | success   |                  |
| ...          |        |     |          |           |                  |
```

### Step 3: Alert Callouts

Highlight anything needing attention:

```
ATTENTION:
- entitlements: Issue #12 "Merge conflict in pom.xml" [human-required]
- storage: PR #5 "upstream-sync" needs review
- indexer: Latest workflow on main FAILED
- search: cascade-blocked issue open for >24h
```

---

## Focused Queries

### Blocked Cascades

```bash
ORG="${SPI_ORG:-azure}"
for svc in partition entitlements legal schema file storage indexer search; do
  BLOCKED=$(gh issue list --repo "$ORG/osdu-spi-$svc" --label "cascade-blocked" --state open \
    --json number,title --jq '.[] | "  #\(.number) \(.title)"' 2>/dev/null)
  if [ -n "$BLOCKED" ]; then
    echo "osdu-spi-$svc:"
    echo "$BLOCKED"
  fi
done
```

### Human-Required Issues

```bash
ORG="${SPI_ORG:-azure}"
for svc in partition entitlements legal schema file storage indexer search; do
  ISSUES=$(gh issue list --repo "$ORG/osdu-spi-$svc" --label "human-required" --state open \
    --json number,title,assignees \
    --jq '.[] | "  #\(.number) \(.title) @\(.assignees | map(.login) | join(","))"' 2>/dev/null)
  if [ -n "$ISSUES" ]; then
    echo "osdu-spi-$svc:"
    echo "$ISSUES"
  fi
done
```

### Sync PRs Pending Review

```bash
ORG="${SPI_ORG:-azure}"
for svc in partition entitlements legal schema file storage indexer search; do
  PRS=$(gh pr list --repo "$ORG/osdu-spi-$svc" --label "upstream-sync" --state open \
    --json number,title,reviewDecision,createdAt \
    --jq '.[] | "  #\(.number) \(.title) review=\(.reviewDecision // "none") created=\(.createdAt)"' 2>/dev/null)
  if [ -n "$PRS" ]; then
    echo "osdu-spi-$svc:"
    echo "$PRS"
  fi
done
```

### Template-Sync PRs

```bash
ORG="${SPI_ORG:-azure}"
for svc in partition entitlements legal schema file storage indexer search; do
  PRS=$(gh pr list --repo "$ORG/osdu-spi-$svc" --label "template-sync" --state open \
    --json number,title --jq '.[] | "  #\(.number) \(.title)"' 2>/dev/null)
  if [ -n "$PRS" ]; then
    echo "osdu-spi-$svc:"
    echo "$PRS"
  fi
done
```

### Failing Workflows

```bash
ORG="${SPI_ORG:-azure}"
for svc in partition entitlements legal schema file storage indexer search; do
  FAILED=$(gh run list --repo "$ORG/osdu-spi-$svc" --branch main --limit 3 \
    --json name,conclusion,createdAt \
    --jq '.[] | select(.conclusion == "failure") | "  \(.name) FAILED \(.createdAt)"' 2>/dev/null)
  if [ -n "$FAILED" ]; then
    echo "osdu-spi-$svc:"
    echo "$FAILED"
  fi
done
```

### PR Detail (Single Repo)

```bash
ORG="${SPI_ORG:-azure}"
SERVICE="partition"
gh pr list --repo "$ORG/osdu-spi-$SERVICE" --state open \
  --json number,title,isDraft,reviewDecision,headRefName,labels,author,createdAt \
  --jq '.[] | "  #\(.number) \(.title)\n    branch=\(.headRefName) draft=\(.isDraft) review=\(.reviewDecision // "none")\n    labels=[\(.labels | map(.name) | join(","))] author=\(.author.login) created=\(.createdAt)"'
```

### Branch Divergence

Check how far `fork_integration` has drifted from `main`:

```bash
ORG="${SPI_ORG:-azure}"
for svc in partition entitlements legal schema file storage indexer search; do
  REPO="$ORG/osdu-spi-$svc"
  DIFF=$(gh api "repos/$REPO/compare/main...fork_integration" \
    --jq '{ahead: .ahead_by, behind: .behind_by}' 2>/dev/null || echo '{"error": "no data"}')
  echo "osdu-spi-$svc: $DIFF"
done
```

---

## Output Format

When presenting results, always use this structure:

1. **Summary table** — One row per service, counts + status
2. **Alert callouts** — Only items needing attention (human-required, cascade-blocked, failing workflows, stale PRs)
3. **Detail panels** — Only on request or for repos with alerts

If no alerts exist, say so explicitly: "All 8 fork repos are clean — no blocked cascades, no human-required issues, no failing workflows."

## Integration

- If issues found → suggest using `forks` skill to resolve (sync, cascade, conflict resolution)
- If workflows failing → suggest using `forks` skill to investigate or re-trigger
- For infrastructure issues → suggest `health` skill
- For deploying fixes → suggest `iac` skill
