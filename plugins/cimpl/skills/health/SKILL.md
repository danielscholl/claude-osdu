---
name: health
allowed-tools: Bash, Read, Glob
description: >-
  Comprehensive health assessment of deployed AZD environments — cluster
  infrastructure, workloads, and OSDU platform services.
  Use when the user asks about environment health, cluster status, or wants a
  report on their deployed environments. Trigger on phrases like "report on my
  environments", "environment health", "how is my cluster", "cluster status",
  "environment status", or "what's deployed".
  Not for: deploying or modifying infrastructure (use the iac skill), installing
  tools (use the setup skill), or application-level debugging.
---

# Environment Health Report

Comprehensive health assessment of deployed AZD environments — cluster infrastructure, workloads, and OSDU platform services.

## The Iron Law

```
EVERY HEALTH REPORT MUST USE LIVE DATA — NEVER ASSUME STATUS
```

Connect to the actual cluster and query real endpoints. Cached or assumed status is worthless.

## When to Use This Skill

- User asks to "report on my environments"
- User asks about environment health, cluster health, or cluster status
- User asks "how is my cluster", "what's deployed", "is everything running"
- User asks for environment details or a status overview
- User asks "what environments do I have" and wants depth beyond a simple listing
- Before or after a deployment to confirm state

## Quick Start

```bash
# Verify key tools
kubectl version --client
az version
```

If either command is not found, **stop and use the `setup` skill** to install missing dependencies.

## Report Procedure

Follow these phases in order. Do NOT skip phases — partial reports must be clearly labeled as incomplete.

### Phase 1: Enumerate Environments

Discover all configured AZD environments from the `.azure/` directory.

```bash
# List all environments
ls -d .azure/*/

# For each environment, extract key config
grep -E "^(AZURE_ENV_NAME|AZURE_LOCATION|AZURE_RESOURCE_GROUP|AZURE_AKS_CLUSTER_NAME|AZURE_SUBSCRIPTION_ID)" .azure/<env>/.env
```

Present a summary table:

| Environment | Location | Resource Group | AKS Cluster | Subscription |
|-------------|----------|---------------|-------------|--------------|

### Phase 2: Connect to Cluster

For each environment, establish kubectl context using the credentials command stored in the environment config.

```bash
# Extract and run the get-credentials command from the env file
grep "get_credentials_command" .azure/<env>/.env

# Execute it (typically):
az aks get-credentials -g <resource-group> -n <cluster-name> && kubelogin convert-kubeconfig -l azurecli
```

**If connection fails**, report the failure clearly and skip to the next environment. Do NOT fabricate cluster data.

### Phase 3: Cluster Infrastructure Health

Run these commands and interpret the output:

```bash
# Node status — all should be Ready
kubectl get nodes -o wide

# Cluster version
kubectl version --short 2>/dev/null || kubectl version

# Namespace inventory
kubectl get namespaces

# Pod health — find non-running pods (excluding Completed jobs)
kubectl get pods -A --no-headers | grep -v Running | grep -v Completed

# Resource pressure
kubectl top nodes 2>/dev/null || echo "Metrics server not available"
```

**Report format:**

| Check | Status | Details |
|-------|--------|---------|
| Nodes | pass / warn / fail | X/Y Ready, versions |
| K8s Version | — | vX.Y.Z |
| Pods | pass / warn / fail | X running, Y failing |
| Resource Pressure | pass / warn | CPU/Memory utilization |

### Phase 4: Workload Health

Check key platform namespaces and their workloads:

```bash
# Helm releases — what's deployed
helm list -A --no-headers 2>/dev/null

# Key namespace pod status
for ns in osdu-system airflow cert-manager ingress-nginx kube-system monitoring; do
  echo "=== $ns ==="
  kubectl get pods -n $ns --no-headers 2>/dev/null | awk '{print $3}' | sort | uniq -c
done

# Ingress status
kubectl get ingress -A 2>/dev/null

# Certificate status (cert-manager)
kubectl get certificates -A 2>/dev/null
```

**Report format:**

| Namespace | Pods | Status | Notes |
|-----------|------|--------|-------|
| osdu-system | X/Y ready | pass / warn / fail | key observations |

### Phase 5: OSDU Platform Health

Use the OSDU MCP server tools to check platform-level health.

**Step 1: Run the health check**

Use the `osdu_health_check` tool from the OSDU MCP server (with `include_services: true`) to probe:
- Connectivity (network + base URL reachability)
- Authentication (token acquisition)
- Service endpoints (Search, Storage, Schema, Legal, Entitlements, Partition)

**Step 2: Query service versions**

Use available OSDU MCP server tools to gather version/status data:
- `osdu_schema_list` — verify schema service responds and count available schemas
- `osdu_search_query` — verify search service responds (kind: `*:*:*:*`, limit: 1)
- `osdu_partition_list` — list active data partitions
- `osdu_legaltag_list` — verify legal service responds
- `osdu_entitlements_mine` — verify entitlements service and show current user groups

**Report format:**

| Service | Status | Details |
|---------|--------|---------|
| Connectivity | pass / fail | URL reachable |
| Auth | pass / fail | Token acquired |
| Search | pass / fail | Response time, record count |
| Storage | pass / fail | Endpoint status |
| Schema | pass / fail | X schemas available |
| Legal | pass / fail | X legal tags |
| Entitlements | pass / fail | X groups |
| Partition | pass / fail | Partitions listed |

**If the OSDU MCP server is not configured or the `osdu_health_check` tool fails**, skip the entire Phase 5 and report:
> OSDU platform API health check skipped — MCP server not connected. Configure the OSDU MCP server and restart.

**Do NOT attempt to probe OSDU endpoints directly via curl, wget, or kubectl port-forward.** The OSDU MCP server handles authentication, SSL, and endpoint resolution — manual probes are unreliable and create noise. Report what you know from kubectl (Phase 3-4) and note that API-level checks require the OSDU MCP server.

### Phase 6: Summary

Produce an overall health summary with a clear verdict:

```
## Environment Health Summary: <env-name>

Overall: Healthy / Degraded / Unhealthy

### Infrastructure
- Nodes: X/Y Ready
- K8s: vX.Y.Z
- Pods: X running, Y failing

### Platform Services
- OSDU: X/Y services healthy
- Key issues: [list any]

### Action Items
- [Any recommended actions]
```

## Handling Multiple Environments

When multiple environments exist:
1. List all environments first
2. Ask the user which to inspect (or inspect all if they said "all" or "environments" plural)
3. Run the full report for each selected environment
4. Provide a cross-environment comparison table if more than one

## Error Handling

| Error | Action |
|-------|--------|
| `az aks get-credentials` fails | Check subscription access, report and skip |
| `kubectl` commands fail | Cluster may be down — report connection failure |
| OSDU MCP server tools fail | Platform may be down — report with last-known status |
| Metrics server unavailable | Skip resource pressure, note in report |
| Namespace doesn't exist | Skip that namespace, note it's not deployed |

## Red Flags

| Signal | Meaning |
|--------|---------|
| Nodes NotReady | Cluster infrastructure problem |
| Pods in CrashLoopBackOff | Application configuration or dependency failure |
| Pods in Pending | Resource constraints or scheduling issues |
| OSDU auth failure | Keycloak/identity issue |
| Multiple services down | Possible infrastructure-level outage |
| Certificates not ready | TLS/ingress will fail |

## Integration

After generating the report:
- If issues are found, suggest using the `iac` skill to investigate
- If verification is needed after fixes, suggest re-running this health check
