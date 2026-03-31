# SPI Plugin

## Scope

The @spi agent is the infrastructure and fork management specialist for Azure's OSDU
Service Provider Interface (SPI) repositories.

**Handles:** osdu-spi (fork template), osdu-spi-infra (Azure PaaS infrastructure),
osdu-spi-{partition,entitlements,legal,schema,file,storage,indexer,search} (service forks).
Terraform, Helm, AKS, Azure PaaS (CosmosDB, Service Bus, Storage, Key Vault), GitHub Actions
workflows, three-branch fork management, upstream sync, cascade integration, fork initialization
into configurable orgs, cross-repo status aggregation and monitoring.

**Does NOT handle:** CIMPL infrastructure (`cimpl-azure-provisioning`) — that belongs to
the cimpl plugin. OSDU platform services on GitLab (QA, analytics, builds, knowledge) —
that belongs to the osdu plugin.

**Platform:** GitHub (`gh` CLI), not GitLab (`glab`).

## Deployment Layers (osdu-spi-infra)

| Layer | Path | Technology |
|-------|------|-----------|
| L1 — Infrastructure | `infra/` | Terraform — AKS + CosmosDB + Service Bus + Storage + Key Vault |
| L1a — RBAC bootstrap | `infra-access/` | Terraform — elevated role assignments |
| L2 — Foundation | `software/foundation/` | Terraform + Helm — cert-manager, ECK, CNPG, ExternalDNS, Gateway API |
| L3 — Stack | `software/stack/` | Terraform + Helm — Elasticsearch, PostgreSQL, Redis, Airflow, OSDU services |

## Fork Repos (osdu-spi template)

| Service | GitHub repo | Upstream GitLab |
|---------|-------------|----------------|
| Partition | azure/osdu-spi-partition | osdu/platform/system/partition |
| Entitlements | azure/osdu-spi-entitlements | osdu/platform/security-and-compliance/entitlements |
| Legal | azure/osdu-spi-legal | osdu/platform/security-and-compliance/legal |
| Schema | azure/osdu-spi-schema | osdu/platform/system/schema-service |
| File | azure/osdu-spi-file | osdu/platform/system/file |
| Storage | azure/osdu-spi-storage | osdu/platform/system/storage |
| Indexer | azure/osdu-spi-indexer | osdu/platform/system/indexer-service |
| Search | azure/osdu-spi-search | osdu/platform/system/search-service |

## Cross-Plugin Routing

When context is ambiguous between SPI and CIMPL:

| Signal | Routes to |
|--------|-----------|
| Repo contains "osdu-spi" | **spi** |
| Repo contains "cimpl" | **cimpl** |
| GitHub context (`gh` CLI, GitHub Actions) | **spi** |
| GitLab context (`glab` CLI, GitLab CI) | **cimpl** or **osdu** |
| Azure PaaS (CosmosDB, Service Bus, Key Vault) | **spi** |
| In-cluster middleware (RabbitMQ, MinIO, Keycloak) | **cimpl** |
| Fork management, three-branch, upstream sync | **spi** |

## Quality Checks

Before shipping infrastructure changes:
- `terraform fmt -check` on all `.tf` files
- `helm lint` on chart directories
- PowerShell syntax validation on `.ps1` scripts
