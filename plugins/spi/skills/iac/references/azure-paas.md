# Azure PaaS Resource Patterns

Detailed reference for Azure PaaS resources provisioned by osdu-spi-infra Layer 1.

## CosmosDB

### Gremlin Account (Entitlements Graph)

Single account for the entitlements graph database:

```hcl
resource "azurerm_cosmosdb_account" "gremlin" {
  name                = "${local.cluster_name}-graph"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  kind                = "GlobalDocumentDB"
  offer_type          = "Standard"

  capabilities { name = "EnableGremlin" }

  consistency_policy {
    consistency_level = "Session"
  }

  geo_location {
    location          = var.location
    failover_priority = 0
  }
}
```

### SQL Accounts (Per-Partition)

One CosmosDB SQL account per data partition, each with 24 containers:

```hcl
resource "azurerm_cosmosdb_account" "sql" {
  for_each = local.partitions

  name                = "${local.cluster_name}-${each.key}"
  resource_group_name = azurerm_resource_group.main.name
  location            = var.location
  kind                = "GlobalDocumentDB"
  offer_type          = "Standard"

  consistency_policy {
    consistency_level = "Session"
  }
}
```

### Container Definitions (from locals.tf)

| Container | Partition Key | Used By |
|-----------|--------------|---------|
| Authority | /id | Schema |
| EntityType | /id | Schema |
| FileLocationEntity | /id | File |
| IngestionStrategy | /workflowType | Workflow |
| LegalTag | /id | Legal |
| MappingInfo | /sourceSchemaKind | Storage |
| RegisterAction | /dataPartitionId | Register |
| RegisterDdms | /dataPartitionId | Register |
| RegisterSubscription | /dataPartitionId | Register |
| RelationshipStatus | /id | Storage |
| ReplayStatus | /id | Indexer |
| SchemaInfo | /partitionId | Schema |
| Source | /id | Schema |
| StorageRecord | /id | Storage |
| StorageSchema | /kind | Storage |
| TenantInfo | /id | Partition |
| UserInfo | /id | Entitlements |
| Workflow | /workflowId | Workflow |
| WorkflowCustomOperatorInfo | /operatorId | Workflow |
| WorkflowCustomOperatorV2 | /partitionKey | Workflow |
| WorkflowRun | /partitionKey | Workflow |
| WorkflowRunV2 | /partitionKey | Workflow |
| WorkflowRunStatus | /partitionKey | Workflow |
| WorkflowV2 | /partitionKey | Workflow |

### System Database Containers (Primary Partition Only)

| Container | Partition Key |
|-----------|--------------|
| Authority | /id |
| EntityType | /id |
| SchemaInfo | /partitionId |
| Source | /id |
| WorkflowV2 | /partitionKey |

### Flatten Pattern

```hcl
# Partition x container → flat map for for_each
locals {
  partition_db_containers = merge([
    for p in var.data_partitions : {
      for name, spec in local.osdu_db_containers :
      "${p}/${name}" => {
        partition     = p
        container     = name
        partition_key = spec.partition_key
      }
    }
  ]...)
}
```

## Service Bus

### Topic Definitions (Per-Partition)

14 topics per partition namespace:

| Topic | Max Size | Subscriptions |
|-------|----------|--------------|
| indexing-progress | 1024 MB | indexing-progresssubscription |
| legaltags | 1024 MB | legaltagssubscription |
| recordstopic | 1024 MB | recordstopicsubscription, wkssubscription |
| recordstopicdownstream | 1024 MB | downstreamsub |
| recordstopiceg | 1024 MB | eg_sb_wkssubscription |
| schemachangedtopic | 1024 MB | schemachangedtopicsubscription |
| schemachangedtopiceg | 1024 MB | eg_sb_schemasubscription |
| legaltagschangedtopiceg | 1024 MB | eg_sb_legaltagssubscription |
| statuschangedtopic | 5120 MB | statuschangedtopicsubscription |
| statuschangedtopiceg | 1024 MB | eg_sb_statussubscription |
| recordstopic-v2 | 1024 MB | recordstopic-v2-subscription |
| reindextopic | 1024 MB | reindextopicsubscription |
| entitlements-changed | 1024 MB | (none) |
| replaytopic | 1024 MB | replaytopicsubscription |

All subscriptions use `max_delivery_count = 5` and `lock_duration = PT5M`.

### Flatten Pattern

Same triple-nested pattern as CosmosDB:
```hcl
locals {
  partition_sb_topics = merge([
    for p in var.data_partitions : {
      for name, spec in local.servicebus_topics :
      "${p}/${name}" => { partition = p, topic = name, max_size = spec.max_size }
    }
  ]...)
}
```

## Azure Storage

### Common Account Containers

| Container | Purpose |
|-----------|---------|
| system | System configuration data |
| azure-webjobs-hosts | WebJobs runtime metadata |
| azure-webjobs-eventhub | Event Hub checkpoint data |
| airflow-logs | Airflow task logs |
| airflow-dags | Airflow DAG definitions |
| share-unit | Unit service conversion data |
| share-crs | CRS catalog data |
| share-crs-conversion | CRS conversion definitions |

### Per-Partition Account Containers

| Container | Purpose |
|-----------|---------|
| legal-service-azure-configuration | Legal tag compliance rules |
| osdu-wks-mappings | WKS type mapping definitions |
| wdms-osdu | WDMS data store |
| file-staging-area | Temporary file upload staging |
| file-persistent-area | Permanent file storage |

## Key Vault

Single vault per deployment. Stores:
- CosmosDB connection strings (per partition)
- Service Bus connection strings (per partition)
- Storage account keys
- SSL certificates
- Airflow Fernet key
- Redis password

Accessed via Workload Identity — no CSI secret store driver needed.

## Workload Identity Federation

8 federated credentials, one per namespace:

```hcl
locals {
  federated_credentials = {
    "federated-ns-default"        = "system:serviceaccount:default:workload-identity-sa"
    "federated-ns-osdu-core"      = "system:serviceaccount:osdu-core:workload-identity-sa"
    "federated-ns-airflow"        = "system:serviceaccount:airflow:workload-identity-sa"
    "federated-ns-osdu-system"    = "system:serviceaccount:osdu-system:workload-identity-sa"
    "federated-ns-osdu-auth"      = "system:serviceaccount:osdu-auth:workload-identity-sa"
    "federated-ns-osdu-reference" = "system:serviceaccount:osdu-reference:workload-identity-sa"
    "federated-ns-osdu"           = "system:serviceaccount:osdu:workload-identity-sa"
    "federated-ns-platform"       = "system:serviceaccount:platform:workload-identity-sa"
  }
}
```

Each namespace's ServiceAccount gets the annotation:
```yaml
azure.workload.identity/client-id: <managed-identity-client-id>
```
