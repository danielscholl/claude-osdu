---
description: >-
  Clone OSDU GitLab repositories to the local workspace with optional worktree layout.
---

Clone the requested OSDU repositories directly. Do NOT delegate to an agent or load a skill.

## Step 1: Resolve the request

From the arguments below, determine which repos to clone. Map the input to repo names and URLs.

$ARGUMENTS

### Repo → URL mapping

Base: `https://community.opengroup.org`

| Repo | URL path |
|------|----------|
| cimpl-azure-provisioning | `osdu/platform/deployment-and-operations/cimpl-azure-provisioning` |
| os-core-common | `osdu/platform/system/lib/core/os-core-common` |
| os-core-lib-azure | `osdu/platform/system/lib/cloud/azure/os-core-lib-azure` |
| entitlements | `osdu/platform/security-and-compliance/entitlements` |
| legal | `osdu/platform/security-and-compliance/legal` |
| crs-catalog-service | `osdu/platform/system/reference/crs-catalog-service` |
| crs-conversion-service | `osdu/platform/system/reference/crs-conversion-service` |
| unit-service | `osdu/platform/system/reference/unit-service` |
| wellbore-domain-services | `osdu/platform/domain-data-mgmt-services/wellbore/wellbore-domain-services` |
| seismic-store-service | `osdu/platform/domain-data-mgmt-services/seismic/seismic-dms-suite/seismic-store-service` |
| ingestion-workflow | `osdu/platform/data-flow/ingestion/ingestion-workflow` |
| partition | `osdu/platform/system/partition` |
| storage | `osdu/platform/system/storage` |
| indexer-service | `osdu/platform/system/indexer-service` |
| indexer-queue | `osdu/platform/system/indexer-queue` |
| search-service | `osdu/platform/system/search-service` |
| schema-service | `osdu/platform/system/schema-service` |
| file | `osdu/platform/system/file` |
| notification | `osdu/platform/system/notification` |
| secret | `osdu/platform/system/secret` |
| dataset | `osdu/platform/system/dataset` |
| register | `osdu/platform/system/register` |

### Categories

| Category | Repos |
|----------|-------|
| infra | cimpl-azure-provisioning |
| libraries | os-core-common, os-core-lib-azure |
| core | partition, entitlements, legal, secret, schema-service, storage, file, indexer-service, indexer-queue, search-service, dataset, register, notification |
| reference | crs-catalog-service, crs-conversion-service, unit-service |
| ingestion | ingestion-workflow |
| domain | wellbore-domain-services, seismic-store-service |

Map common aliases: "common lib" → os-core-common, "search" → search-service, etc.
Repo names take precedence over category names.

## Step 2: Run the clone script

Find the bundled script and run it once per repo:

```bash
CLONE_SCRIPT=$(find ~/.claude/plugins -path "*/skills/clone/clone.py" -type f 2>/dev/null | head -1)
uv run "$CLONE_SCRIPT" "https://community.opengroup.org/{path}.git"
```

The script handles workspace resolution, worktree detection, and clone execution automatically.

## Step 3: Report results

Show which repos were cloned, skipped, or failed.
