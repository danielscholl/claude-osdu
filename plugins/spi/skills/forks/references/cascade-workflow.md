# Cascade Workflow

Moves validated changes from `fork_integration` to `main`. The cascade is the
critical path for shipping upstream updates into the Azure SPI release.

## Trigger Mechanisms

- **Automatic:** `cascade-monitor.yml` runs every 6 hours and detects when
  `fork_integration` has changes not yet in `main`
- **Manual:** `gh workflow run cascade.yml` or via GitHub Actions UI

## Two-Phase Cascade (ADR-009)

### Phase 1: fork_upstream → fork_integration

**Always requires manual review.**

- Created automatically by `sync.yml` after upstream sync
- Reviewer checks for conflicts and unexpected changes
- May require conflict resolution if upstream modified SPI-touched files

### Phase 2: fork_integration → main

**Auto-merge eligible** if ALL conditions are met:
1. Diff size < 1000 lines
2. No breaking changes detected (heuristic: no deleted public APIs, no major version bumps)
3. All status checks passing (build, validate, CodeQL)

If any condition fails, the PR requires human review.

## Cascade Labels

| Label | Meaning |
|-------|---------|
| `cascade-active` | Cascade workflow currently running |
| `cascade-ready` | fork_integration is ahead of main, ready to cascade |
| `cascade-blocked` | Cascade cannot proceed (conflicts, failing checks) |
| `human-required` | Manual intervention needed |

## Cascade Monitor (ADR-019)

`cascade-monitor.yml` runs every 6 hours:

1. Compares `fork_integration` and `main` HEADs
2. If diverged: checks for existing cascade PR
3. If no PR exists: creates one (or triggers cascade workflow)
4. If PR exists but stale (>48h): escalates via issue label

### SLA

- **48 hours** to resolve a cascade PR
- After 48h: `cascade-monitor.yml` adds `human-required` label and creates an issue

## Concurrency Control

Only one cascade pipeline runs at a time per repository. The workflow uses
GitHub's `concurrency` feature:

```yaml
concurrency:
  group: cascade-${{ github.repository }}
  cancel-in-progress: false
```

## Troubleshooting

### Cascade Blocked

```bash
# Check what's different
gh api "repos/azure/osdu-spi-partition/compare/main...fork_integration" \
  --jq '{ahead: .ahead_by, behind: .behind_by, files: [.files[].filename]}'

# Check failing status checks
gh pr list --repo "azure/osdu-spi-partition" --label "cascade-blocked" \
  --json number,statusCheckRollup --jq '.[0]'
```

### Auto-Merge Not Triggering

- Verify diff size: `gh api repos/azure/osdu-spi-partition/compare/main...fork_integration --jq '.files | length'`
- Check all required checks pass: `gh pr checks <pr-number> --repo azure/osdu-spi-partition`
- Ensure no `cascade-blocked` label

### Manual Cascade Trigger

```bash
gh workflow run cascade.yml --repo "azure/osdu-spi-partition"
```
