# OSDU Activity CLI Reference

Complete command reference for the `osdu-activity` CLI tool.

## Global Options

```
--version, -v    Show version and exit
--help           Show help and exit
```

## Commands

### osdu-activity mr

Show merge request report. Displays open merge requests with pipeline status across OSDU projects.

```
Usage: osdu-activity mr [OPTIONS]

Options:
  --project, -p TEXT         Project(s) to analyze (comma-separated, fuzzy match)
  --provider TEXT            Filter jobs by provider: azure, aws, gcp, ibm, core. Default: all
  --milestone, -m TEXT       Filter by milestone (fuzzy match supported)
  --state [opened|merged|closed|all]  MR state filter [default: opened]
  --user, -u TEXT            Filter by any user involvement (author, assignee, or reviewer)
  --author TEXT              Filter by MR author username
  --assignee TEXT            Filter by MR assignee username
  --reviewer TEXT            Filter by MR reviewer username
  --style, -s [table|list]   Display style: table (summary) or list (detailed) [default: table]
  --output, -o [tty|json|markdown]  Output format [default: tty]
  --output-dir TEXT          Directory for file output
  --token TEXT               GitLab access token [env var: GITLAB_TOKEN]
  --include-draft            Include draft/WIP merge requests
  --show-jobs, -j            Show failed job details (list style only)
  --limit, -l INTEGER        Maximum items per project [default: 20]
  --help                     Show this message and exit
```

**Examples:**

```bash
# All open MRs (table view)
osdu-activity mr --output json

# Single project
osdu-activity mr --project partition --output json

# Multiple projects
osdu-activity mr --project partition,storage,search --output json

# Detailed list with failed jobs
osdu-activity mr --style list --show-jobs --output json

# Include draft MRs
osdu-activity mr --include-draft --output json

# Azure provider only
osdu-activity mr --provider azure --output json

# Save markdown report
osdu-activity mr --output markdown --output-dir ./reports

# Filter by milestone (release triage)
osdu-activity mr --milestone M26 --output json

# All MRs for milestone (open, merged, closed)
osdu-activity mr --milestone M26 --state all --output json

# Merged MRs only
osdu-activity mr --state merged --output json

# Filter by author
osdu-activity mr --author johndoe --output json

# Filter by any user involvement
osdu-activity mr --user johndoe --output json

# Combine milestone and user filters
osdu-activity mr --milestone M26 --author johndoe --output json
```

**JSON Output Structure:**

```json
{
  "generated_at": "2025-01-14T10:00:00Z",
  "total_mrs": 45,
  "projects": [
    {
      "name": "partition",
      "path": "osdu/platform/system/partition",
      "mrs": [
        {
          "iid": 123,
          "title": "Add new feature",
          "author": "username",
          "created_at": "2025-01-10T08:00:00Z",
          "updated_at": "2025-01-13T15:00:00Z",
          "web_url": "https://community.opengroup.org/...",
          "pipeline_status": "success",
          "draft": false,
          "labels": ["enhancement"],
          "failed_jobs": []
        }
      ]
    }
  ]
}
```

---

### osdu-activity pipeline

Show pipeline report. Displays pipeline status across OSDU projects.

```
Usage: osdu-activity pipeline [OPTIONS]

Options:
  --project, -p TEXT         Project(s) to analyze (comma-separated, fuzzy match)
  --provider TEXT            Filter jobs by provider: azure, aws, gcp, ibm, core. Default: all
  --style, -s [table|list]   Display style: table (summary) or list (detailed) [default: table]
  --output, -o [tty|json|markdown]  Output format [default: tty]
  --output-dir TEXT          Directory for file output
  --token TEXT               GitLab access token [env var: GITLAB_TOKEN]
  --include-draft            Include pipelines from draft/WIP merge requests
  --limit, -l INTEGER        Maximum items per project [default: 20]
  --help                     Show this message and exit
```

**Examples:**

```bash
# All pipeline status
osdu-activity pipeline --output json

# Single project detailed
osdu-activity pipeline --project storage --style list --output json

# Azure pipelines only
osdu-activity pipeline --provider azure --output json

# Include draft MR pipelines
osdu-activity pipeline --include-draft --output json
```

**JSON Output Structure:**

```json
{
  "generated_at": "2025-01-14T10:00:00Z",
  "summary": {
    "total": 150,
    "success": 120,
    "failed": 20,
    "running": 5,
    "pending": 5
  },
  "projects": [
    {
      "name": "partition",
      "path": "osdu/platform/system/partition",
      "pipelines": [
        {
          "id": 340289,
          "ref": "master",
          "status": "success",
          "created_at": "2025-01-14T09:00:00Z",
          "web_url": "https://community.opengroup.org/...",
          "failed_jobs": []
        }
      ]
    }
  ]
}
```

---

### osdu-activity issue

Show issue report. Displays open issues across OSDU projects.

```
Usage: osdu-activity issue [OPTIONS]

Options:
  --project, -p TEXT         Project(s) to analyze (comma-separated, fuzzy match)
  --provider TEXT            Filter jobs by provider: azure, aws, gcp, ibm, core. Default: all
  --style, -s [table|list]   Display style: table (summary) or list (detailed) [default: table]
  --output, -o [tty|json|markdown]  Output format [default: tty]
  --output-dir TEXT          Directory for file output
  --token TEXT               GitLab access token [env var: GITLAB_TOKEN]
  --limit, -l INTEGER        Maximum items per project [default: 50]
  --adr                      Show only ADR (Architecture Decision Record) issues
  --help                     Show this message and exit
```

**Examples:**

```bash
# All open issues
osdu-activity issue --output json

# ADR issues only
osdu-activity issue --adr --output json

# Single project issues
osdu-activity issue --project storage --output json

# Detailed list view
osdu-activity issue --style list --output json
```

**JSON Output Structure:**

```json
{
  "generated_at": "2025-01-14T10:00:00Z",
  "total_issues": 87,
  "projects": [
    {
      "name": "partition",
      "path": "osdu/platform/system/partition",
      "issues": [
        {
          "iid": 45,
          "title": "Bug in authentication",
          "author": "username",
          "created_at": "2025-01-05T10:00:00Z",
          "updated_at": "2025-01-12T14:00:00Z",
          "web_url": "https://community.opengroup.org/...",
          "labels": ["bug", "priority::high"],
          "assignees": ["developer1"]
        }
      ]
    }
  ]
}
```

---

### osdu-activity update

Check for and install updates from GitLab Package Registry. Auto-detects installation method (uv vs pipx).

```
Usage: osdu-activity update [OPTIONS]

Options:
  --check-only       Only check for updates, don't install
  --force            Force reinstall even if up to date
  --show-changelog   Display changelog for new version [default: enabled]
  --no-changelog     Skip changelog display
  --token TEXT       GitLab access token [env var: GITLAB_TOKEN]
  --help             Show this message and exit
```

**Examples:**

```bash
# Check if update available
osdu-activity update --check-only

# Update to latest
osdu-activity update

# Force reinstall
osdu-activity update --force
```

---

For authentication, output formats, project names, and provider values, see the
[shared CLI reference](../../../reference/osdu-cli-reference.md).

## Display Styles

| Style | Description |
|-------|-------------|
| `table` | Summary view with counts and status (default) |
| `list` | Detailed view with individual items |

Use `--style list` with `--show-jobs` to see failed job details.

## Filtering Tips

**Combine filters for targeted analysis:**
```bash
osdu-activity mr --project partition --provider azure --output json
```

**Use fuzzy matching for convenience:**
```bash
osdu-activity mr --project idx  # Matches indexer-service, indexer-queue
```

**Draft MRs are excluded by default** - use `--include-draft` to include them.

## Milestone Filtering

Filter MRs by GitLab milestone for release triage:

**Fuzzy matching:** The `--milestone` flag supports fuzzy matching:
- `--milestone M26` matches "M26", "Milestone 26", "m26"
- `--milestone 26` matches any milestone containing "26"

**State combinations:**

| Scenario | Command |
|----------|---------|
| Open MRs for release | `osdu-activity mr --milestone M26` |
| All MRs for release | `osdu-activity mr --milestone M26 --state all` |
| Merged for release | `osdu-activity mr --milestone M26 --state merged` |
| Closed (abandoned) | `osdu-activity mr --milestone M26 --state closed` |

**Release triage workflow:**
```bash
# What's still open for the release
osdu-activity mr --milestone M26 --output json

# Full picture including merged
osdu-activity mr --milestone M26 --state all --output json

# Identify stale MRs (check created_at in JSON output)
osdu-activity mr --milestone M26 --output json
# Look for created_at > 30 days ago with no recent updated_at
```

**JSON output includes:**
- `milestone` field with milestone name
- `created_at` / `updated_at` for staleness detection
- `labels` for additional categorization

## User Filtering

Filter MRs by user involvement:

| Filter | Matches |
|--------|---------|
| `--user johndoe` | MRs where user is author, assignee, OR reviewer |
| `--author johndoe` | MRs authored by user |
| `--assignee johndoe` | MRs assigned to user |
| `--reviewer johndoe` | MRs where user is a reviewer |

**Use case examples:**

```bash
# What's on my plate? (any involvement)
osdu-activity mr --user myusername --output json

# What did I author?
osdu-activity mr --author myusername --output json

# What am I reviewing?
osdu-activity mr --reviewer myusername --output json

# What's assigned to me?
osdu-activity mr --assignee myusername --output json
```

**Combining filters:**
```bash
# MRs by author for a milestone
osdu-activity mr --milestone M26 --author johndoe --output json

# User's MRs on a specific project
osdu-activity mr --project partition --user johndoe --output json
```
