---
name: remediate
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
description: >-
  Execute dependency remediation from an analysis report with validation,
  risk-tiered commits, and code fixes. Applies updates incrementally with
  build verification after each change.
  Use when the user has a dependency analysis report and wants to apply the
  recommended updates, or says "remediate", "fix dependencies", "apply updates".
  Not for: scanning dependencies (use dependency-scan), or general code fixes
  unrelated to dependency versions.
---

# OSDU Remediation Workflow

Execute a dependency remediation plan from an analysis report, applying updates incrementally with validation after each change.

## Risk Tiers

| Tier | Score | Strategy | Commits |
|------|-------|----------|---------|
| LOW | 0-1 | Batch together | Single commit |
| MEDIUM | 2-3 | Individual | One commit per update |
| HIGH | 4+ | Research first | One commit per update |

## Options

| Flag | Description |
|------|-------------|
| `--low` | Apply LOW risk updates only (default) |
| `--medium` | Apply LOW + MEDIUM risk updates |
| `--high` | Apply LOW + MEDIUM + HIGH risk updates |
| `--all` | Same as --high |
| `--dry-run` | Show what would be applied without changes |

## Execution Phases

### Phase 0: Parse Arguments
Extract report file path and flags.

### Phase 1: Parse Report
Read the "For /remediate Command" section. Extract updates by risk level with package, from-version, to-version, CVE, fix-location.

### Phase 1.5: Version Verification (CRITICAL)
Before applying any update, verify target versions exist in Maven Central:
```bash
uv run skills/maven/scripts/check.py check \
  -d {groupId}:{artifactId} -v {current-version} --json
```

### Phase 2: Preparation
1. Check clean git status
2. Checkout main/master, pull latest
3. **Validate baseline** — spawn build-runner sub-agent:
   ```
   Read charter: agents/build-runner.agent.md
   Task: Validate {project} using javatest.py --validate
   ```
4. Create remediation branch: `agent/dep-remediation-{YYYYMMDD}`

### Phase 3: LOW Risk Updates (Batch)
1. Apply all verified LOW risk updates to pom.xml
2. Spawn build-runner to validate
3. On success → single commit: `chore(deps): apply low-risk security updates`
4. On failure → bisect, skip problematic update

### Phase 4: MEDIUM Risk Updates (One-by-One)
**Each update gets its own cycle: Apply → Build → Test → Commit → Next**
1. Apply ONE update
2. Spawn build-runner to compile
3. Spawn build-runner to test
4. On success → commit: `chore(deps): update <package> to <version>`
5. On failure → analyze, fix if localized, or skip

### Phase 5: HIGH Risk Updates (Research First)
1. Research breaking changes
2. Apply update
3. Fix compilation iteratively
4. Fix tests
5. Commit with BREAKING CHANGE footer if needed

### Phase 6: Final Validation
Spawn build-runner to validate full build. Compare to baseline.

### Phase 7: Generate Summary
Report applied, skipped, deferred updates with commit hashes.

### Phase 8: Update Report File
Append remediation results to the original report.

## Multi-Repo Considerations

In a multi-repo workspace:
1. Identify which project the report targets
2. If updating a shared library (os-core-common), note downstream impact
3. After remediating a shared library, suggest running baseline builds on dependent services
4. Track cross-repo dependency chains: library → service builds

## Commit Convention

```
chore(deps): description

[optional body with CVE references]
```
