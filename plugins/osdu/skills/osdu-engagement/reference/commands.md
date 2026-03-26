# OSDU Engagement CLI Reference

Complete command reference for the `osdu-engagement` CLI tool.

## Global Options

```
--version, -v    Show version and exit
--help, -h       Show help and exit
```

## Commands

### osdu-engagement contribution

Analyze code contributions across OSDU projects. Measures merge requests, commits, reviews, and participation.

```
Usage: osdu-engagement contribution [OPTIONS] COMMAND [ARGS]...

Options:
  --days, -d INTEGER     Number of days to analyze (default: 30) [default: 30]
  --start-date TEXT      Start date for analysis (YYYY-MM-DD). Overrides --days
  --end-date TEXT        End date for analysis (YYYY-MM-DD). Defaults to today
  --project, -p TEXT     Filter to specific project (fuzzy matching)
  --output, -o TEXT      Output format: tty, json, or markdown [default: tty]
  --output-dir TEXT      Directory for file output
  --token TEXT           GitLab token (or set GITLAB_TOKEN env var)
  --verbose              Show detailed progress
  --help, -h             Show this message and exit

Commands:
  trend    Historical contribution trend analysis
```

**Examples:**

```bash
# Last 30 days (default)
osdu-engagement contribution --output json

# Custom time period
osdu-engagement contribution --days 90 --output json

# Specific date range
osdu-engagement contribution --start-date 2025-01-01 --end-date 2025-01-14 --output json

# Single project
osdu-engagement contribution --project partition --output json

# Save markdown report
osdu-engagement contribution --output markdown --output-dir ./reports
```

**JSON Output Structure:**

```json
{
  "period": {
    "start": "2024-12-15",
    "end": "2025-01-14",
    "days": 30
  },
  "summary": {
    "total_contributors": 45,
    "total_merge_requests": 120,
    "total_commits": 350,
    "total_reviews": 280,
    "projects_with_activity": 25
  },
  "contributors": [
    {
      "username": "developer1",
      "name": "Developer Name",
      "merge_requests": 15,
      "commits": 45,
      "reviews": 22,
      "comments": 38,
      "projects": ["partition", "storage", "search"]
    }
  ],
  "projects": [
    {
      "name": "partition",
      "merge_requests": 8,
      "contributors": 5,
      "top_contributor": "developer1"
    }
  ]
}
```

---

### osdu-engagement contribution trend

Historical contribution trend analysis. Shows activity patterns over months.

```
Usage: osdu-engagement contribution trend [OPTIONS]

Options:
  --months INTEGER       Number of months to analyze
  --output, -o TEXT      Output format: tty, json, or markdown [default: tty]
  --output-dir TEXT      Directory for file output
  --help, -h             Show this message and exit
```

**Examples:**

```bash
# Default trend
osdu-engagement contribution trend --output json

# 6-month trend
osdu-engagement contribution trend --months 6 --output json

# 12-month trend
osdu-engagement contribution trend --months 12 --output json
```

**JSON Output Structure:**

```json
{
  "months": [
    {
      "month": "2025-01",
      "merge_requests": 45,
      "contributors": 20,
      "commits": 120
    },
    {
      "month": "2024-12",
      "merge_requests": 52,
      "contributors": 22,
      "commits": 145
    }
  ],
  "trend": {
    "direction": "stable",
    "change_percent": -2.5
  }
}
```

---

### osdu-engagement decision

Analyze Architecture Decision Record (ADR) engagement. Shows ADR activity and participation.

```
Usage: osdu-engagement decision [OPTIONS] COMMAND [ARGS]...

Options:
  --days, -d INTEGER     Filter to ADRs with activity in last N days.
                         Without this, shows all current ADRs.
  --start-date TEXT      Start date for filtering (YYYY-MM-DD)
  --end-date TEXT        End date for filtering (YYYY-MM-DD)
  --project, -p TEXT     Filter to specific project (fuzzy matching)
  --output, -o TEXT      Output format: tty, json, or markdown [default: tty]
  --output-dir TEXT      Directory for file output
  --token TEXT           GitLab token (or set GITLAB_TOKEN env var)
  --verbose              Show detailed progress
  --help, -h             Show this message and exit
```

**Examples:**

```bash
# All current ADRs
osdu-engagement decision --output json

# ADRs with recent activity (last 30 days)
osdu-engagement decision --days 30 --output json

# Project-specific ADRs
osdu-engagement decision --project core-lib-azure --output json

# Date range filter
osdu-engagement decision --start-date 2025-01-01 --output json
```

**JSON Output Structure:**

```json
{
  "generated_at": "2025-01-14T10:00:00Z",
  "total_adrs": 15,
  "adrs": [
    {
      "id": 123,
      "title": "ADR-001: Use event sourcing for audit",
      "project": "partition",
      "status": "proposed",
      "created_at": "2025-01-05T10:00:00Z",
      "updated_at": "2025-01-12T15:00:00Z",
      "author": "architect1",
      "participants": ["developer1", "developer2", "reviewer1"],
      "comments_count": 8,
      "web_url": "https://community.opengroup.org/..."
    }
  ],
  "summary": {
    "proposed": 5,
    "accepted": 8,
    "deprecated": 2,
    "active_discussions": 3
  }
}
```

---

### osdu-engagement update

Check for and install updates from GitLab Package Registry.

```
Usage: osdu-engagement update [OPTIONS]

Options:
  --check-only    Only check for updates, don't install
  --help          Show this message and exit
```

---

For authentication, output formats, project names, and provider values, see the
[shared CLI reference](../../../reference/osdu-cli-reference.md).

## Date Filtering

**Using --days:**
```bash
osdu-engagement contribution --days 30  # Last 30 days from today
osdu-engagement contribution --days 90  # Last 90 days from today
```

**Using date range:**
```bash
osdu-engagement contribution --start-date 2025-01-01 --end-date 2025-01-14
```

**Note:** `--start-date` overrides `--days` if both are provided.

## Metrics Explained

**Merge Requests:**
- Count of MRs created by contributor
- Indicates feature/fix contribution

**Commits:**
- Number of commits authored
- Measures code change volume

**Reviews:**
- Number of MRs reviewed
- Indicates code review participation

**Comments:**
- Discussion participation
- Shows engagement in reviews

## ADR Status Values

| Status | Meaning |
|--------|---------|
| `proposed` | Under discussion, not yet accepted |
| `accepted` | Approved and being implemented |
| `deprecated` | No longer relevant or superseded |
| `rejected` | Not accepted (rare) |
