# OSDU CLI Tools — Shared Reference

Common reference for the `osdu-activity`, `osdu-quality`, and `osdu-engagement` CLI tools.

## Installation

Install using `uv` (recommended):

```bash
uv tool install osdu-activity --index-url https://community.opengroup.org/api/v4/projects/1629/packages/pypi/simple
uv tool install osdu-quality --index-url https://community.opengroup.org/api/v4/projects/1630/packages/pypi/simple
uv tool install osdu-engagement --index-url https://community.opengroup.org/api/v4/projects/1631/packages/pypi/simple
```

Verify: `osdu-activity --version && osdu-quality --version && osdu-engagement --version`

Update: Each CLI has a built-in `update` command (e.g., `osdu-activity update`).

## Authentication

All three CLIs authenticate in the same order:
1. `--token` command-line option
2. `GITLAB_TOKEN` environment variable
3. `glab` CLI authentication (if installed)

**Token Requirements:** `read_api` scope minimum. For full access: `read_api`, `read_repository`.

## Output Formats

| Format | When to Use |
|--------|-------------|
| `markdown` | **Default for AI agents.** Optimized for LLM consumption, reduced token usage. |
| `json` | When you need raw data for programmatic filtering or field extraction. |
| `tty` | **Never use from agents.** ANSI escape codes break parsing. |

**Rule:** Always pass `--output markdown` (or `--output json` for raw data). Never use `--output tty` or omit the flag (default is tty).

## Project Names

Projects can be specified by:
- Short name: `partition`, `storage`, `search-service`
- Full path: `osdu/platform/system/partition`
- Fuzzy matching: `part` matches `partition`
- Multiple: `--project partition,storage,indexer` (comma-separated)

## Cloud Providers

Valid provider values: `azure`, `aws`, `gcp`, `ibm`, `cimpl` (Venus), `core` (shared tests).

## Common Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Missing/expired token | `export GITLAB_TOKEN=glpat-xxx` or `glab auth login --hostname community.opengroup.org` |
| `403 Forbidden` | Token lacks project access | Verify membership in GitLab web UI |
| `404 Project Not Found` | Wrong project name | Use short name with fuzzy matching (e.g., `--project partition`) |
| `429 Too Many Requests` | Rate limit hit | Reduce scope (`--project X`), wait 60s, or ensure token is set (authed requests get higher limits) |
| ANSI codes in output | Using tty format | Pass `--output markdown` or `--output json` |
| Slow response | Scanning all 30+ projects | Filter with `--project`, reduce `--pipelines`/`--limit`/`--days` |
| `command not found` | Not installed | Use the `setup` skill to install missing dependencies |

## Skill Boundaries

Each CLI has a distinct domain. Use the right tool:

| Question | Tool |
|----------|------|
| Open MRs, pipeline status, failed jobs, issues | `osdu-activity` |
| Test pass rates, flaky tests, test reliability | `osdu-quality` |
| Contributor rankings, review patterns, ADR engagement | `osdu-engagement` |
| GitLab CLI operations on a single repo | `glab` (not these tools) |
