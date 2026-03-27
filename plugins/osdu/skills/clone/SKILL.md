---
name: clone
allowed-tools: Bash, Read
description: >-
  Clone OSDU GitLab repositories and infrastructure repos to the workspace. Supports single service, category, or all repos with bare-clone worktree or standard git clone.
  Use when the user asks to clone an OSDU repo, set up the workspace, download source code for a service, or clone infrastructure repos.
  Not for: building or testing cloned repos (use maven or acceptance-test), or checking repo status (use glab or osdu-activity).
---

# OSDU Clone

> **Execute directly. Do NOT delegate to an agent or sub-agent.**

## Step 1: Resolve the clone target

Parse the user's request to determine a single TARGET string.

### Valid targets

| Target | What it clones |
|--------|----------------|
| `partition` | Single repo by name |
| `os-core-common` | Single repo by name |
| `core` | All repos in the core category |
| `libraries` | All repos in the libraries category |
| `service:partition` | Explicit single repo |
| `category:core` | Explicit category |
| `all` | Everything |

### Categories

| Category | Repos |
|----------|-------|
| infra | cimpl-azure-provisioning |
| libraries | os-core-common, os-core-lib-azure |
| core | partition, entitlements, legal, secret, schema-service, storage, file, indexer-service, indexer-queue, search-service, dataset, register, notification |
| reference | crs-catalog-service, crs-conversion-service, unit-service |
| ingestion | ingestion-workflow |
| domain | wellbore-domain-services, seismic-store-service |

Repo names take precedence over category names. Map common aliases
(e.g., "common library" → "os-core-common", "search" → "search-service").

## Step 2: Construct the clone URL

Base: `https://community.opengroup.org`

| Pattern | GitLab path |
|---------|-------------|
| infra | `osdu/platform/deployment-and-operations/cimpl-azure-provisioning` |
| system services | `osdu/platform/system/{service}` |
| security services | `osdu/platform/security-and-compliance/{service}` |
| reference services | `osdu/platform/system/reference/{service}` |
| os-core-common | `osdu/platform/system/lib/core/os-core-common` |
| os-core-lib-azure | `osdu/platform/system/lib/cloud/azure/os-core-lib-azure` |
| wellbore-domain-services | `osdu/platform/domain-data-mgmt-services/wellbore/wellbore-domain-services` |
| seismic-store-service | `osdu/platform/domain-data-mgmt-services/seismic/seismic-dms-suite/seismic-store-service` |
| ingestion-workflow | `osdu/platform/data-flow/ingestion/ingestion-workflow` |

Construct the full URL: `https://community.opengroup.org/{path}.git`

For categories, construct a URL for each repo in the category.

## Step 3: Run the clone script

The clone script is bundled with this skill. Find and run it once per repo:

```bash
CLONE_SCRIPT=$(find ~/.claude/plugins -path "*/skills/clone/clone.py" -type f 2>/dev/null | head -1)
uv run "$CLONE_SCRIPT" <URL> [<name>]
```

The script handles everything automatically:
- Workspace resolution (`$OSDU_WORKSPACE` or cwd)
- `wt` / `git-wt` detection (bare clone + worktree if available, standard clone otherwise)
- Clone execution with skip/fail handling
- Result reporting

## After Execution

Report to the user:
- Which repos were cloned, skipped, or failed
- The clone method used (worktree or standard)
- For worktree clones, show the layout:
  ```
  <repo>/
    .bare/       ← bare clone
    .git         ← pointer file
    <branch>/    ← worktree (ready to work in)
  ```

## Working in Cloned Repos

**With worktrunk (`wt`):**
- `wt switch --create feature/xxx --base master` — create feature branch worktree

**Without worktrunk:**
- `git checkout -b feature/xxx` — create feature branch
- Standard git workflow
