# Sync Operations

How upstream synchronization works and how to manage it.

## Daily Sync (sync.yml)

Runs on a daily cron schedule for each fork repository.

### Process

1. Fetch the upstream GitLab repository's default branch HEAD
2. Compare with current `fork_upstream` HEAD
3. **Decision matrix (ADR-024):**
   - Same SHA → Skip (no change)
   - New SHA, no existing sync PR → Create new sync
   - New SHA, existing sync PR for older SHA → Update branch
   - Abandoned sync PR → Clean up
4. If sync needed: force-push `fork_upstream` to match upstream HEAD
5. Create PR: `fork_upstream` → `fork_integration`
6. Label PR with `upstream-sync`

### Duplicate Prevention (ADR-024)

State-based detection using git config tracks the last-synced SHA:

```bash
# Check last synced state
git -C .bare config --get sync.last-upstream-sha
```

This prevents accumulation of duplicate PRs when upstream doesn't change.

## Template Sync (sync-template.yml)

Propagates workflow and configuration updates from the osdu-spi template to forks.

### Process

1. Check template repo for newer commits than last sync
2. If template advanced: copy updated workflows from template-workflows/
3. Apply sync-config.json rules for file-level sync
4. Create PR with `template-sync` label

### sync-config.json

Controls which files are synced from template to forks:

```json
{
  "sync": {
    "workflows": {
      "source": ".github/template-workflows/",
      "destination": ".github/workflows/",
      "files": ["sync.yml", "cascade.yml", "build.yml", ...]
    },
    "actions": {
      "source": ".github/actions/",
      "destination": ".github/actions/"
    }
  }
}
```

## Manual Sync Operations

### Trigger Sync for One Repo

```bash
gh workflow run sync.yml --repo "azure/osdu-spi-partition"
```

### Trigger Sync for All Repos

```bash
for svc in partition entitlements legal schema file storage indexer search; do
  echo "Triggering sync for osdu-spi-$svc..."
  gh workflow run sync.yml --repo "azure/osdu-spi-$svc" 2>/dev/null || echo "  (skipped)"
done
```

### Check Sync Status

```bash
# Open sync PRs
for svc in partition entitlements legal schema file storage indexer search; do
  SYNCS=$(gh pr list --repo "azure/osdu-spi-$svc" --label "upstream-sync" --state open --json number --jq 'length' 2>/dev/null || echo "?")
  echo "osdu-spi-$svc: $SYNCS open sync PRs"
done
```

### Check Template Sync Status

```bash
for svc in partition entitlements legal schema file storage indexer search; do
  SYNCS=$(gh pr list --repo "azure/osdu-spi-$svc" --label "template-sync" --state open --json number --jq 'length' 2>/dev/null || echo "?")
  echo "osdu-spi-$svc: $SYNCS template-sync PRs"
done
```

## Sync Failures

### Upstream Unreachable

If GitLab is down, the sync workflow exits gracefully and retries on next cron.
No PR is created. Check workflow run logs:

```bash
gh run list --repo "azure/osdu-spi-partition" --workflow sync.yml --limit 5
```

### Merge Conflicts in Sync PR

Conflicts between `fork_upstream` and `fork_integration` mean Azure SPI code
and upstream changed the same files. This is handled by the conflict resolution
process (see cascade-workflow.md).

### Force Push Blocked

If `fork_upstream` branch protection blocks the sync bot's force push:
1. Check GitHub App permissions
2. Verify the sync workflow has the correct `contents: write` permission
3. Check branch protection rules allow the GitHub App to push
