---
name: forks
allowed-tools: Bash, Read, Glob, Grep
description: >-
  Fork management lifecycle for Azure OSDU SPI service forks — three-branch
  strategy, upstream sync, cascade integration, conflict resolution, template
  propagation, and multi-repo status monitoring across 8 service forks.
  Use when checking sync status, reviewing cascades, resolving conflicts,
  triggering manual syncs, managing fork_upstream/fork_integration/main branches,
  or coordinating template updates across osdu-spi-* repos.
  Not for: infrastructure deployment (use iac skill), OSDU GitLab services
  (use osdu plugin), or tool installation (use setup skill).
---

# SPI Fork Management

Three-branch fork lifecycle for Azure's OSDU service forks on GitHub.

## Quick Start

```bash
gh auth status    # Must be authenticated to GitHub
```
If `gh` is not found, **stop and use the `setup` skill**.

---

## Three-Branch Strategy

Each fork repo maintains three long-lived branches:

```
Upstream OSDU (GitLab)
        │
        ▼  (daily cron sync)
  fork_upstream          ← Pure mirror of upstream community code
        │
        ▼  (automated PR, manual review)
  fork_integration       ← Merge workspace, conflict resolution
        │
        ▼  (cascade, auto-merge eligible)
  main                   ← Stable Azure SPI code → ADME downstream
```

| Branch | Purpose | Protection |
|--------|---------|-----------|
| `main` | Production-ready SPI code for ADME builds | Protected, requires PR + checks |
| `fork_upstream` | Exact mirror of upstream, no local changes | Protected, sync-only |
| `fork_integration` | Merge upstream changes, resolve conflicts | Open for conflict resolution |

---

## Fork Registry

| Service | GitHub repo | Upstream GitLab path |
|---------|-------------|---------------------|
| Partition | `azure/osdu-spi-partition` | `osdu/platform/system/partition` |
| Entitlements | `azure/osdu-spi-entitlements` | `osdu/platform/security-and-compliance/entitlements` |
| Legal | `azure/osdu-spi-legal` | `osdu/platform/security-and-compliance/legal` |
| Schema | `azure/osdu-spi-schema` | `osdu/platform/system/schema-service` |
| File | `azure/osdu-spi-file` | `osdu/platform/system/file` |
| Storage | `azure/osdu-spi-storage` | `osdu/platform/system/storage` |
| Indexer | `azure/osdu-spi-indexer` | `osdu/platform/system/indexer-service` |
| Search | `azure/osdu-spi-search` | `osdu/platform/system/search-service` |

---

## Daily Operations

### Check Sync Status Across All Forks

```bash
# List open sync PRs across all fork repos
for svc in partition entitlements legal schema file storage indexer search; do
  echo "=== osdu-spi-$svc ==="
  gh pr list --repo "azure/osdu-spi-$svc" --label "upstream-sync" --state open 2>/dev/null || echo "  (repo not yet created)"
done
```

### Check for Blocked Cascades

```bash
# Find issues labeled cascade-blocked
for svc in partition entitlements legal schema file storage indexer search; do
  echo "=== osdu-spi-$svc ==="
  gh issue list --repo "azure/osdu-spi-$svc" --label "cascade-blocked" --state open 2>/dev/null || echo "  (repo not yet created)"
done
```

### Check Branch Divergence

```bash
# For a specific fork repo
REPO="azure/osdu-spi-partition"
gh api "repos/$REPO/compare/fork_upstream...main" --jq '{ahead: .ahead_by, behind: .behind_by, status: .status}'
```

---

## Sync Workflow

The `sync.yml` workflow runs on a daily cron schedule:

1. Fetches latest upstream commit from GitLab
2. Compares with current `fork_upstream` HEAD
3. If upstream advanced: force-pushes `fork_upstream` to match
4. Creates PR from `fork_upstream` → `fork_integration`
5. Labels PR with `upstream-sync`

**Duplicate prevention (ADR-024):** State-based detection using git config prevents
daily accumulation of duplicate PRs. If a sync PR already exists for the same upstream
SHA, it is skipped.

### Trigger Manual Sync

```bash
# Via GitHub Actions workflow dispatch
gh workflow run sync.yml --repo "azure/osdu-spi-partition"
```

---

## Cascade Workflow

Cascade moves validated changes from `fork_integration` to `main`.

### Two Phases

1. **fork_upstream → fork_integration** — Always requires manual review. An automated
   PR is created by the sync workflow. A reviewer must check for conflicts and approve.

2. **fork_integration → main** — Auto-merge eligible if ALL conditions met:
   - Diff size < 1000 lines
   - No breaking changes detected
   - All status checks passing

If auto-merge criteria not met, a human must review and approve.

### Trigger Cascade Manually

```bash
gh workflow run cascade.yml --repo "azure/osdu-spi-partition"
```

### Check Cascade Status

```bash
# List cascade-related labels on open PRs
gh pr list --repo "azure/osdu-spi-partition" --label "cascade-active" --state open
gh pr list --repo "azure/osdu-spi-partition" --label "cascade-ready" --state open
```

---

## Conflict Resolution

Conflicts appear in `fork_integration` when upstream changes collide with Azure SPI code.

### Where Conflicts Occur

- **pom.xml** — Dependency version differences between upstream and Azure SPI
- **application.properties** — Different config defaults
- **Provider implementations** — SPI layer files that upstream also modified

### Resolution Process

1. A GitHub Issue is created with label `human-required`
2. Check out `fork_integration` locally:
   ```bash
   gh repo clone azure/osdu-spi-partition -- --branch fork_integration
   ```
3. Review the conflict markers in affected files
4. Resolve conflicts preserving Azure SPI-specific code
5. Commit and push to `fork_integration`
6. Close the conflict issue
7. The cascade workflow will pick up the resolution

### SLA

Conflicts must be resolved within **48 hours** (monitored by `cascade-monitor.yml`).
After 48 hours, the cascade monitor escalates via issue labels.

---

## Template Sync

The osdu-spi template propagates workflow updates to all forks via `sync-template.yml`:

1. Template repo publishes a new version (via Release Please)
2. Each fork's `sync-template.yml` checks for template updates
3. If template advanced: creates a PR updating workflows, actions, and configuration
4. PR labeled with `template-sync`

### Check Template Sync Status

```bash
for svc in partition entitlements legal schema file storage indexer search; do
  echo "=== osdu-spi-$svc ==="
  gh pr list --repo "azure/osdu-spi-$svc" --label "template-sync" --state open 2>/dev/null || echo "  (repo not yet created)"
done
```

---

## ADR Quick Reference

31 ADRs in the osdu-spi template (`doc/src/adr/`). Most critical for daily work:

| ADR | Decision |
|-----|----------|
| 001 | Three-branch fork management strategy |
| 005 | Automated conflict management — conflicts isolated in fork_integration |
| 009 | Asymmetric cascade review — upstream→integration manual, integration→main auto-eligible |
| 015 | Template/fork workflow separation — `.github/workflows/` vs `.github/template-workflows/` |
| 019 | Cascade monitor — human-centric with automated safety net |
| 024 | Sync duplicate prevention via state-based detection |
| 025 | Java/Maven build architecture (Temurin 17, Maven 3.9+, JaCoCo) |
| 029 | GitHub App authentication (replaces PATs with short-lived tokens) |

---

## Common Tasks

### Initialize a New Fork (CLI)

Configure the target org (defaults to `azure` for production):

```bash
ORG="${SPI_ORG:-azure}"
```

For engineering system testing with a personal org:
```bash
export SPI_ORG=danielscholl-osdu
```

**Single service initialization:**

Do NOT use `gh repo create --template` — it fails with SSO errors on the `azure` org.
Use the clone+push approach instead:

```bash
ORG="${SPI_ORG:-azure}"
SERVICE="partition"
REPO="$ORG/osdu-spi-$SERVICE"
TEMPLATE="${SPI_TEMPLATE:-azure/osdu-spi}"

# Step 1: Check if repo exists
if gh repo view "$REPO" --json name >/dev/null 2>&1; then
  echo "Repository $REPO already exists"
else
  # Step 2: Clone public template and create repo
  WORK_DIR=$(mktemp -d)
  git clone "https://github.com/$TEMPLATE" "$WORK_DIR/osdu-spi-$SERVICE"
  cd "$WORK_DIR/osdu-spi-$SERVICE"
  git remote remove origin && git branch -M main
  gh repo create "$REPO" --source . --public --push
  cd - && rm -rf "$WORK_DIR"

  # Step 3: Wait for Initialize Fork workflow (~15s auto-triggered by push)
  # Step 4: Comment upstream URL on init issue
  # Step 5: Wait for Initialize Complete workflow (~30s)
  # See references/fork-init.md for the full workflow polling pattern
fi
```

**Branch-based testing** (test template changes before merging to azure/osdu-spi):

```bash
TEMPLATE_BRANCH="feature/new-sync-logic"
WORK_DIR=$(mktemp -d)
git clone --branch "$TEMPLATE_BRANCH" "https://github.com/$TEMPLATE" "$WORK_DIR/osdu-spi-$SERVICE"
cd "$WORK_DIR/osdu-spi-$SERVICE"
git branch -M main && git remote remove origin
gh repo create "$REPO" --source . --public --push
cd - && rm -rf "$WORK_DIR"
# Init workflow auto-triggers on push — continue with Steps 3-5
```

**For complete initialization details** including upstream URL mapping, workflow
polling, bulk initialization, and troubleshooting:
see [references/fork-init.md](references/fork-init.md)

### View All Fork Repos

```bash
ORG="${SPI_ORG:-azure}"
gh repo list "$ORG" --json name --jq '.[].name' | grep -i 'osdu-spi-\|^partition$\|^entitlements$\|^legal$\|^schema$\|^file$\|^storage$\|^indexer$\|^search$' | sort
```

### Bulk Status Check

For a quick summary, use the `status` skill. For inline checking:

```bash
ORG="${SPI_ORG:-azure}"
for svc in partition entitlements legal schema file storage indexer search; do
  REPO="$ORG/osdu-spi-$svc"
  OPEN_PRS=$(gh pr list --repo "$REPO" --state open --json number --jq 'length' 2>/dev/null || echo "?")
  OPEN_ISSUES=$(gh issue list --repo "$REPO" --state open --json number --jq 'length' 2>/dev/null || echo "?")
  echo "osdu-spi-$svc: ${OPEN_PRS} PRs, ${OPEN_ISSUES} issues"
done
```
