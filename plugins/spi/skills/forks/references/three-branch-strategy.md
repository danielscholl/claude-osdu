# Three-Branch Fork Management Strategy

Condensed from ADR-001. This is the foundational architecture for all SPI service forks.

## Problem

Microsoft must maintain Azure-specific SPI code while staying in sync with the
upstream OSDU community repositories on GitLab. A naive fork diverges quickly;
manual syncing is error-prone and unsustainable across 8 services.

## Solution: Three Long-Lived Branches

```
Upstream OSDU (GitLab, community.opengroup.org)
        │
        │  Daily cron sync (sync.yml)
        ▼
  fork_upstream          ← Pure mirror, force-pushed to match upstream
        │
        │  Automated PR (requires manual review)
        ▼
  fork_integration       ← Merge workspace for conflict resolution
        │
        │  Cascade (auto-merge eligible if criteria met)
        ▼
  main                   ← Stable Azure SPI code → ADME downstream builds
```

### Branch Roles

| Branch | Write Access | Content | Protection |
|--------|-------------|---------|-----------|
| `main` | PR-only, requires checks | Azure SPI code + upstream core | Protected |
| `fork_upstream` | Sync workflow only | Exact upstream mirror | Protected |
| `fork_integration` | PR + direct push (conflict resolution) | Merged upstream + SPI | Semi-protected |

### Why Three Branches?

- **Two branches (main + upstream)** doesn't work — merge conflicts block main directly
- **Three branches** isolate conflict resolution in `fork_integration`, keeping `main` stable
- `fork_upstream` provides a clean reference point for "what is upstream right now?"

## Branch Lifecycle

### Normal Flow (No Conflicts)

1. Upstream pushes a commit to `master` on GitLab
2. `sync.yml` detects the new commit (daily cron)
3. `fork_upstream` is force-pushed to match upstream HEAD
4. PR created: `fork_upstream` → `fork_integration`
5. Reviewer approves (no conflicts)
6. PR merged into `fork_integration`
7. `cascade.yml` creates PR: `fork_integration` → `main`
8. Auto-merge criteria met → merged automatically
9. `integration-cleanup.yml` syncs `fork_integration` back to `main`

### Conflict Flow

1. Steps 1-4 same as above
2. PR shows merge conflicts (upstream changed a file SPI also modified)
3. GitHub Issue created with `human-required` label
4. Developer checks out `fork_integration`, resolves conflicts
5. Developer pushes resolution to `fork_integration`
6. PR can now merge cleanly
7. Remainder of flow continues as normal

## Key Principles

- **`fork_upstream` is never modified locally** — it is always a pure mirror
- **Azure SPI code only lives in `main`** — never committed to `fork_upstream` or `fork_integration` directly (except conflict resolutions)
- **`fork_integration` is a workspace, not a stable branch** — it gets reset to match `main` after each cascade
- **All changes to `main` go through PRs** — no direct pushes

## Branch Protection Rules

```json
{
  "main": {
    "required_reviews": 1,
    "required_status_checks": ["build", "validate"],
    "dismiss_stale_reviews": true,
    "restrict_pushes": true
  },
  "fork_upstream": {
    "restrict_pushes": ["sync-workflow-bot"],
    "allow_force_pushes": ["sync-workflow-bot"]
  },
  "fork_integration": {
    "required_status_checks": ["build"]
  }
}
```

## Integration Cleanup

After a cascade merges `fork_integration` → `main`, the `integration-cleanup.yml`
workflow synchronizes `fork_integration` with `main` to prevent false divergence
detection on the next sync cycle.
