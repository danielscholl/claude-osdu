# OSDU Azure Environments

The OSDU platform uses three Azure environments in a progressive deployment pipeline. Each serves a distinct purpose in the software lifecycle.

## Environment Overview

```
Code → glab (CI/CD) → stg (Release Staging) → ship (QA / Preshipping)
       MR + merge       release branches        milestone validation
```

### glab — CI/CD Environment

The primary development environment. Every merge request and merge to master/main triggers CI/CD pipelines that deploy and test against this environment.

- **Purpose:** Continuous integration and delivery validation
- **Triggers:** MR pipelines, merges to master/main
- **GitLab:** https://community.opengroup.org
- **Who uses it:** Developers via CI/CD pipelines (automated)

### stg — Release Staging Environment

The release staging environment. When a pipeline runs from a release branch, it deploys into stg instead of glab. This is the intermediate step between development and full QA validation.

- **Purpose:** Release branch deployment and staging validation
- **Triggers:** Release branch pipelines (e.g., `release/0.29`)
- **Who uses it:** Release engineers, CI/CD pipelines from release branches

### ship — QA / Preshipping Environment

The full end-to-end QA validation environment. A release undergoes comprehensive testing here before shipping a milestone release. This is where the OSDU agent runs API tests, audits user access, and manages entitlements.

- **Purpose:** Full E2E validation before milestone release
- **Who uses it:** QA engineers, the OSDU agent, release validators
- **Configuration:** Requires `AI_OSDU_*` environment variables (see below)

## Workspace Configuration

These variables control where the plugin stores knowledge and clones repositories:

| Variable | Description | Default |
|----------|-------------|---------|
| `OSDU_BRAIN` | Path to the Obsidian knowledge vault | `~/.osdu-brain` |
| `OSDU_WORKSPACE` | Path to the OSDU service workspace | Current working directory |

Both are optional — the defaults work out of the box for skills and agents.

!!! note "OSDU extension requires OSDU_WORKSPACE"
    The OSDU extension runs as a separate process and cannot detect your working directory automatically. For the extension to auto-discover your azd environment, set `OSDU_WORKSPACE` in your shell profile:

    ```bash
    # Add to ~/.zshrc or ~/.bashrc
    export OSDU_WORKSPACE=~/source/cimpl/workspace  # your workspace path
    ```

    Without this, the OSDU extension tools (`health_check`, `search_query`, etc.) won't connect to your environment. Skills that use kubectl (like `health`) still work — only the extension-based API tools are affected.

## Agent Environment Variables

The OSDU agent's skills (azure-ad, azure-osdu, osdu-qa) interact with the **ship** environment via these variables:

| Variable | Description |
|----------|-------------|
| `AI_OSDU_HOST` | OSDU instance hostname |
| `AI_OSDU_DATA_PARTITION` | Data partition ID |
| `AI_OSDU_CLIENT` | Service principal app ID |
| `AI_OSDU_SECRET` | Service principal secret |
| `AI_OSDU_TENANT_ID` | Azure AD tenant ID |
| `AI_OSDU_DOMAIN` | Default email domain |

### How to Configure

1. **Get credentials** — Contact a tenant administrator for the service principal client ID, secret, and tenant ID. These come from an Azure App Registration.

2. **Set environment variables** — The `AI_OSDU_*` variables must be available in your shell. How you persist them depends on your platform:

   - **macOS/Linux:** Add exports to your shell profile (`~/.zshenv`, `~/.bashrc`, etc.)
   - **Windows:** Use System Environment Variables, or a `.env` file with your tooling

   The agent can help you determine the best approach for your platform — just ask.

   ```
   AI_OSDU_HOST=<host>
   AI_OSDU_DATA_PARTITION=<partition>
   AI_OSDU_CLIENT=<client-id>
   AI_OSDU_SECRET=<client-secret>
   AI_OSDU_TENANT_ID=<tenant-id>
   ```

3. **Verify** — Run the check command:

   ```bash
   uv run skills/azure-ad/scripts/invite.py check
   ```

### Additional Prerequisites

| Tool | Purpose | Install |
|------|---------|---------|
| `az` CLI | Azure AD queries, Graph API | [Install Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) then `az login` |
| `uv` | Python script runner | [Install uv](https://docs.astral.sh/uv/getting-started/installation/) |
| `glab` | GitLab CLI for pipeline/MR operations | [Install glab](https://gitlab.com/gitlab-org/cli#installation) then `glab auth login` |
| `GITLAB_TOKEN` | GitLab API access | Personal access token from community.opengroup.org |

### QA Test Environments (osdu-qa skill)

The osdu-qa skill supports multiple test targets beyond ship:

| Target | Platform | Partition | Description |
|--------|----------|-----------|-------------|
| `azure/ship` | Azure | opendes | Preshipping QA (primary) |
| `cimpl/qa` | CIMPL | qa | CIMPL QA environment |
| `cimpl/dev1` | CIMPL | osdu | CIMPL development |

Switch targets with: `env use azure/ship` or `env use cimpl/qa`

## What Each Skill Needs

| Skill | Requires | Environment |
|-------|----------|-------------|
| azure-ad (invite, audit) | `az` CLI + `AI_OSDU_*` vars | ship |
| azure-osdu (entitlements) | `AI_OSDU_*` vars | ship |
| osdu-qa (API tests) | Test collection configs | ship, cimpl/* |
| osdu-activity (GitLab) | `GITLAB_TOKEN` or `glab` auth | glab |
| osdu-azure (dev toolkit) | `az` CLI + Key Vault access | glab (local dev) |
| glab (MR management) | `GITLAB_TOKEN` or `glab` auth | glab |
