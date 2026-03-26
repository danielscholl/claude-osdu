---
name: send
allowed-tools: Bash, Read, Glob, Grep
description: >-
  Ship local changes through a review-commit-push-MR workflow using git and glab.
  Performs a lite code review, runs quality checks, commits with a conventional commit
  message, pushes to remote, and creates a GitLab merge request.
  Use when the user wants to send, ship, submit, or push their work, create an MR,
  or says "send it", "ship it", "push my changes", or "I'm done, send this up".
  Not for: reviewing someone else's MR (use mr-review), contributing to another
  developer's MR (use contribute), or setting up tools (use setup).
---

# Send: Review, Commit, Push, and Merge Request

A workflow that takes local changes from working directory to merge request. Each phase gates the
next — if something fails, stop and report rather than pushing broken code upstream.

**IMPORTANT:** All `git` commands in this skill MUST use `--no-pager` to prevent interactive
paging from hanging the shell.

## Prerequisites

- `git` — version control
- `glab` — GitLab CLI (authenticated with the target remote)

## Phase 0: Preflight

1. Get the current branch:
   ```bash
   git branch --show-current
   ```
2. **Branch safety:**
   - `main` or `master`: **STOP**. These are release branches. The user needs to
     create a feature branch from `dev`.
   - `dev`: The user is on the integration branch. They cannot MR from `dev` → `dev`. **Ask
     the user** for a feature name, then create a feature branch:
     ```bash
     git checkout -b feature/<user-provided-name>
     ```
     Continue the workflow on the new branch.
   - `feature/*` or any other name: proceed normally.
3. **Contribution check — am I on someone else's MR branch?**
   Check if the current branch has an open MR where you are NOT the author:
   ```bash
   glab api "projects/:id/merge_requests?source_branch=$(git branch --show-current)&state=opened" \
     --hostname community.opengroup.org 2>/dev/null
   ```
   If an open MR exists and the author is not the current user, the user may intend to
   contribute to that MR rather than create a new one. Ask: "You're on the `<branch>` branch
   from MR !X by `<author>`. Do you want to contribute these changes to that MR, or create
   a separate MR?" If they want to contribute, hand off to the `contribute` skill.
4. Check for changes:
   ```bash
   git --no-pager status --short
   ```
   If clean, also check for unpushed commits:
   ```bash
   git --no-pager log --oneline @{upstream}..HEAD 2>/dev/null
   ```
   If both are clean, **STOP** — nothing to send. If there are unpushed commits but no local
   changes, skip to Phase 4 (Push).

## Phase 1: Lite Code Review

A quick sanity check — catch obvious problems before they become MR comments.

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

Run checks based on which file types changed — skip checks that don't apply.

- **Terraform** (`.tf` files changed):
  ```bash
  terraform fmt -check -recursive ./infra 2>/dev/null
  terraform fmt -check -recursive ./platform 2>/dev/null
  ```
- **YAML** (`.yaml` or `.yml` files changed):
  ```bash
  git --no-pager diff --name-only --diff-filter=ACM -- '*.yaml' '*.yml' | xargs -I{} python3 -c "import yaml, sys; yaml.safe_load(open(sys.argv[1]))" {}
  ```

If any check fails, **STOP** and report. Do not proceed to commit.

## Phase 3: Commit

Stage changes and generate a conventional commit message directly.

```bash
git add -A
```

Generate the commit message directly using conventional commit format based on the staged diff. Analyze the changes and produce a message following these rules:

**Commit rules — these are hard requirements:**
- **One-line summary** under 72 characters: `type(scope): description`
- Types: feat fix docs refactor chore ci style test build perf
- Use imperative mood (add, implement, fix — not adds, added, adding)
- Add 1-2 detail lines only for large changes (15+ files). Max 3 lines total.
- **NEVER** add `Co-Authored-By` trailers — not for any AI or agent
- **NEVER** add "Generated with", "Built by", or any agent/AI attribution
- **NEVER** add `Signed-off-by` unless the user explicitly requests DCO sign-off

```bash
git commit -m "<generated message>"
```

## Phase 4: Push

Push the branch to the remote:
```bash
git push -u origin $(git branch --show-current)
```

## Phase 5: Merge Request

1. Check for an existing MR:
   ```bash
   glab mr list --source-branch="$(git branch --show-current)"
   ```
2. If an MR already exists, report its URL and skip creation.
3. Get the current GitLab username for assignment:
   ```bash
   ASSIGNEE=$(glab auth status 2>&1 | grep 'Logged in' | sed 's/.* as \([^ ]*\).*/\1/')
   ```
4. Determine the MR title from the most recent commit (or summarize if multiple commits):
   ```bash
   TITLE=$(git --no-pager log -1 --format='%s')
   ```
5. Generate the MR description directly. Analyze the commit log and diff stats to produce a
   description that explains the *why*, not just the *what*:
   ```bash
   DIFF_STATS=$(git --no-pager diff --stat origin/dev..HEAD)
   COMMITS=$(git --no-pager log origin/dev..HEAD --format='%s%n%b')
   ```
   Use the [MR Description Prompt Reference](references/mr-description-prompt.md) as a guide
   for the description structure. Generate the description text directly based on the commit
   log and diff stats.
6. Create the MR, assigning the current user:
   ```bash
   glab mr create \
     --title "$TITLE" \
     --description "$BODY" \
     --target-branch dev \
     --assignee "$ASSIGNEE" \
     --remove-source-branch
   ```
7. Report the MR URL to the user.

## Final Summary

After all phases complete, present a compact summary:

```
Review:  <clean or list of concerns addressed>
Commit:  <short-hash> <commit message>
Branch:  <branch-name> → pushed to origin
MR:      <MR URL>
```
