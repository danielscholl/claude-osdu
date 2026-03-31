# Feature Flags

All services and middleware in the SPI stack can be individually enabled/disabled.

## Flag Hierarchy

```
enable_osdu_core_services (master switch)
├── enable_common
├── enable_partition
├── enable_entitlements
├── enable_legal
├── enable_schema
├── enable_storage
├── enable_search
├── enable_indexer
├── enable_indexer_queue
├── enable_file
└── enable_workflow

enable_osdu_reference_services (master switch)
├── enable_unit
├── enable_crs_conversion
└── enable_crs_catalog
```

## Core Service Flags

Defined in `software/stack/variables-flags-osdu-core.tf`:

| Flag | Default | Service |
|------|---------|---------|
| `enable_osdu_core_services` | true | Master switch for all core services |
| `enable_common` | true | Shared namespace resources (ConfigMaps, Secrets) |
| `enable_partition` | true | Partition service |
| `enable_entitlements` | true | Entitlements service |
| `enable_legal` | true | Legal service |
| `enable_schema` | true | Schema service |
| `enable_storage` | true | Storage service |
| `enable_search` | true | Search service |
| `enable_indexer` | true | Indexer service |
| `enable_indexer_queue` | true | Indexer Queue service |
| `enable_file` | true | File service |
| `enable_workflow` | true | Workflow service |

## Reference Service Flags

Defined in `software/stack/variables-flags-osdu-reference.tf`:

| Flag | Default | Service |
|------|---------|---------|
| `enable_osdu_reference_services` | true | Master switch for reference services |
| `enable_unit` | true | Unit service |
| `enable_crs_conversion` | true | CRS Conversion service |
| `enable_crs_catalog` | true | CRS Catalog service |

## Platform & Middleware Flags

Defined in `software/stack/variables-flags-platform.tf`:

| Flag | Default | Component |
|------|---------|-----------|
| `enable_nodepool` | true | Karpenter NodePool for stateful workloads |
| `enable_public_ingress` | true | Public ingress |
| `enable_external_dns` | false | ExternalDNS (disabled by default) |
| `enable_cert_manager` | true | cert-manager TLS certificates |
| `enable_gateway` | true | Gateway API resources |
| `enable_redis` | true | In-cluster Redis |
| `enable_elasticsearch` | true | Elasticsearch + Kibana |
| `enable_elastic_bootstrap` | true | Elastic Bootstrap job |
| `enable_airflow` | true | Airflow (includes PostgreSQL) |

## Ingress Flags

| Flag | Default | Route |
|------|---------|-------|
| `enable_osdu_api_ingress` | true | OSDU API HTTPRoute |
| `enable_airflow_ingress` | true | Airflow UI HTTPRoute |
| `enable_kibana_ingress` | true | Kibana UI HTTPRoute |

## Usage Pattern

In Terraform modules:

```hcl
module "partition" {
  source = "./modules/osdu-service"
  count  = var.enable_osdu_core_services && var.enable_partition ? 1 : 0
  # ...
}
```

The master switch AND the individual flag must both be true.

## Setting Flags via azd

```bash
# Disable reference services
azd env set TF_VAR_enable_osdu_reference_services false

# Disable a specific service
azd env set TF_VAR_enable_search false

# Disable Grafana (cost optimization)
azd env set ENABLE_GRAFANA_WORKSPACE false
```
