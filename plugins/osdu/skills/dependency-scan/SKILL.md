---
name: dependency-scan
allowed-tools: Bash, Read, Write, Glob, Grep
description: >-
  Analyze project dependencies for available updates, overlay CVE data, and create
  an actionable risk-scored remediation report. Supports Maven projects with Python
  and Node.js planned.
  Use when the user asks to scan dependencies, check for vulnerabilities, generate a
  dependency report, or says "what needs updating".
  Not for: applying dependency updates (use remediate), or general project build
  issues (use build-runner).
---

# OSDU Dependency Analysis Workflow

Comprehensive dependency management: analyze ALL project dependencies for available updates, overlay CVE data, and create an actionable risk-scored report.

## Critical Rules

- This is DEPENDENCY MANAGEMENT with CVE awareness — show ALL dependencies, not just vulnerable ones
- AI DOES THE THINKING — scripts provide verified data, you provide intelligence and context
- ALL version recommendations MUST come from script output (Maven Central), never from training data
- Use ABSOLUTE PATHS for all script invocations and report output
- Calculate RISK SCORE for each update using the risk framework

## Tools

| Tool | Location | Purpose |
|------|----------|---------|
| check.py | `skills/maven/scripts/check.py` | Maven Central version checking |
| scan.py | `skills/maven/scripts/scan.py` | Trivy CVE scanning |
| report.py | `skills/dependency-scan/scripts/report.py` | Data aggregation for CI/automation |

## Execution Steps

### Step 0: Resolve Paths
Compute WORKSPACE_ROOT, PROJECT_PATH, REPORT_PATH before any work.
- WORKSPACE_ROOT = directory containing the plugin skills
- PROJECT_PATH = absolute path to project being analyzed
- REPORT_PATH depends on whether the brain vault exists:
  - **Brain exists** (`$OSDU_BRAIN/04-reports/` present): `$OSDU_BRAIN/04-reports/dependencies/dependencies-{project-name}-{YYYYMMDD}.md`
  - **No brain**: `{CWD}/dependencies-{project-name}-{YYYYMMDD}.md` (workspace directory)

### Step 1: Project Discovery
Read pom.xml to understand structure: groupId, artifactId, version, packaging, BOMs, modules.

### Step 2: Version Check
```bash
uv run {WORKSPACE_ROOT}/skills/maven/scripts/check.py pom \
  --path {PROJECT_PATH} --include-managed --json
```

### Step 3: Vulnerability Scan
```bash
uv run {WORKSPACE_ROOT}/skills/maven/scripts/scan.py scan \
  --path {PROJECT_PATH} --compact --json
```

### Step 4: Version Lookup for CVEs
For key CVE packages not in version_properties:
```bash
uv run {WORKSPACE_ROOT}/skills/maven/scripts/check.py check \
  -d {groupId}:{artifactId} -v {version} --json
```

### Step 5: AI Intelligence
- Identify deprecated/EOL packages
- Assess breaking changes for major updates
- Apply risk framework (Category + Jump + CVE + Location)

### Step 6: Write Report
Organize by UPDATE RISK LEVEL (LOW/MEDIUM/HIGH), not CVE severity.

## Risk Scoring

Sum modifiers: LOW (0-1), MEDIUM (2-3), HIGH (4+)

| Factor | Values |
|--------|--------|
| Category | Framework(+2), Serial/Net/DB/Security/Cloud(+1), Utility/Testing(0) |
| Jump | Patch(0), Minor(+1), Major(+3) |
| CVE | CRITICAL(-1), HIGH/MEDIUM/LOW(0), None(+1) |
| Fix Location | Direct(0), Temporary override(+1) |

See `reference/risk-framework.md` for complete details.

## Data Aggregation (JSON only)

For CI/automation, use report.py to aggregate data:
```bash
uv run {WORKSPACE_ROOT}/skills/dependency-scan/scripts/report.py \
  {project-path} \
  --json
```

**Note:** report.py provides JSON data aggregation. For rich markdown reports, use this skill which applies AI intelligence.

## Report Structure

**CRITICAL**: Organize reports by **update risk level**, NOT by CVE severity.

### Input → Output Transformation

| Input (from Trivy) | Output (in report) |
|-------------------|-------------------|
| CVE Severity (CRITICAL/HIGH/MEDIUM/LOW) | Update Risk (LOW/MEDIUM/HIGH) |
| "How dangerous is this vulnerability?" | "How safe is this fix to apply?" |

### Required Output Sections

```
## Updates by Risk Level

### LOW Risk (Score 0-1)
[Batch apply - list updates with score breakdown]

### MEDIUM Risk (Score 2-3)
[Individual commits - list updates with score breakdown]

### HIGH Risk (Score 4+)
[Research first - list updates with score breakdown]

## For /remediate Command
[Machine-readable tables grouped by risk level]
```

### Examples

- CRITICAL CVE + patch fix = **LOW** risk update (urgent AND safe)
- No CVE + major framework bump = **HIGH** risk update (not urgent, potentially breaking)

**Anti-pattern**: Do NOT organize sections by CVE severity (Critical Vulnerabilities, High Vulnerabilities, etc.). Users need to know what's safe to fix first, not what's most dangerous.

## Multi-Repo Awareness

When run in a multi-repo workspace, the workflow should:
1. Identify which project to analyze (from user input or current directory)
2. Check if shared libraries (os-core-common, os-core-lib-azure) are also cloned
3. Note upstream dependency relationships between workspace repos
4. Flag when a dependency fix in a shared library would cascade to downstream services
