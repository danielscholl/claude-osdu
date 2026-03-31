# Blue/Green Stack Deployments

SPI infrastructure supports parallel stack deployments on the same AKS cluster
via the `STACK_NAME` environment variable.

## How It Works

The `STACK_NAME` variable prefixes namespace names, enabling multiple independent
deployments to coexist on the same cluster infrastructure.

```bash
# Default deployment (no STACK_NAME or empty)
#   Namespaces: platform, osdu
azd env set STACK_NAME ""

# Blue deployment
#   Namespaces: platform-blue, osdu-blue
azd env set STACK_NAME "blue"

# Green deployment
#   Namespaces: platform-green, osdu-green
azd env set STACK_NAME "green"
```

## What Gets Namespaced

| Component | Default | With STACK_NAME=blue |
|-----------|---------|---------------------|
| Platform namespace | `platform` | `platform-blue` |
| OSDU namespace | `osdu` | `osdu-blue` |
| Helm release names | `<service>` | `<service>-blue` |
| Gateway HTTPRoutes | Default routes | Blue-specific routes |

## What Is Shared (Not Namespaced)

- Layer 1: All Azure PaaS resources (CosmosDB, Service Bus, Storage, Key Vault)
- Layer 1a: RBAC assignments
- Layer 2: Foundation operators (cert-manager, ECK, CNPG, ExternalDNS)
- Elasticsearch cluster (shared across stacks)
- PostgreSQL cluster (shared across stacks)

## Use Cases

### Zero-Downtime Upgrades

1. Deploy the new version as a "blue" stack alongside the existing "green" stack
2. Validate the blue stack with health checks and smoke tests
3. Switch traffic from green to blue via Gateway API route updates
4. Tear down the green stack after validation

### Canary Testing

1. Deploy a canary stack with a subset of services
2. Route a percentage of traffic to the canary via Gateway API weights
3. Monitor error rates and latency
4. Promote or rollback based on metrics

### Development/Staging

Run multiple environments on one cluster to reduce infrastructure costs:
- `STACK_NAME=""` — Production
- `STACK_NAME="staging"` — Pre-production testing
- `STACK_NAME="dev"` — Development

## Deploying a Named Stack

```bash
# Set the stack name
azd env set STACK_NAME "blue"

# Deploy (only Layer 3 changes — Layers 1/2 are shared)
azd deploy
```

## Tearing Down a Named Stack

```bash
# Select the stack to tear down
azd env set STACK_NAME "blue"

# Tear down only the stack layer
# The pre-down hook destroys only the namespaced resources
azd down
```

## Limitations

- Each stack needs its own set of Workload Identity ServiceAccounts in its namespaces
- Elasticsearch and PostgreSQL are shared — all stacks use the same data
- Service Bus and CosmosDB are shared — parallel stacks process the same messages
- Not suitable for complete data isolation (use separate clusters for that)
