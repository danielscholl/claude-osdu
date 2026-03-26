# Dependency Report Format

This document describes the structure and format of dependency analysis reports.

## File Naming

Reports are saved to the `reports/` directory with the following naming convention:

```
reports/dependencies-{project-name}-{YYYYMMDD}.md
```

Example: `reports/dependencies-partition-20251204.md`

## Report Structure

### Summary Section

```markdown
# Dependency Analysis: {Project Name}

## Summary
- **Analyzed**: {date}
- **Project**: {name} v{version}
- **Type**: Library | Service
- **Location**: {path}
```

### Security Vulnerabilities Section

```markdown
## Security Vulnerabilities

| Severity | Count |
|----------|-------|
| CRITICAL | {n}   |
| HIGH     | {n}   |
| MEDIUM   | {n}   |

### Critical CVEs (Immediate Action Required)
[If CRITICAL CVEs exist]

| CVE | Package | Current | Fix Version | Description |
|-----|---------|---------|-------------|-------------|

### High Severity CVEs (Plan for Current Sprint)
[If HIGH CVEs exist]

| CVE | Package | Current | Fix Version |
|-----|---------|---------|-------------|

### Medium Severity CVEs (Maintenance Backlog)
[If MEDIUM CVEs exist]

| CVE | Package | Current | Fix Version |
|-----|---------|---------|-------------|
```

If no vulnerabilities are found:
```markdown
No known vulnerabilities detected.
```

### Dependency Updates Section

```markdown
## Dependency Updates (Non-CVE)

### Patch Updates (Low Risk)
Safe to apply immediately.

| Package | Current | Update To | Notes |
|---------|---------|-----------|-------|

### Minor Updates (Medium Risk)
Review changelog before applying.

| Package | Current | Update To | Notable Changes |
|---------|---------|-----------|-----------------|

### Major Updates (High Risk)
Requires planning and potential code changes.

| Package | Current | Latest | Breaking Changes |
|---------|---------|--------|------------------|

### Pre-release to Stable
Currently using milestone/pre-release versions.

| Package | Current | Stable Version |
|---------|---------|----------------|
```

### Recommendations Section

```markdown
## Recommendations

### Phase 1: Immediate (Low Risk)
- {patch updates and CVE fixes}

### Phase 2: Short-term (Medium Risk)
- {minor version updates}

### Phase 3: Planned (High Risk)
- {major version upgrades with notes}
```

### Testing Section

```markdown
## Testing
```bash
# Validate changes
mvn clean verify  # for Maven
npm test          # for Node
pytest            # for Python
```
```

## JSON Output Format

When using `--json` flag, the report is output as JSON:

```json
{
  "status": "success",
  "result": {
    "project_name": "partition",
    "project_version": "1.0.0",
    "project_type": "maven",
    "project_path": "/path/to/project",
    "analyzed_at": "2025-12-04T10:30:00",
    "severity_counts": {
      "critical": 1,
      "high": 2,
      "medium": 3,
      "low": 0
    },
    "total_vulnerabilities": 6,
    "total_updates": 12,
    "vulnerabilities": [
      {
        "cve_id": "CVE-2024-1234",
        "severity": "critical",
        "package_name": "org.springframework:spring-core",
        "installed_version": "5.3.0",
        "fixed_version": "5.3.32",
        "description": "..."
      }
    ],
    "updates": [
      {
        "package_name": "org.springframework:spring-core",
        "current_version": "5.3.0",
        "latest_version": "5.3.32",
        "bump_type": "patch",
        "risk_level": "low",
        "has_cve": true,
        "cve_ids": ["CVE-2024-1234"]
      }
    ]
  }
}
```

## Output Locations

- **Markdown reports**: `reports/dependencies-*.md`
- **JSON output**: stdout when using `--json` flag

## Usage Examples

```bash
# Generate markdown report (default)
uv run report.py /path/to/project

# Generate JSON output
uv run report.py /path/to/project --json

# Custom output directory
uv run report.py /path/to/project --output /custom/reports/

# Current directory
uv run report.py .
```
