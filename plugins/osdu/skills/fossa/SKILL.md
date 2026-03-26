---
name: fossa
allowed-tools: Bash, Read, Write
description: >-
  Fix FOSSA NOTICE file from failed MR pipeline. Downloads the updated NOTICE artifact from a GitLab CI fossa-check-notice job and commits it.
  Use when the user mentions FOSSA failure, NOTICE file update, fossa-check-notice job failure, or needs to fix a FOSSA pipeline error.
  Not for: license scanning setup, dependency vulnerability analysis (use maven scan), or general pipeline debugging (use glab).
---

# OSDU FOSSA Fix Workflow

Fix the FOSSA NOTICE file when the `fossa-check-notice` job fails in a GitLab MR pipeline.

## Execution Steps

### Step 1: Determine MR Number
If provided, use it. Otherwise detect from current branch:
```bash
git branch --show-current
glab mr list --source-branch=$(git branch --show-current) --state=opened
```
> **Windows (PowerShell):** Use `$branch = git branch --show-current` then `glab mr list --source-branch=$branch --state=opened`

### Step 2: Get Project ID
```bash
glab api projects/:fullpath | grep -o '"id":[0-9]*' | head -1
```
> **Windows (PowerShell):** `glab api projects/:fullpath | ConvertFrom-Json | Select-Object -ExpandProperty id`

### Step 3: Get MR Pipelines
```bash
glab api projects/<project-id>/merge_requests/<mr-number>/pipelines
```
Find pipeline with `source: "merge_request_event"` (parent pipeline).

### Step 4: Find Child Pipeline ID
Get the `trigger-trusted-tests` job trace and parse the child pipeline ID:
```bash
glab api projects/<project-id>/jobs/<trigger-job-id>/trace
```

### Step 5: Check fossa-check-notice Job
```bash
glab api "projects/<project-id>/pipelines/<child-pipeline-id>/jobs?per_page=100"
```
- If `status: "success"` → Report "FOSSA check passed, no action needed"
- If `status: "failed"` → Continue

### Step 6: Extract NOTICE URL from Job Log
Search for the wget command containing the NOTICE URL in the job trace.

### Step 7: Download Updated NOTICE
```bash
glab api "projects/<project-id>/jobs/<fossa-analyze-job-id>/artifacts/fossa-output/generated-clean-NOTICE" > NOTICE
```

### Step 8: Verify and Commit
```bash
git add NOTICE
git commit -m "chore(fossa): update NOTICE file"
```

### Step 9: Push Changes
```bash
git push origin <branch-name>
```

## Multi-Repo Context

In a multi-repo workspace, this workflow operates on whichever repo the user specifies or the current working directory. The agent should:
1. Identify which service repo to operate on
2. `cd` into that repo before executing
3. Ensure the correct GitLab remote is being used

## Error Handling

| Scenario | Action |
|----------|--------|
| No MR found for branch | Report error, ask user to provide MR number |
| Pipeline not found | Report error with MR URL |
| fossa-check-notice passed | Report success, no action needed |
| No wget URL in log | Report error, show relevant log section |
| Download fails | Report error with URL for manual download |
| Empty NOTICE file | Report error, do not commit |
