---
name: osdu-data-load
allowed-tools: Bash, Read, Glob, Grep
description: >-
  Load OSDU datasets (reference data, TNO, Volve, NOPIMS) into any OSDU instance.
  Use when the user asks to load test data, bootstrap an instance, populate reference data,
  check what data is loaded, list available datasets, or load specific datasets like TNO/Volve/NOPIMS.
  Also triggers on "what datasets are available", "is reference data loaded", "load all data",
  or "how do I get test data into my OSDU instance".
  Supports CIMPL (auto-detected via kubectl) and Azure ADME (via environment variables).
  Not for: querying existing records (use OSDU MCP tools), schema management (use schema MCP tools),
  or building/testing services (use maven or acceptance-test).
---

# OSDU Data Load

> **Execute directly. Do NOT delegate to an agent or sub-agent.**

## Step 1: Parse the user's intent

| User Input | Action |
|------------|--------|
| `datasets`, `what datasets`, `list data`, `what can I load` | Run `datasets` command |
| `check`, `what's loaded`, `is reference data loaded`, `how many records` | Run `check` command |
| `load reference-data`, `load tno`, `load volve`, `load nopims` | Run `load` command |
| `load all`, `bootstrap instance`, `populate data` | Run `load --dataset all` |
| `dry run`, `preview load`, `what would load do` | Run `load --dry-run` |

## Step 2: Verify prerequisites

Before running any command, check:

1. **uv** is installed: `uv --version`
2. **Data repos** are cloned (the script will tell you if they're missing, but you can check proactively):
   - `data-definitions` — needed for reference-data, schemas, activity-templates
   - `open-test-data` — needed for tno, volve, nopims

If repos are missing, clone them using the `clone` skill or the commands shown in the script output.

For CIMPL environments, **kubectl** must be configured and pointing at the cluster. The script auto-detects everything else.

## Step 3: Run the command

The script path (relative to plugin root):
```
LOAD_SCRIPT="skills/osdu-data-load/scripts/load.py"
```

### List Available Datasets
```bash
uv run "$LOAD_SCRIPT" datasets
```

### Check What's Loaded
```bash
uv run "$LOAD_SCRIPT" check --dataset reference-data
uv run "$LOAD_SCRIPT" check --dataset all
```

### Load Data

Two modes:
- **`--direct`** (recommended): Uses Storage API directly. Fast, synchronous.
- **Default (Workflow)**: Submits to Airflow DAG pipeline. Slower but validates schema/integrity.

```bash
# Load reference data (fast direct mode)
uv run "$LOAD_SCRIPT" load --dataset reference-data --direct

# Load TNO test dataset
uv run "$LOAD_SCRIPT" load --dataset tno --direct

# Load everything
uv run "$LOAD_SCRIPT" load --dataset all --direct

# Preview without submitting
uv run "$LOAD_SCRIPT" load --dataset reference-data --dry-run

# Filter by filename
uv run "$LOAD_SCRIPT" load --dataset reference-data --direct --filter seismic
```

## Dataset Registry

| Dataset | Source Repo | Contents | Recommended Mode |
|---------|-------------|----------|-----------------|
| `reference-data` | data-definitions | 566 lookup catalogs, 79,904 records | `--direct` |
| `schemas` | data-definitions | OSDU schema registrations | workflow |
| `activity-templates` | data-definitions | Standard subsurface activity templates | `--direct` |
| `tno` | open-test-data | TNO wells, wellbores, logs, markers, trajectories | `--direct` |
| `volve` | open-test-data | Volve wells, wellbores, seismics, logs, horizons | workflow |
| `nopims` | open-test-data | Australian open petroleum wells, wellbores, seismics | workflow |

## Environment Configuration

### CIMPL Environments (Zero Config)

If kubectl is configured and pointing at a CIMPL cluster, the script **auto-detects** everything:
- Reads `datafier-secret` from the `osdu` namespace
- Derives Keycloak token URL from the `platform` namespace
- Manages port-forwards automatically (Keycloak 18082, Storage 18081, Search 18084, Workflow 18083)
- Defaults to `osdu-demo-legaltag` legal tag

### Azure ADME / Helm Environments

```bash
export OSDU_URL="https://platform5552.energy.azure.com"
export OSDU_DATA_PARTITION="opendes"
export OSDU_CLIENT_ID="<client-id>"
export OSDU_CLIENT_SECRET="<client-secret>"
export OSDU_TENANT_ID="<tenant-id>"
export OSDU_LEGAL_TAG="opendes-legal-tag-load"
```

### Keycloak Environments (Manual)

```bash
export OSDU_URL="https://osdu.myenv.example.com"
export OSDU_DATA_PARTITION="osdu"
export OSDU_CLIENT_ID="datafier"
export OSDU_CLIENT_SECRET="<secret>"
export OSDU_TOKEN_URL="https://keycloak.myenv.example.com/realms/osdu/protocol/openid-connect/token"
export OSDU_LEGAL_TAG="osdu-demo-legaltag"
```

## Required Data Repos

```bash
git clone https://community.opengroup.org/osdu/data/data-definitions.git ~/workspace/data-definitions
git clone https://community.opengroup.org/osdu/data/open-test-data.git ~/workspace/open-test-data
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OSDU_URL` | ADME only | auto-detected for CIMPL | OSDU base URL |
| `OSDU_DATA_PARTITION` | ADME only | `osdu` for CIMPL | Data partition |
| `OSDU_CLIENT_ID` | ADME only | auto-detected for CIMPL | Client ID |
| `OSDU_CLIENT_SECRET` | ADME only | auto-detected for CIMPL | Client secret |
| `OSDU_TENANT_ID` | ADME only | — | Azure AD tenant ID |
| `OSDU_TOKEN_URL` | Keycloak manual | auto-detected for CIMPL | Keycloak token endpoint |
| `OSDU_LEGAL_TAG` | ADME only | `osdu-demo-legaltag` for CIMPL | Legal tag |
| `OSDU_RESOURCE_ID` | No | same as client_id | AAD app ID for OAuth scope |
| `OSDU_ACL_OWNERS` | No | derived from partition | ACL owners group |
| `OSDU_ACL_VIEWERS` | No | derived from partition | ACL viewers group |
| `OSDU_DATA_DEFINITIONS_DIR` | No | `~/workspace/data-definitions` | data-definitions repo path |
| `OSDU_OPEN_TEST_DATA_DIR` | No | `~/workspace/open-test-data` | open-test-data repo path |

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| Missing env vars | Not configured and not CIMPL | Set required variables or ensure kubectl context |
| `Repo not found` | Data repo not cloned | Run `git clone` command shown above |
| HTTP 401/403 | Auth failure | Check credentials or kubectl context |
| HTTP 409 | Record exists | Safe to ignore (record already loaded) |
| "Invalid legal tags" | Wrong legal tag name | Check `OSDU_LEGAL_TAG` matches an existing tag |
| Port-forward failure | Service not running in cluster | Check `kubectl get svc -n osdu` for available services |
