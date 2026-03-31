---
name: iac
allowed-tools: Bash, Read, Glob, Grep, Edit, Write
description: >-
  Infrastructure as Code for Azure SPI — Terraform modules, Azure PaaS services
  (CosmosDB, Service Bus, Storage, Key Vault), Helm/Kustomize deployments, AKS
  Deployment Safeguards, azd integration, multi-partition support, and systematic
  debugging for the osdu-spi-infra repository.
  Use when working with SPI Terraform, Azure PaaS provisioning, azd up/down,
  Workload Identity, multi-partition resources, feature flags, blue/green stacks,
  deployment failures, or infrastructure verification.
  Not for: fork management (use the forks skill), CIMPL infrastructure (use
  cimpl:iac), OSDU platform services, or tool installation (use setup skill).
---

# SPI Infrastructure as Code

Terraform, Helm, and Azure PaaS infrastructure for OSDU SPI, with systematic
debugging and evidence-based verification.

## Quick Start

Before first use, verify tools are available:
```bash
terraform --version && helm version --short && kubectl version --client && az version && azd version
```
If any command is not found, **stop and use the `setup` skill** to install missing dependencies.

## Project Architecture

Three-layer Terraform architecture with independent state per layer, orchestrated by azd:

```
osdu-spi-infra/
├── azure.yaml                  # azd project definition
├── infra/                      # Layer 1: AKS + Azure PaaS (~15 min)
│   ├── aks.tf                  # AVM AKS Automatic module
│   ├── cosmosdb.tf             # Gremlin (entitlements) + SQL (per partition)
│   ├── servicebus.tf           # Per-partition topics
│   ├── storage.tf              # Common + per-partition accounts
│   ├── keyvault.tf             # Secrets and certificates
│   ├── identity.tf             # Workload Identity + federated credentials
│   ├── monitoring.tf           # App Insights, Log Analytics, Prometheus
│   ├── locals.tf               # 24 CosmosDB containers, 14 Service Bus topics
│   └── outputs.tf              # 40+ outputs for downstream layers
├── infra-access/               # Layer 1a: RBAC bootstrap (~1 min)
│   └── main.tf                 # Elevated role assignments
├── software/
│   ├── foundation/             # Layer 2: Cluster operators (~3 min)
│   │   ├── main.tf             # cert-manager, ECK, CNPG, ExternalDNS, Gateway
│   │   └── charts/             # Helm charts per operator
│   └── stack/                  # Layer 3: Middleware + OSDU services (~5 min)
│       ├── middleware.tf        # Elasticsearch, PostgreSQL, Redis, Airflow
│       ├── osdu-services-core.tf      # 11 core services
│       ├── osdu-services-reference.tf # 3 reference services (CRS, Unit)
│       ├── platform.tf         # Namespaces, Karpenter NodePool, Istio mTLS
│       └── modules/            # Helm-based components
│           └── osdu-service/   # Reusable OSDU service wrapper
└── scripts/                    # azd lifecycle hooks (PowerShell 7.4+)
```

**Key separation:**
- **infra/** — Azure resources (AKS, CosmosDB, Service Bus, Storage). State managed by azd.
- **infra-access/** — Elevated RBAC. Separate state for privilege isolation.
- **software/foundation/** — Cluster-wide operators. Independent Terraform state.
- **software/stack/** — OSDU services and middleware. Independent Terraform state.
- Cross-layer values flow through azd environment variables, never direct state references.

---

## Azure PaaS Resources

### CosmosDB

Two types per deployment:

**Gremlin** (1 account) — Entitlements graph database:
```hcl
resource "azurerm_cosmosdb_account" "gremlin" {
  kind = "GlobalDocumentDB"
  capabilities { name = "EnableGremlin" }
}
```

**SQL** (1 per partition) — Operational data with 24 containers:
```hcl
resource "azurerm_cosmosdb_account" "sql" {
  for_each = toset(var.data_partitions)
  kind     = "GlobalDocumentDB"
}
```

Containers include: Authority, EnvConfigValues, FileLocationEntity, IngestionStrategy,
LegalTag, MappingInfo, RegisterAction, RegisterDdms, RegisterSubscription, Schema,
SchemaInfoRepository, StorageRecord, StorageSchema, Tags, TenantInfo, WorkflowCustomOperatorInfo,
WorkflowRunStore, WorkflowV2, and more.

### Service Bus

Per-partition namespaces with 14 topics:
```
indexing-progress, legaltags-changed, records-changed, schema-changed,
storage-records-changed, storage-records-deleted, file-generated,
csv-parser-status, status-changed, topic-wks, reindex-topic,
gcm-topic, replay-topic, search-event
```

### Azure Storage

- **Common account** — System data, Airflow DAGs, CRS conversion data
- **Per-partition accounts** — Legal configs, file area, WKS mappings

### Key Vault

Single vault storing connection strings, credentials, and certificates.
Accessed via Workload Identity — no long-lived secrets in pods.

---

## Multi-Partition Support

```hcl
variable "data_partitions" {
  type    = list(string)
  default = ["opendes"]
}
```

Each partition gets its own CosmosDB SQL account, Service Bus namespace, and Storage
account. System database is created only on the primary partition (first in list).

Use `for_each = toset(var.data_partitions)` for partition-scoped resources.
Use indexing (`var.data_partitions[0]`) only for the primary partition.

---

## Workload Identity

Azure AD federated credentials across 8 namespaces:
`default`, `osdu-core`, `airflow`, `osdu-system`, `osdu-auth`, `osdu-reference`, `osdu`, `platform`

Each namespace gets a ServiceAccount with the annotation:
```yaml
azure.workload.identity/client-id: <managed-identity-client-id>
```

No CSI secret store driver needed — pods authenticate directly to Azure PaaS via
federated tokens.

---

## Feature Flags

Per-service enable/disable in stack variables:

```hcl
# Core services
variable "enable_partition"    { default = true }
variable "enable_entitlements" { default = true }
variable "enable_legal"        { default = true }
# ... etc for all 11 core + 3 reference services

# Middleware
variable "enable_elasticsearch" { default = true }
variable "enable_airflow"       { default = true }
variable "enable_redis"         { default = true }

# Networking
variable "enable_gateway"           { default = true }
variable "enable_osdu_api_ingress"  { default = true }
variable "enable_external_dns"      { default = true }
```

Use count patterns: `count = var.enable_partition ? 1 : 0`

---

## Blue/Green Stacks

The `STACK_NAME` variable enables parallel deployments on the same cluster:

```bash
# Default stack
azd env set STACK_NAME ""          # Namespaces: platform, osdu

# Blue stack
azd env set STACK_NAME "blue"      # Namespaces: platform-blue, osdu-blue
```

Useful for zero-downtime upgrades and canary deployments.

---

## azd Lifecycle Hooks

PowerShell 7.4+ scripts in `scripts/`:

| Hook | Script | Purpose |
|------|--------|---------|
| prerestore | resolve-chart-versions.ps1 | Resolve OSDU chart versions from OCI registry |
| preprovision | pre-provision.ps1 | Validate tools, auto-detect settings, generate credentials |
| postprovision | post-provision.ps1 | Bootstrap Layer 1a RBAC, deploy Layer 2 foundation |
| predeploy | pre-deploy.ps1 | Deploy Layer 3 stack |
| predown | pre-down.ps1 | Destroy stack before cluster teardown |
| postdown | post-down.ps1 | Clean up Terraform state artifacts |

**Important:** These are PowerShell scripts (`.ps1`), not bash. Debugging requires
`pwsh` to be installed. See the setup skill.

---

## Postrender + Kustomize for AKS Safeguards

Charts that don't expose safeguard fields need postrender:

```hcl
resource "helm_release" "operator" {
  name  = "my-operator"
  chart = "my-operator"
  postrender {
    binary_path = "${path.module}/kustomize/postrender.ps1"
  }
}
```

Note: SPI uses PowerShell postrender scripts (`postrender.ps1`), not bash.

AKS Automatic Deployment Safeguards are the same as CIMPL:
- All containers: `readinessProbe`, `livenessProbe`, resource `requests`, `seccompProfile: RuntimeDefault`
- Replicas > 1: `topologySpreadConstraints` or `podAntiAffinity`
- Forbidden: `:latest` tags, privileged containers, `NET_ADMIN`/`NET_RAW`

---

## Key Difference from CIMPL

| Aspect | CIMPL | SPI |
|--------|-------|-----|
| Document DB | PostgreSQL (CNPG, in-cluster) | CosmosDB SQL (Azure PaaS) |
| Graph DB | PostgreSQL (CNPG, in-cluster) | CosmosDB Gremlin (Azure PaaS) |
| Messaging | RabbitMQ (in-cluster) | Service Bus (Azure PaaS) |
| Object storage | MinIO (in-cluster) | Azure Storage (Azure PaaS) |
| Auth | Keycloak (in-cluster) | Azure AD (external) |
| Lifecycle hooks | PowerShell | PowerShell |
| State layers | 3 (infra, foundation, stack) | 4 (infra, infra-access, foundation, stack) |
| Multi-partition | Single partition | N partitions via for_each |
| Platform | GitLab | GitHub |

Both use AKS Automatic, managed Istio, cimpl-helm charts, and azd orchestration.

---

## Debugging Infrastructure Issues

### The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

### Four-Phase Process

| Phase | Action | Output |
|-------|--------|--------|
| 1. Gather Evidence | Collect logs, state, errors | Evidence document |
| 2. Recent Changes | git history, terraform state | Change list |
| 3. Hypothesis | Form single testable theory | Clear hypothesis |
| 4. Verify Fix | Test minimal change, document | Verified solution |

### Phase 1: Gather Evidence

**STOP. Do not attempt any fix yet.**

```bash
# Terraform state
terraform -chdir=infra state list | head -30
terraform -chdir=software/stack state list | head -30

# Azure PaaS health
az cosmosdb show --name <name> -g <rg> --query provisioningState
az servicebus namespace show --name <name> -g <rg> --query status
az storage account show --name <name> -g <rg> --query statusOfPrimary

# Cluster health
kubectl get pods -A --field-selector status.phase!=Running
kubectl get events --sort-by=.lastTimestamp -A | tail -20

# azd state
azd env get-values
```

### Phase 2: Recent Changes

```bash
git log --oneline -10
terraform -chdir=infra state pull | jq '.serial'
```

### Phase 3: Form Hypothesis

State a single, testable theory: "The Service Bus topic X is not receiving messages
because the Workload Identity federation is missing for namespace Y."

### Phase 4: Verify Fix

Make the minimal change. Verify with fresh evidence. Document what was wrong and why.

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```
