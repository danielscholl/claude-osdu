---
name: send
allowed-tools: Bash, Read, Glob, Grep
description: >-
  Ship local changes through a review-commit-push workflow. Performs a lite code
  review, runs quality checks, commits with a conventional commit message, pushes
  to remote, and creates a merge request (GitLab) or pull request (GitHub).
  Auto-detects the remote platform and available tools (worktrunk, aipr).
  Use when the user wants to send, ship, submit, or push their work, create an MR
  or PR, or says "send it", "ship it", "push my changes", or "I'm done, send this up".
  Not for: reviewing someone else's MR (use mr-review), contributing to another
  developer's MR (use contribute), or setting up tools (use setup).
---

# Send: Review, Commit, Push, and Merge/Pull Request

A workflow that takes local changes from working directory to merge/pull request. Each phase gates
the next -- if something fails, stop and report rather than pushing broken code upstream.

**IMPORTANT:** All `git` commands in this skill MUST use `--no-pager` to prevent interactive
paging from hanging the shell.

## Argument Handling

Parse `$ARGUMENTS` (appended at the bottom of this skill) to extract the user's **intent**.

- **No arguments**: Proceed normally -- auto-generate everything.
- **Arguments provided** (e.g., `feat: add repo argument support to prime command`):
  Store as `INTENT` and use it throughout:
  - **Branch name** (Phase 0d): derive a slug from the intent
  - **Commit message** (Phase 3): use as the commit subject if it follows conventional
    commit format (`type: description` or `type(scope): description`), otherwise use it
    as input to the commit tool
  - **PR/MR title** (Phase 5): use as the title

**Deriving a branch slug from intent:**
Strip conventional commit prefix if present (`feat: `, `fix(scope): `, etc.), lowercase,
replace spaces and special characters with hyphens, collapse consecutive hyphens, truncate
to 50 characters, strip leading/trailing hyphens.

Example: `feat: add repo argument support to prime command` → `add-repo-argument-support-to-prime`

## Prerequisites

- `git` -- version control
- **Remote CLI** (auto-detected from remote URL):
  - GitLab remotes (`opengroup.org`, `gitlab`): requires `glab`
  - GitHub remotes (`github.com`): requires `gh`
- **Optional** (graceful degradation if absent):
  - `wt` ([worktrunk](https://worktrunk.dev)) -- worktree-based branching and commits
  - `aipr` -- AI-powered commit message generation

**Sandbox note:** In bare repo worktree layouts (`.bare/` directory), branch creation writes
to `.bare/refs/heads/`. This may require sandbox write access to the repo's `.bare/` path.

## Phase 0: Preflight

### 0a. Check for changes (bail early if nothing to send)

```bash
git --no-pager status --short
```

If clean, also check for unpushed commits:
```bash
git --no-pager log --oneline @{upstream}..HEAD 2>/dev/null
```

If both are clean, **STOP** -- nothing to send. If there are unpushed commits but no local
changes, skip to Phase 4 (Push).

### 0b. Detect environment

Run these checks. The results gate all later phases.

**Remote platform:**
```bash
REMOTE_URL=$(git remote get-url origin 2>/dev/null)
if echo "$REMOTE_URL" | grep -q "github\.com"; then
  PLATFORM=github
elif echo "$REMOTE_URL" | grep -qE "opengroup\.org|gitlab"; then
  PLATFORM=gitlab
else
  PLATFORM=unknown
fi
```

**Bare repo / worktree layout:**
```bash
IS_BARE_WORKTREE=false
if [ -f .git ]; then
  IS_BARE_WORKTREE=true
fi
```

This matters for branch naming -- bare repos cannot use slashes in branch names because
they create subdirectories under `.bare/refs/heads/` which may conflict or fail.

**Worktree tool:**
```bash
if command -v wt >/dev/null 2>&1 || command -v git-wt >/dev/null 2>&1; then
  HAS_WT=true
else
  HAS_WT=false
fi
```

**Commit tool** (prefer `wt step commit` > `aipr` > manual):
```bash
if [ "$HAS_WT" = true ]; then
  COMMIT_TOOL=wt
elif command -v aipr >/dev/null 2>&1; then
  COMMIT_TOOL=aipr
else
  COMMIT_TOOL=manual
fi
```

### 0c. Get the current branch

```bash
git branch --show-current
```

### 0d. Branch safety

**Branch naming rules** (gated by `IS_BARE_WORKTREE`):
- `IS_BARE_WORKTREE=true`: use **flat names** with hyphens (e.g., `add-repo-argument-support`)
- `IS_BARE_WORKTREE=false`: use **slashed names** (e.g., `feature/add-repo-argument-support`)

**On `main` or `master`:**
These are release branches -- changes must go on a feature branch.

If `INTENT` is available (from ARGUMENTS), auto-derive a branch name from the slug and
create the branch without asking the user:

```bash
# Example for bare worktree with INTENT slug "add-repo-argument-support"
git checkout -b add-repo-argument-support
# Example for standard clone
git checkout -b feature/add-repo-argument-support
```

If no INTENT, ask the user for a feature name, then create the branch.

**On `dev`:**
The user is on the integration branch -- cannot merge from `dev` to `dev`. Same logic as
above: auto-derive from INTENT if available, otherwise ask.

When using `wt` for branch creation:
```bash
# wt always uses flat names for worktree directory names
wt switch --create <slug> --base dev
```
> This changes the working directory to a new worktree path. All subsequent
> commands run from the new directory.

**On `feature/*` or any other name:** proceed normally.

### 0e. Contribution check -- am I on someone else's branch?

**GitLab:**
```bash
glab api "projects/:id/merge_requests?source_branch=$(git branch --show-current)&state=opened" \
  --hostname community.opengroup.org 2>/dev/null
```

**GitHub:**
```bash
gh pr list --head "$(git branch --show-current)" --state open --json number,author 2>/dev/null
```

If an open MR/PR exists and the author is not the current user, ask: "You're on the
`<branch>` branch from MR/PR #X by `<author>`. Do you want to contribute these changes
to that MR/PR, or create a separate one?" If they want to contribute, hand off to the
`contribute` skill.

## Phase 1: Lite Code Review

A quick sanity check -- catch obvious problems before they become review comments.

1. View the full diff:
   ```bash
   git --no-pager diff --stat
   git --no-pager diff
   ```
2. Scan the changes for:
   - Hardcoded secrets, credentials, API keys, `.env` files
   - Files that should not be committed: binaries, `.tfstate`, `.env`, credential files
   - Obvious bugs or logic errors
3. Present a brief review summary listing changed files and any concerns.
4. If there are blocking concerns (secrets, dangerous files), **STOP** and ask the user to fix
   them before continuing.

## Phase 2: Quality Checks

Run checks based on which file types changed -- skip checks that don't apply. Only run a
check if the relevant tool is available.

- **Terraform** (`.tf` files changed):
  ```bash
  terraform fmt -check -recursive ./infra 2>/dev/null
  terraform fmt -check -recursive ./platform 2>/dev/null
  ```
- **YAML** (`.yaml` or `.yml` files changed):
  ```bash
  git --no-pager diff --name-only --diff-filter=ACM -- '*.yaml' '*.yml' | xargs -I{} python3 -c "import yaml, sys; yaml.safe_load(open(sys.argv[1]))" {}
  ```
- **JSON** (`.json` files changed):
  ```bash
  git --no-pager diff --name-only --diff-filter=ACM -- '*.json' | xargs -I{} python3 -c "import json, sys; json.load(open(sys.argv[1]))" {}
  ```
- **Python** (`.py` files changed) -- syntax check only:
  ```bash
  git --no-pager diff --name-only --diff-filter=ACM -- '*.py' | xargs -I{} python3 -m py_compile {}
  ```
- **Java** (`pom.xml` exists and `.java` files changed) -- compile check only:
  ```bash
  mvn compile -q 2>/dev/null
  ```

If any check fails, **STOP** and report. Do not proceed to commit.

## Phase 3: Commit

Stage changes and create a conventional commit. The method depends on which tools
are available (detected in Phase 0b). If INTENT is available and already follows
conventional commit format, prefer using it as the commit message rather than
auto-generating -- the user told you what this change is.

### Option A: `wt step commit` (if `HAS_WT=true`)

worktrunk handles staging, diff analysis, and message generation:
```bash
wt step commit
```
Review the generated message -- if it doesn't follow the commit rules below, amend.

**If `wt step commit` fails** (non-zero exit), fall through to Option B or C. Don't stop
the workflow because of a tool failure when alternatives exist.

### Option B: `aipr commit -s` (if `aipr` is available)

```bash
git add -A
git commit -m "$(aipr commit -s)"
```

### Option C: Manual commit (fallback)

```bash
git add -A
```

If INTENT is available and matches conventional commit format (`type: ...` or
`type(scope): ...`), use it directly as the commit message. Otherwise, generate
the message from the staged diff using the
[Commit Prompt Reference](references/commit-prompt.md).

```bash
git commit -m "<message>"
```

### Commit rules -- hard requirements (apply to ALL options)

- **One-line summary** under 72 characters: `type(scope): description`
- Types: feat fix docs refactor chore ci style test build perf
- Use imperative mood (add, implement, fix -- not adds, added, adding)
- Add 1-2 detail lines only for large changes (15+ files). Max 3 lines total.
- **NEVER** add `Co-Authored-By` trailers -- not for any AI or agent
- **NEVER** add "Generated with", "Built by", or any agent/AI attribution
- **NEVER** add `Signed-off-by` unless the user explicitly requests DCO sign-off

## Phase 4: Push

Push the branch to the remote:
```bash
git push -u origin $(git branch --show-current)
```

## Phase 5: Merge / Pull Request

### 5a. Check for an existing MR/PR

**GitLab:**
```bash
glab mr list --source-branch="$(git branch --show-current)"
```

**GitHub:**
```bash
gh pr list --head "$(git branch --show-current)" --state open
```

If one already exists, report its URL and skip creation.

### 5b. Determine the target branch

Default target: `dev` (OSDU convention). If no `dev` branch exists on the remote, fall
back to `main` or `master`:
```bash
git --no-pager ls-remote --heads origin dev main master 2>/dev/null
```
Use the first branch that exists, in order: `dev`, `main`, `master`.

### 5c. Determine the title

If INTENT is available and follows conventional commit format, use it as the title.
Otherwise, derive from the most recent commit (or summarize if multiple commits):
```bash
TITLE=$(git --no-pager log -1 --format='%s')
```

### 5d. Generate the description

Analyze the commit log and diff stats to produce a description:
```bash
DIFF_STATS=$(git --no-pager diff --stat origin/$TARGET_BRANCH..HEAD)
COMMITS=$(git --no-pager log origin/$TARGET_BRANCH..HEAD --format='%s%n%b')
```

Use the [MR Description Prompt Reference](references/mr-description-prompt.md) as a guide
for the description structure. When INTENT is available, incorporate the user's stated
purpose into the Summary section as the "why" -- don't just describe the diff mechanically.

### 5e. Create the MR/PR

**GitLab:**
```bash
ASSIGNEE=$(glab auth status 2>&1 | grep 'Logged in' | sed 's/.* as \([^ ]*\).*/\1/')
glab mr create \
  --title "$TITLE" \
  --description "$BODY" \
  --target-branch "$TARGET_BRANCH" \
  --assignee "$ASSIGNEE" \
  --remove-source-branch
```

**GitHub:**
```bash
gh pr create \
  --title "$TITLE" \
  --body "$BODY" \
  --base "$TARGET_BRANCH"
```

### 5f. Report the MR/PR URL to the user.

## Final Summary

After all phases complete, present a compact summary:

```
Review:  <clean or list of concerns addressed>
Commit:  <short-hash> <commit message>
Branch:  <branch-name> -> pushed to origin
MR/PR:   <URL>
```
