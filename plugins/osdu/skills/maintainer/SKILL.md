---
name: maintainer
allowed-tools: Bash, Read, Glob
description: >-
  Maintainer actions for MR trusted branch sync. Check sync status between source and trusted branches, then push to the trusted branch so the child pipeline can run.
  Use when the user says 'allow MR', 'sync trusted branch', 'trigger trusted tests', or asks to review and approve an MR for pipeline execution.
  Not for: code review or pipeline analysis (use mr-review), creating or merging MRs (use glab), or test reliability (use osdu-quality).
---

# OSDU Maintainer Workflow

Maintainer actions for GitLab MR pipelines. Review MRs and allow them to proceed by syncing the trusted branch.

## Background

Developers create MRs on regular branches. The child pipeline requires a "trusted" branch that only maintainers can create/sync. The `trigger-trusted-tests` job verifies the trusted branch SHA matches the source branch before allowing the child pipeline to run.

## Actions

| Action | Purpose | Default |
|--------|---------|---------|
| `review` | Analyze MR changes, show sync status, provide recommendation | Default |
| `allow` | Sync trusted branch and retry pipeline job | — |

## Input Parsing

- `review` or no action → review mode
- `allow` → allow mode
- MR number or full GitLab URL accepted
- Auto-detect from current branch if omitted

### URL Parsing
From `https://community.opengroup.org/osdu/platform/security-and-compliance/entitlements/-/merge_requests/904`:
- Host: `community.opengroup.org`
- Project path: `osdu/platform/security-and-compliance/entitlements`
- MR number: `904`

**CRITICAL:** `glab` defaults to gitlab.com. For OSDU, ALL `glab api` commands MUST use:
```bash
GITLAB_HOST=community.opengroup.org glab api ...
```

## Review Action

1. **Get MR Metadata** — title, author, labels, target branch
2. **Check Milestone & Labels** — flag missing milestone, suggest labels based on changed files
3. **Analyze Changes** — categorize by risk (Dependencies/CI-CD/Source/Tests/Docs/Secrets)
4. **Show Commit History** — check conventional commits
5. **Analyze Code Changes** — summarize modifications, purpose, impact
6. **Security Checks** — scan for hardcoded secrets, suspicious patterns
7. **Check Sync Status** — compare source branch SHA vs trusted branch SHA
8. **Provide Recommendation** — APPROVE / REVIEW NEEDED / CAUTION

### Label Suggestions

| Change Pattern | Suggested Label |
|----------------|-----------------|
| Common/shared code | `common` |
| Azure-specific paths | `Azure` |
| GCP-specific paths | `GCP` |
| AWS/IBM-specific paths | `AWS` / `IBM` |
| pom.xml, package.json | `dependencies` |
| .gitlab-ci.yml, Dockerfile | `ci/cd` |
| *.md, docs/** | `documentation` |

## Allow Action

1. Parse MR number or detect from branch
2. Derive trusted branch: `trusted-<source-branch>`
3. Sync: `git push origin <source-branch>:refs/heads/<trusted-branch> --force`
4. Retry `trigger-trusted-tests` job

## Multi-Repo Context

In a multi-repo workspace:
1. Determine which service repo the MR belongs to
2. If a local clone exists, use it for `git push` operations
3. If no local clone, use a temp clone for the sync
4. The project ID resolution uses the GitLab API with URL-encoded paths
