---
name: mr-review
allowed-tools: Bash, Read, Glob, Grep
description: >-
  Review a GitLab merge request with code analysis and pipeline diagnostics.
  Fetches the diff, analyzes changes by risk area, checks pipeline status,
  classifies job failures, and produces a structured verdict.
  Use when the user says "review MR", "look at this MR", "is this safe to merge",
  "check the pipeline for MR X", or pastes a GitLab MR URL without other instruction.
  Not for: shipping your own changes (use send), contributing to someone else's MR
  (use contribute), or syncing trusted branches (use maintainer).
---

# MR Review: Code Analysis + Pipeline Diagnostics

Review a GitLab merge request end to end. The output is a structured assessment that covers both
what the code does and whether the pipeline is healthy enough to merge.

## Input Parsing

Accept any of:
- Full GitLab URL: `https://community.opengroup.org/osdu/platform/system/search-service/-/merge_requests/845`
- Short reference: `search-service MR 845`, `search !845`
- MR number alone: `845`, `!845` (requires current repo context or prior context)

### URL Parsing

From `https://community.opengroup.org/osdu/platform/system/search-service/-/merge_requests/845`:
- Host: `community.opengroup.org`
- Project path: `osdu/platform/system/search-service`
- MR number: `845`

**CRITICAL:** `glab` defaults to gitlab.com. For OSDU, ALL `glab api` commands MUST use:
```bash
GITLAB_HOST=community.opengroup.org glab api ...
```

Or use `--hostname community.opengroup.org` if supported by the subcommand.

## Prerequisites

- `glab` authenticated to the target GitLab instance
- If glab is not authenticated, fall back to web fetch for public repos

## Phase 1: Fetch MR Context

Gather everything needed before analysis. Run these in parallel where possible.

### 1a. MR Metadata

```bash
glab api "projects/<url-encoded-path>/merge_requests/<mr-number>" \
  --hostname community.opengroup.org
```

Extract: title, author, description, source branch, target branch, labels, milestone, state.

### 1b. Diff

```bash
glab api "projects/<url-encoded-path>/merge_requests/<mr-number>/changes?access_raw_diffs=true" \
  --hostname community.opengroup.org
```

If the diff is too large for a single API call, use the `.diff` endpoint:

```bash
# Via web fetch as fallback
https://<host>/<project-path>/-/merge_requests/<number>.diff
```

### 1c. Pipeline Status

```bash
glab api "projects/<url-encoded-path>/merge_requests/<mr-number>/pipelines" \
  --hostname community.opengroup.org
```

Take the most recent pipeline and fetch its jobs:

```bash
glab api "projects/<url-encoded-path>/pipelines/<pipeline-id>/jobs?per_page=100" \
  --hostname community.opengroup.org
```

**Child/downstream pipelines** (common in OSDU trusted-tests pattern): Look for jobs where
the stage is `trigger` or the job name contains `trigger-trusted`. These bridge jobs have a
`downstream_pipeline` object in the JSON response containing the child pipeline ID. Fetch
the child pipeline's jobs using that ID. The real test results are usually in the child
pipeline, not the parent.

## Phase 2: Code Analysis

Analyze the diff with these goals:

### Change Categorization

Group changes into areas:

| Area | Patterns |
|------|----------|
| Dependencies | pom.xml, package.json, go.mod, requirements.txt, NOTICE |
| CI/CD | .gitlab-ci.yml, Dockerfile, Makefile |
| Source (core) | Main application code |
| Source (provider) | Provider-specific implementations (azure/, aws/, gcp/, ibm/) |
| Tests | src/test/**, tests/**, *_test.go, *.test.js |
| API/Contract | OpenAPI specs, Swagger config, REST endpoints |
| Docs | *.md, docs/** |
| Config | application.properties, *.yaml config files |

### Code Review Checklist

Scan for:
- Security: hardcoded secrets, credential handling, injection vectors
- Behavioral changes: null handling differences, exception type changes, new error paths
- API contract: header changes, endpoint modifications, response shape changes
- Cross-provider consistency: if one provider is changed, are others updated where needed
- Test coverage: are new code paths tested, are test assertions meaningful

### Summary

Write a concise summary of what the MR does and why. Lead with the problem being solved,
then describe the approach. Keep it to 3-5 sentences max.

## Phase 3: Pipeline Diagnostics

This is the differentiator. For each failed job in the pipeline:

### 3a. Get Job Logs

```bash
glab api "projects/<url-encoded-path>/jobs/<job-id>/trace" \
  --hostname community.opengroup.org
```

Read the last 80 lines to find the failure reason. If the tail only shows cascading failures
(e.g., "BUILD FAILURE" with no root cause), search upward for the first error. Look for patterns
like `ERROR`, `FAILED`, `Exception`, `error:`, or test assertion failures.

### 3b. Classify Each Failure

Categorize every failed job:

| Classification | Meaning | Examples |
|----------------|---------|---------|
| **MR-caused** | Directly caused by changes in this MR | Test failures from new code, coverage drop, compile errors |
| **Pre-existing** | Failure exists on the target branch too | Flaky tests, coverage already below threshold |
| **Environment** | Infrastructure or environment issue | DNS failures, cluster unreachable, service timeouts |
| **Transient** | One-time failure, likely passes on retry | Network blips, resource contention |

**How to classify:**
- **MR-caused**: The failure message references files or logic changed in the MR, or a metric
  (like coverage) dropped because of newly added code.
- **Pre-existing**: Check the target branch's latest pipeline. If the same job fails with the
  same error there, it is pre-existing.
- **Environment**: The error is about infrastructure (DNS, cluster connectivity, service timeouts,
  certificate errors) not about the code being tested.
- **Transient**: Similar to environment but the error pattern is intermittent (resource contention,
  network blip). If the same job passed in a previous pipeline run on the same branch, it is
  likely transient.

For MR-caused failures, explain what specifically in the MR triggered them and what the fix
would look like.

### 3c. Pipeline Summary Table

```
Pipeline #XXXXX: <status>

| Job                    | Status  | Classification | Details                    |
|------------------------|---------|----------------|----------------------------|
| compile                | passed  |                |                            |
| unit-tests             | passed  |                |                            |
| core_code_coverage     | failed  | MR-caused      | 78% vs 80% threshold       |
| azure-acceptance-test  | failed  | Environment    | 400s on record ingestion   |
| ibm-deploy             | failed  | Environment    | DNS resolution failure     |
```

### 3d. Blockers vs Non-Blockers

Clearly separate:
- **Blockers**: failures the MR author needs to fix before merge
- **Non-blockers**: failures unrelated to the MR (environment, pre-existing, transient)

## Phase 4: Verdict

Provide a clear recommendation:

| Verdict | When |
|---------|------|
| **Approve** | Code is sound, no MR-caused pipeline failures |
| **Approve with notes** | Code is sound, minor items worth mentioning but not blocking |
| **Needs work** | MR-caused issues that require changes (coverage, test failures, bugs) |
| **Blocked** | Serious issues (security, breaking changes, design problems) |

Include specific next actions for anything that isn't "approve."

## Phase 5: Draft Comment

Generate a comment for the MR. **Do NOT post it automatically.** Show the draft to the user
and wait for approval or edits.

### Comment Tone

The comment must read like a developer wrote it. Follow these rules strictly:

- Write short, direct sentences. No filler.
- Do not use em dashes as punctuation. Use periods or commas instead.
- Do not open with praise ("Great work!", "Nice MR!"). Just get into it.
- Do not use phrases like "It's worth noting", "I noticed that", "Just a thought".
- No excessive bullet lists when a short paragraph works fine.
- Technical, factual, concise. The kind of comment a senior developer leaves in a real review.
- If there's nothing meaningful to say, don't pad the comment. Shorter is better.

**Good example:**
> The cache fix looks correct. Each provider now resolves cluster settings by partition ID
> instead of pulling from request scope, which eliminates the poisoning vector.
>
> One pipeline blocker: `core_code_coverage` fails at 78% (threshold 80%). Your new code
> is fully covered, the gap is pre-existing untested classes. I've submitted !850 with tests
> for the three cache delegation wrappers to bring it above the threshold.

**Bad example:**
> Great work on this MR! I noticed that the changes look solid — the fix for the cache
> poisoning issue is well-implemented. It's worth noting that the pipeline has some failures,
> but most of them aren't caused by your changes. Here are my detailed findings:
> - The code changes are consistent across all providers
> - The test coverage is good
> - ...

### Comment Structure

For simple reviews: a short paragraph or two is fine.

For complex reviews with pipeline issues:
1. Brief assessment of the code (2-3 sentences)
2. Pipeline status with focus on blockers
3. Any specific action items or offers to help

## Fallback: No glab Auth

If glab is not authenticated for the target instance:

1. Use web fetch to get the MR page and diff (works for public OSDU repos)
2. Pipeline details may be limited. Note this in the output.
3. Posting comments requires glab auth. Draft the comment but tell the user they'll need
   to post it manually or authenticate glab first.

## Integration

After the review:
- If the user wants to contribute fixes, suggest the `contribute` skill
- If the user says "allow it" or "sync trusted", hand off to the `maintainer` skill
- If the user wants to store the review, offer the `brain` skill for vault storage

## Posting the Comment

Only when the user explicitly approves:

```bash
glab mr note <mr-number> \
  --repo <project-path> \
  -m "<approved comment text>"
```
