# OSDU Quality CLI Reference

Complete command reference for the `osdu-quality` CLI tool.

## Global Options

```
--version, -v    Show version and exit
--help, -h       Show help and exit
```

## Commands

### osdu-quality analyze

Multi-project quality analysis. Analyzes test reliability across multiple pipelines, detects flaky tests, calculates pass rates, and provides cloud provider metrics.

```
Usage: osdu-quality analyze [OPTIONS]

Options:
  --pipelines INTEGER    Number of pipelines to analyze per project [default: 10]
  --project TEXT         Specific project(s) to analyze (comma-separated)
  --output TEXT          Output format: tty (terminal), json, markdown [default: tty]
  --output-dir TEXT      Directory to save markdown reports
  --token TEXT           GitLab token (or use GITLAB_TOKEN env var, or glab auth)
  --stage TEXT           Filter by stage (unit, integration, acceptance)
  --provider TEXT        Filter by cloud provider (azure, aws, gcp, ibm, cimpl, core)
  --help, -h             Show this message and exit
```

**Examples:**

```bash
# Analyze all projects
osdu-quality analyze --output json

# Single project deep dive
osdu-quality analyze --project partition --output json

# Multiple projects
osdu-quality analyze --project partition,storage,search-service --output json

# Filter by stage
osdu-quality analyze --stage integration --output json

# Filter by provider
osdu-quality analyze --provider azure --output json

# Combined filters
osdu-quality analyze --project partition --stage unit --provider azure --output json

# More pipeline history
osdu-quality analyze --pipelines 20 --output json

# Save markdown report
osdu-quality analyze --output markdown --output-dir ./reports
```

**JSON Output Structure:**

```json
{
  "summary": {
    "total_projects": 30,
    "total_pipelines": 300,
    "overall_pass_rate": 85.2,
    "flaky_test_count": 12
  },
  "projects": [
    {
      "name": "partition",
      "path": "osdu/platform/system/partition",
      "pass_rate": 92.5,
      "pipelines_analyzed": 10,
      "stages": {
        "unit": { "pass_rate": 100, "total": 50 },
        "integration": { "pass_rate": 85, "total": 20 },
        "acceptance": { "pass_rate": 60, "total": 10 }
      },
      "providers": {
        "azure": { "pass_rate": 95 },
        "aws": { "pass_rate": 88 }
      },
      "flaky_tests": ["TestClassName.testMethod"]
    }
  ]
}
```

---

### osdu-quality status

Latest test status by stage. Generate comprehensive status reports showing latest test results by stage (unit/integration/acceptance), version information, and issue counts.

```
Usage: osdu-quality status [OPTIONS]

Options:
  --pipelines INTEGER    Number of pipelines to analyze per project [default: 10]
  --project TEXT         Specific project(s) to analyze (comma-separated)
  --output TEXT          Output format: tty (terminal), json, markdown [default: tty]
  --output-dir TEXT      Directory to save markdown reports
  --token TEXT           GitLab token (or use GITLAB_TOKEN env var, or glab auth)
  --venus / --no-venus   Show only CIMPL (Venus) provider jobs [default: no-venus]
  --no-release           Skip release tag rows (show only master/main branch)
  --help, -h             Show this message and exit
```

**Examples:**

```bash
# Status for all projects
osdu-quality status --output json

# Single project status
osdu-quality status --project partition --output json

# Venus/CIMPL provider only
osdu-quality status --venus --output json

# Main branch only (skip releases)
osdu-quality status --no-release --output json
```

**JSON Output Structure:**

```json
{
  "generated_at": "2025-01-14T10:00:00Z",
  "projects": [
    {
      "name": "partition",
      "version": "0.28.0",
      "branch": "master",
      "unit_tests": {
        "status": "passed",
        "pass_rate": 100,
        "passed": 150,
        "failed": 0,
        "skipped": 5
      },
      "integration_tests": {
        "status": "passed",
        "pass_rate": 95,
        "passed": 38,
        "failed": 2,
        "skipped": 0
      },
      "acceptance_tests": {
        "status": "failed",
        "pass_rate": 60,
        "passed": 6,
        "failed": 4,
        "skipped": 0
      },
      "open_issues": 3
    }
  ]
}
```

---

### osdu-quality tests

Analyze detailed test results from pipeline jobs. Parses job logs to show individual test class results, pass/fail counts, and specific failure details.

```
Usage: osdu-quality tests [OPTIONS]

Options:
  --project, -p TEXT     Project to analyze (required). Use project name or path.
  --pipeline INTEGER     Specific pipeline ID. Defaults to latest master pipeline.
  --output, -o TEXT      Output format: tty, json, or markdown. [default: tty]
  --output-dir TEXT      Directory for file output (json/markdown).
  --token TEXT           GitLab token (or set GITLAB_TOKEN env var).
  --help, -h             Show this message and exit
```

**Examples:**

```bash
# Latest pipeline test details
osdu-quality tests --project partition --output json

# Specific pipeline
osdu-quality tests --project partition --pipeline 340289 --output json

# Save output
osdu-quality tests --project storage --output json --output-dir ./reports
```

**JSON Output Structure:**

```json
{
  "project": "partition",
  "pipeline_id": 340289,
  "pipeline_ref": "master",
  "jobs": [
    {
      "name": "unit-test-azure",
      "stage": "unit",
      "status": "passed",
      "tests": [
        {
          "class": "com.osdu.partition.PartitionServiceTest",
          "passed": 25,
          "failed": 0,
          "skipped": 2,
          "failures": []
        }
      ]
    }
  ],
  "summary": {
    "total_passed": 150,
    "total_failed": 3,
    "total_skipped": 10,
    "pass_rate": 98.0
  }
}
```

---

### osdu-quality update

Check for and install updates from GitLab Package Registry.

```
Usage: osdu-quality update [OPTIONS]

Options:
  --check-only    Only check for updates, don't install
  --help          Show this message and exit
```

---

For authentication, output formats, project names, and provider values, see the
[shared CLI reference](../../../reference/osdu-cli-reference.md).

## Stages

Valid stage values:
- `unit` - Unit tests (fast, isolated)
- `integration` - Integration tests (component interaction)
- `acceptance` - Acceptance/E2E tests (full system)
