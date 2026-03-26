---
name: clone
allowed-tools: Bash, Read
description: >-
  Clone OSDU GitLab repositories and infrastructure repos to the workspace. Supports single service, category, or all repos with bare-clone worktree or standard git clone.
  Use when the user asks to clone an OSDU repo, set up the workspace, download source code for a service, or clone infrastructure repos.
  Not for: building or testing cloned repos (use maven or acceptance-test), or checking repo status (use glab or osdu-activity).
---

# OSDU Clone Workflow

Clone repositories into the OSDU workspace.

## Path Resolution

The workspace location is determined by:
- `$OSDU_WORKSPACE` environment variable (if set)
- Default: current working directory

All paths below use `$OSDU_WORKSPACE` to mean the resolved location.

```bash
OSDU_WORKSPACE="${OSDU_WORKSPACE:-$(pwd)}"
```

## Clone Method Detection

Before cloning, detect which method to use:

```bash
which wt 2>/dev/null || which git-wt 2>/dev/null
# Windows (PowerShell): Get-Command wt -ErrorAction SilentlyContinue
```

- **`wt` found**: Use bare clone + worktree layout (preferred — enables `wt` worktree management)
- **Not found**: Use standard `git clone` (simpler, still works)

## Workspace Layout

**With worktrunk (bare clone + worktree):**
```
$OSDU_WORKSPACE/
├── partition/
│   ├── .bare/        # bare clone
│   └── master/       # default worktree
├── storage/
│   ├── .bare/
│   └── master/
└── ...
```

**Without worktrunk (standard clone):**
```
$OSDU_WORKSPACE/
├── partition/         # regular clone (default branch checked out)
├── storage/           # regular clone
└── ...
```

Both layouts work with the rest of the plugin.

## Categories

| Category | Repos |
|----------|-------|
| infra | cimpl-azure-provisioning |
| libraries | os-core-common, os-core-lib-azure |
| core | partition, entitlements, legal, secret, schema-service, storage, file, indexer-service, indexer-queue, search-service, dataset, register, notification |
| reference | crs-catalog-service, crs-conversion-service, unit-service |
| ingestion | ingestion-workflow |
| domain | wellbore-domain-services, seismic-store-service |

## URL Construction

Base: `https://community.opengroup.org`

Path resolution (from Project Registry):
- infra → `osdu/platform/deployment-and-operations/cimpl-azure-provisioning`
- system services → `osdu/platform/system/{service}`
- security services → `osdu/platform/security-and-compliance/{service}`
- reference services → `osdu/platform/system/reference/{service}`
- libraries → `osdu/platform/system/lib/core/os-core-common` and `osdu/platform/system/lib/cloud/azure/os-core-lib-azure`
- domain → `osdu/platform/domain-data-mgmt-services/wellbore/wellbore-domain-services` and `osdu/platform/domain-data-mgmt-services/seismic/seismic-dms-suite/seismic-store-service`
- ingestion → `osdu/platform/data-flow/ingestion/ingestion-workflow`

## Parsing Algorithm

1. **Check for explicit prefix first:**
   - `service:<name>` → clone that single service
   - `category:<name>` → clone all repos in that category
   - `all` → clone everything

2. **If no prefix, apply precedence rules:**
   - **FIRST**: Check if input exactly matches a repo name → clone that single repo only
   - **SECOND**: Check if input matches a category → clone all in category
   - **OTHERWISE**: Report error "Unknown repo or category"

**Important:** Repo names take precedence over categories.

## Execution

### Method 1: Bare clone + worktree (when `wt` is installed)

This layout enables worktrunk worktree management after cloning.

```bash
REPO="partition"
CLONE_URL="https://community.opengroup.org/osdu/platform/system/partition.git"

# Skip if already cloned
if [ -d "$OSDU_WORKSPACE/$REPO" ]; then
  echo "Skipping $REPO — already exists"
  continue
fi

# 1. Bare clone
mkdir -p "$OSDU_WORKSPACE/$REPO"
git clone --bare "$CLONE_URL" "$OSDU_WORKSPACE/$REPO/.bare"

# 2. Set up .git pointer (enables wt and git commands)
echo "gitdir: ./.bare" > "$OSDU_WORKSPACE/$REPO/.git"
# Windows (PowerShell): Set-Content -Path "$env:OSDU_WORKSPACE\$REPO\.git" -Value "gitdir: ./.bare" -NoNewline

# 3. Configure fetch refspec (bare clones don't track remote branches by default)
git -C "$OSDU_WORKSPACE/$REPO/.bare" config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
git -C "$OSDU_WORKSPACE/$REPO/.bare" fetch origin

# 4. Detect default branch and create worktree
DEFAULT_BRANCH=$(git -C "$OSDU_WORKSPACE/$REPO/.bare" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
DEFAULT_BRANCH=${DEFAULT_BRANCH:-master}
# Windows (PowerShell):
#   $ref = git -C "$env:OSDU_WORKSPACE\$REPO\.bare" symbolic-ref refs/remotes/origin/HEAD 2>$null
#   $DEFAULT_BRANCH = if ($ref) { ($ref -replace 'refs/remotes/origin/','') } else { 'master' }
cd "$OSDU_WORKSPACE/$REPO" && git worktree add "$DEFAULT_BRANCH" "$DEFAULT_BRANCH"
```

### Method 2: Standard git clone (when `wt` is not installed)

```bash
REPO="partition"
CLONE_URL="https://community.opengroup.org/osdu/platform/system/partition.git"

# Skip if already cloned
if [ -d "$OSDU_WORKSPACE/$REPO" ]; then
  echo "Skipping $REPO — already exists"
  continue
fi

git clone "$CLONE_URL" "$OSDU_WORKSPACE/$REPO"
```

## Post-Clone Verification

```bash
# For worktree layout
cd "$OSDU_WORKSPACE/$REPO/$DEFAULT_BRANCH" && git log --oneline -1

# For standard clone
cd "$OSDU_WORKSPACE/$REPO" && git log --oneline -1
```

Report: cloned count, skipped (already existed), failures.

## Working in Cloned Repos

**With worktrunk (`wt`):**
- `wt switch --create feature/xxx --base master` to create feature branches
- `wt step commit` to commit with LLM-generated messages
- `wt step diff` to see changes since branching

**Without worktrunk:**
- `git checkout -b feature/xxx` to create feature branches
- Standard git workflow for commits and diffs
