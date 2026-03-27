---
name: clone
allowed-tools: Bash, Read
description: >-
  Clone OSDU GitLab repositories and infrastructure repos to the workspace. Supports single service, category, or all repos with bare-clone worktree or standard git clone.
  Use when the user asks to clone an OSDU repo, set up the workspace, download source code for a service, or clone infrastructure repos.
  Not for: building or testing cloned repos (use maven or acceptance-test), or checking repo status (use glab or osdu-activity).
---

# OSDU Clone Workflow

Clone repositories into the OSDU workspace using a step-by-step procedure.
Follow these steps in order — each step depends on the previous one.

## Step 1: Resolve workspace path

```bash
OSDU_WORKSPACE="${OSDU_WORKSPACE:-$(pwd)}"
```

## Step 2: Detect clone method

Run this check before any clone operation. The result determines which clone
procedure to use for every repo in this session.

```bash
if command -v wt &>/dev/null || command -v git-wt &>/dev/null; then
  USE_WORKTREE=true
else
  USE_WORKTREE=false
fi
echo "USE_WORKTREE=$USE_WORKTREE"
```

The `wt` tool (worktrunk) manages bare-clone worktree layouts. When it is
installed, the user expects the worktree layout — using a plain `git clone`
in that situation is wrong because it creates a repo structure that `wt`
cannot manage. So the detection result is not a suggestion; it is a gate
that selects the clone procedure.

## Step 3: Resolve which repos to clone

### Categories

| Category | Repos |
|----------|-------|
| infra | cimpl-azure-provisioning |
| libraries | os-core-common, os-core-lib-azure |
| core | partition, entitlements, legal, secret, schema-service, storage, file, indexer-service, indexer-queue, search-service, dataset, register, notification |
| reference | crs-catalog-service, crs-conversion-service, unit-service |
| ingestion | ingestion-workflow |
| domain | wellbore-domain-services, seismic-store-service |

### Parsing algorithm

1. **Explicit prefix:**
   - `service:<name>` → clone that single service
   - `category:<name>` → clone all repos in that category
   - `all` → clone everything

2. **No prefix — apply precedence:**
   - **FIRST**: exact repo name match → clone that single repo
   - **SECOND**: category name match → clone all in category
   - **OTHERWISE**: report error "Unknown repo or category"

Repo names take precedence over categories.

### URL construction

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

## Step 4: Clone each repo

For each repo, first check if it already exists:

```bash
if [ -d "$OSDU_WORKSPACE/$REPO" ]; then
  echo "Skipping $REPO — already exists"
  # continue to next repo
fi
```

Then branch on the detection result from Step 2.

### If USE_WORKTREE=true (bare clone + worktree)

This creates the layout that `wt` expects: a `.bare` directory holding the
bare repo, a `.git` file pointing at it, and a worktree for the default branch.

```bash
REPO="partition"
CLONE_URL="https://community.opengroup.org/osdu/platform/system/partition.git"

# 1. Bare clone into .bare
mkdir -p "$OSDU_WORKSPACE/$REPO"
git clone --bare "$CLONE_URL" "$OSDU_WORKSPACE/$REPO/.bare"

# 2. Point .git at the bare repo so git/wt commands work from $REPO/
echo "gitdir: ./.bare" > "$OSDU_WORKSPACE/$REPO/.git"

# 3. Configure fetch refspec (bare clones don't track remotes by default)
git -C "$OSDU_WORKSPACE/$REPO/.bare" config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
git -C "$OSDU_WORKSPACE/$REPO/.bare" fetch origin

# 4. Detect default branch and create worktree
DEFAULT_BRANCH=$(git -C "$OSDU_WORKSPACE/$REPO/.bare" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||')
DEFAULT_BRANCH=${DEFAULT_BRANCH:-master}
cd "$OSDU_WORKSPACE/$REPO" && git worktree add "$DEFAULT_BRANCH" "$DEFAULT_BRANCH"
```

**Resulting layout:**
```
$OSDU_WORKSPACE/partition/
├── .bare/        # bare clone
├── .git          # file: "gitdir: ./.bare"
└── master/       # default worktree (working directory)
```

### If USE_WORKTREE=false (standard clone)

```bash
REPO="partition"
CLONE_URL="https://community.opengroup.org/osdu/platform/system/partition.git"

git clone "$CLONE_URL" "$OSDU_WORKSPACE/$REPO"
```

## Step 5: Verify

```bash
# Worktree layout — working directory is under $DEFAULT_BRANCH/
cd "$OSDU_WORKSPACE/$REPO/$DEFAULT_BRANCH" && git log --oneline -1

# Standard layout — working directory is $REPO/ itself
cd "$OSDU_WORKSPACE/$REPO" && git log --oneline -1
```

Report: cloned count, skipped (already existed), failures.

## Working in Cloned Repos

**With worktrunk (`wt`):**
- `wt switch --create feature/xxx --base master` — create feature branch worktree
- `wt step commit` — commit with LLM-generated messages
- `wt step diff` — see changes since branching

**Without worktrunk:**
- `git checkout -b feature/xxx` — create feature branch
- Standard git workflow
