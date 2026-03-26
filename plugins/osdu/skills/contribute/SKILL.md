---
name: contribute
allowed-tools: Bash, Read, Glob, Grep
description: >-
  Push local changes into someone else's merge request by creating a sub-MR that
  targets their source branch. Handles fork creation, branch setup, commit, push,
  sub-MR creation, and drafts a comment on the parent MR.
  Use when the user wants to contribute to an existing MR, push changes into another
  developer's branch, or help fix something on someone else's MR.
  Not for: shipping your own work as a new MR (use send), or reviewing an MR without
  contributing code (use mr-review).
---

# Contribute: Push Changes Into an Existing MR

Ship local changes as a sub-MR that targets another developer's merge request branch. The goal
is to help move their MR forward without taking over their branch.

## When to Use

- You've cloned a repo and checked out someone else's MR branch
- You've made changes (tests, fixes, improvements) to help their MR
- You want to submit those changes as a separate MR targeting their source branch
- You want to notify the MR author with a comment on the parent MR

## Prerequisites

- `glab` authenticated to the target GitLab instance
- `git` with push access (direct or via fork)
- Local changes on a branch related to the target MR

## Phase 0: Context Detection

Determine what we're working with.

### Detect the Parent MR

The user should provide the parent MR number or URL. If not provided, try to infer:

```bash
# Check if current branch tracks an MR
CURRENT_BRANCH=$(git branch --show-current)
glab api "projects/<url-encoded-path>/merge_requests?source_branch=$CURRENT_BRANCH&state=opened" \
  --hostname community.opengroup.org
```

If the current branch IS the MR source branch, the user is working directly on it. They need
a new branch for their contribution:

```bash
git checkout -b <contribution-branch> <mr-source-branch>
```

### Verify Parent MR is Open

Before proceeding, confirm the parent MR is still open:

```bash
glab api "projects/<url-encoded-path>/merge_requests/<mr-number>" \
  --hostname community.opengroup.org
```

If the state is `merged` or `closed`, stop and tell the user.

### Derive Project Path

Extract the project path from the git remote for use with `--repo`:

```bash
PROJECT_PATH=$(git remote get-url origin | sed 's|.*community.opengroup.org[:/]||;s|\.git$||')
```

### Detect Push Access

```bash
# Try to determine if we can push directly or need a fork
git remote -v
```

If the remote is the upstream repo and the user doesn't have push access, they need a fork:

```bash
glab repo fork --remote --hostname community.opengroup.org
```

## Phase 1: Prepare Changes

### 1a. Review What's Changed

```bash
git --no-pager status --short
git --no-pager diff --stat
```

If there are no changes, stop. Nothing to contribute.

### 1b. Create a Branch

If not already on a contribution branch:

```bash
git checkout -b <contribution-branch-name> <mr-source-branch>
```

Branch naming: use a descriptive name that references the parent MR. Examples:
- `test/improve-core-plus-coverage` (for test additions)
- `fix/null-check-for-mr-845` (for a specific fix)

## Phase 2: Commit

Stage and commit the changes. Generate the commit message directly using conventional commit
format based on the staged changes.

```bash
git add <specific-files>
git commit -m "<generated conventional commit message>"
```

Follow the same commit rules as the `send` skill:
- One-line summary under 72 characters
- No Co-Authored-By trailers
- No AI attribution

## Phase 3: Push

Push to the appropriate remote (fork or direct):

```bash
git push -u origin <contribution-branch>
```

## Phase 4: Create Sub-MR

Create an MR that targets the parent MR's source branch, not the main/dev branch.

```bash
glab mr create \
  --source-branch <contribution-branch> \
  --target-branch <parent-mr-source-branch> \
  --repo <upstream-project-path> \
  --title "<commit-summary>" \
  --description "<brief description of what this adds and why>"
```

The description should be brief. One paragraph explaining what the changes do and how they
help the parent MR. No templates, no headers, no ceremony.

## Phase 5: Draft Parent MR Comment

Draft a comment for the parent MR that tells the author what you submitted and why.
**Do NOT post automatically.** Show the draft to the user first.

### Comment Guidelines

Follow the tone rules in `skills/mr-review/references/comment-tone.md`:

- Short, direct, developer voice
- No em dashes
- No filler or praise
- State what you did and why, that's it

**Good example:**
> The `core_code_coverage` job fails at 78% (threshold 80%). Your new code is fully covered,
> the gap is pre-existing untested classes. I've submitted !850 with tests for the three
> cache delegation wrappers to bring coverage above the threshold.

**Bad example:**
> Hey! Great MR — I noticed that the coverage gate is failing, so I've taken the liberty of
> submitting some additional tests that should help bring the coverage up. Hope this helps!

### Posting

Only after user approval:

```bash
glab mr note <parent-mr-number> \
  --repo <project-path> \
  -m "<approved comment text>"
```

## Context-Aware Routing

**Note:** The "ship it" disambiguation lives in the `send` skill's Phase 0. When a user says
"ship it" on someone else's MR branch, `send` detects this and redirects to `contribute`.
This skill does not need to handle that routing itself.

### After Contributing

- Offer to run `mr-review` on the parent MR if the user hasn't already reviewed it
- If the parent MR has pipeline failures the contribution addresses, mention that in the
  drafted comment

## Error Handling

| Error | Action |
|-------|--------|
| No push access | Fork the repo, push to fork, create cross-fork MR |
| Parent MR is closed/merged | Stop. Tell the user the MR is no longer open. |
| Contribution branch already has an MR | Report the existing MR URL, skip creation |
| glab not authenticated | Draft the comment but tell the user to post manually |
