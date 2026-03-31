# Fork Repository Registry

Complete reference for all Azure OSDU SPI service forks.

## Active Forks

| # | Service | GitHub Repo | Upstream GitLab Path | Build System |
|---|---------|-------------|---------------------|-------------|
| 1 | Partition | [azure/osdu-spi-partition](https://github.com/azure/osdu-spi-partition) | osdu/platform/system/partition | Maven (Java 17) |
| 2 | Entitlements | [azure/osdu-spi-entitlements](https://github.com/azure/osdu-spi-entitlements) | osdu/platform/security-and-compliance/entitlements | Maven (Java 17) |
| 3 | Legal | [azure/osdu-spi-legal](https://github.com/azure/osdu-spi-legal) | osdu/platform/security-and-compliance/legal | Maven (Java 17) |
| 4 | Schema | [azure/osdu-spi-schema](https://github.com/azure/osdu-spi-schema) | osdu/platform/system/schema-service | Maven (Java 17) |
| 5 | File | [azure/osdu-spi-file](https://github.com/azure/osdu-spi-file) | osdu/platform/system/file | Maven (Java 17) |
| 6 | Storage | [azure/osdu-spi-storage](https://github.com/azure/osdu-spi-storage) | osdu/platform/system/storage | Maven (Java 17) |
| 7 | Indexer | [azure/osdu-spi-indexer](https://github.com/azure/osdu-spi-indexer) | osdu/platform/system/indexer-service | Maven (Java 17) |
| 8 | Search | [azure/osdu-spi-search](https://github.com/azure/osdu-spi-search) | osdu/platform/system/search-service | Maven (Java 17) |

## Template Repository

| Repo | Purpose |
|------|---------|
| [azure/osdu-spi](https://github.com/azure/osdu-spi) | Fork management template — workflows, actions, configuration |

## Why These 8 Services?

These are the OSDU core services where Azure maintains cloud-specific SPI layer
code — primarily around:

- **Data persistence** — CosmosDB SQL/Gremlin instead of PostgreSQL
- **Messaging** — Service Bus instead of RabbitMQ
- **Object storage** — Azure Blob Storage instead of MinIO
- **Authentication** — Azure AD/Entra ID instead of Keycloak
- **Secrets** — Key Vault instead of environment variables

All other OSDU services (CRS, Unit, Notification, Register, etc.) run unmodified
community code via cimpl-helm charts.

## Build Architecture (ADR-025)

All forks use identical build configuration:
- **Runtime:** Eclipse Temurin Java 17
- **Build tool:** Maven 3.9+
- **Coverage:** JaCoCo
- **CI:** GitHub Actions (`build.yml` from template)
- **Dependencies:** GitLab-hosted OSDU Maven repository

## Repository Initialization

New forks are created from the template:

1. Navigate to [azure/osdu-spi](https://github.com/azure/osdu-spi)
2. Click "Use this template" → "Create a new repository"
3. Name: `osdu-spi-<service-name>`
4. The `init.yml` workflow auto-configures:
   - Three branches (main, fork_upstream, fork_integration)
   - Branch protection rules
   - Labels
   - Workflows (from template-workflows/)
   - GitHub App permissions

Initialization completes in < 5 minutes.

## Multi-Repo Operations

### List All Fork Repos

```bash
gh repo list azure --json name --jq '.[].name' | grep '^osdu-spi-' | sort
```

### Bulk Status

```bash
for svc in partition entitlements legal schema file storage indexer search; do
  REPO="azure/osdu-spi-$svc"
  PRS=$(gh pr list --repo "$REPO" --state open --json number --jq 'length' 2>/dev/null || echo "?")
  ISSUES=$(gh issue list --repo "$REPO" --state open --json number --jq 'length' 2>/dev/null || echo "?")
  SYNC=$(gh pr list --repo "$REPO" --label upstream-sync --state open --json number --jq 'length' 2>/dev/null || echo "0")
  echo "osdu-spi-$svc: ${PRS} PRs (${SYNC} sync), ${ISSUES} issues"
done
```

### Bulk Workflow Trigger

```bash
# Trigger sync for all forks
for svc in partition entitlements legal schema file storage indexer search; do
  gh workflow run sync.yml --repo "azure/osdu-spi-$svc" 2>/dev/null && echo "osdu-spi-$svc: triggered" || echo "osdu-spi-$svc: skipped"
done
```

### Clone All Forks Locally

```bash
for svc in partition entitlements legal schema file storage indexer search; do
  gh repo clone "azure/osdu-spi-$svc" -- --branch main
done
```
