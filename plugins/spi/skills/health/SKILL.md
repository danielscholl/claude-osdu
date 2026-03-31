---
name: health
allowed-tools: Bash, Read, Glob
description: >-
  Comprehensive health assessment of deployed SPI environments — cluster
  infrastructure, Azure PaaS resources, workloads, and OSDU platform services.
  Use when the user asks about SPI environment health, cluster status, Azure PaaS
  health, CosmosDB status, Service Bus health, or wants a report on their deployed
  SPI environments. Trigger on phrases like "report on my SPI environment",
  "environment health", "how is my cluster", "cluster status", "is CosmosDB healthy",
  or "what's deployed".
  Not for: deploying or modifying infrastructure (use the iac skill), fork management
  (use the forks skill), installing tools (use the setup skill), or CIMPL environments
  (use cimpl:health).
---

# SPI Environment Health Report

Comprehensive health assessment of deployed SPI environments — cluster infrastructure,
Azure PaaS resources, workloads, and OSDU platform services.

## The Iron Law

```
EVERY HEALTH REPORT MUST USE LIVE DATA — NEVER ASSUME STATUS
```

## Quick Start

```bash
kubectl version --client && az version
```
If either is not found, **stop and use the `setup` skill**.

## Report Procedure

Follow phases in order. Do NOT skip phases.

### Phase 1: Enumerate Environments

```bash
# List azd environments
ls -d .azure/*/

# For each, extract key config
grep -E "^(AZURE_ENV_NAME|AZURE_LOCATION|AZURE_RESOURCE_GROUP)" .azure/<env>/.env
```

### Phase 2: Connect to Cluster

```bash
az aks get-credentials -g <resource-group> -n <cluster-name>
kubelogin convert-kubeconfig -l azurecli
```

If connection fails, report the failure and skip to next environment.

### Phase 3: Cluster Infrastructure Health

```bash
# Node status
kubectl get nodes -o wide

# Pod health
kubectl get pods -A --no-headers | grep -v Running | grep -v Completed

# Resource pressure
kubectl top nodes 2>/dev/null || echo "Metrics server not available"
```

### Phase 4: Azure PaaS Health

**This phase is unique to SPI.** Check all Azure PaaS resources:

```bash
RG="<resource-group>"

# CosmosDB accounts
echo "=== CosmosDB ==="
az cosmosdb list -g "$RG" --query "[].{name:name, kind:kind, state:provisioningState}" -o table

# Service Bus namespaces
echo "=== Service Bus ==="
az servicebus namespace list -g "$RG" --query "[].{name:name, status:status}" -o table

# Storage accounts
echo "=== Storage ==="
az storage account list -g "$RG" --query "[].{name:name, status:statusOfPrimary, kind:kind}" -o table

# Key Vault
echo "=== Key Vault ==="
az keyvault list -g "$RG" --query "[].{name:name, state:properties.provisioningState}" -o table
```

**Per-partition checks:**
```bash
# CosmosDB SQL databases per partition
for acct in $(az cosmosdb list -g "$RG" --query "[?kind=='GlobalDocumentDB' && !contains(capabilities[].name, 'EnableGremlin')].name" -o tsv); do
  echo "=== $acct ==="
  az cosmosdb sql database list --account-name "$acct" -g "$RG" --query "[].{name:id}" -o table
  az cosmosdb sql container list --account-name "$acct" -g "$RG" --database-name "osdu-db" --query "[].{name:id}" -o table 2>/dev/null
done

# Service Bus topics per partition
for ns in $(az servicebus namespace list -g "$RG" --query "[].name" -o tsv); do
  TOPIC_COUNT=$(az servicebus topic list --namespace-name "$ns" -g "$RG" --query "length(@)" -o tsv 2>/dev/null || echo "?")
  echo "$ns: $TOPIC_COUNT topics"
done
```

**Report format:**

| Resource | Instance | Status | Details |
|----------|----------|--------|---------|
| CosmosDB Gremlin | spi-env-graph | Succeeded | Entitlements graph |
| CosmosDB SQL | spi-env-opendes | Succeeded | 24 containers |
| Service Bus | spi-env-opendes-bus | Active | 14 topics |
| Storage (common) | spienvstorage | available | 8 containers |
| Storage (partition) | spienvopendes | available | 5 containers |
| Key Vault | spi-env-kv | Succeeded | Accessible |

### Phase 5: Workload Health

```bash
# Helm releases
helm list -A --no-headers 2>/dev/null

# Key namespace status
for ns in platform osdu osdu-core osdu-reference airflow cert-manager; do
  echo "=== $ns ==="
  kubectl get pods -n "$ns" --no-headers 2>/dev/null | awk '{print $3}' | sort | uniq -c
done

# Gateway / Ingress
kubectl get gateway -A 2>/dev/null
kubectl get httproute -A 2>/dev/null

# Certificates
kubectl get certificates -A 2>/dev/null
```

### Phase 6: OSDU Platform Health

Use the OSDU MCP server tools if available:
- `osdu_health_check` with `include_services: true`
- `osdu_partition_list`
- `osdu_search_query` (kind `*:*:*:*`, limit 1)
- `osdu_entitlements_mine`

If MCP server is not configured, skip and note:
> OSDU platform API health check skipped — MCP server not connected.

### Phase 7: Summary

```
## SPI Environment Health: <env-name>

Overall: Healthy / Degraded / Unhealthy

### Infrastructure
- Nodes: X/Y Ready
- K8s: vX.Y.Z
- Pods: X running, Y failing

### Azure PaaS
- CosmosDB: X accounts (all Succeeded / N degraded)
- Service Bus: X namespaces (all Active / N degraded)
- Storage: X accounts (all available / N degraded)
- Key Vault: Accessible / Inaccessible

### Partitions
- opendes: CosmosDB 24 containers, Service Bus 14 topics, Storage 5 containers

### OSDU Services
- X/Y services healthy
- Key issues: [list any]

### Action Items
- [Any recommended actions]
```

## Red Flags

| Signal | Meaning |
|--------|---------|
| CosmosDB provisioningState != Succeeded | Database provisioning issue |
| Service Bus status != Active | Messaging disrupted |
| Storage statusOfPrimary != available | Object storage outage |
| Key Vault inaccessible | Secrets unavailable |
| Missing partition resources | Incomplete partition provisioning |
| Pods in CrashLoopBackOff | Application/config failure |

## Integration

- Issues found → suggest `iac` skill to investigate
- After fixes → re-run health check to verify
- For CIMPL environments → use `cimpl:health` instead
