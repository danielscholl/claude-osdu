# Multi-Partition Support

SPI infrastructure supports N data partitions via Terraform `for_each` patterns.

## Configuration

```hcl
variable "data_partitions" {
  description = "List of OSDU data partition names"
  type        = list(string)
  default     = ["opendes"]
}
```

Set via azd:
```bash
azd env set TF_VAR_data_partitions '["opendes","partner"]'
```

## What Each Partition Gets

| Resource | Naming Pattern | Count per Partition |
|----------|---------------|-------------------|
| CosmosDB SQL account | `spi-<env>-<partition>` | 1 |
| CosmosDB SQL database | `osdu-db` | 1 |
| CosmosDB containers | (24 names) | 24 |
| Service Bus namespace | `spi-<env>-<partition>-bus` | 1 |
| Service Bus topics | (14 names) | 14 |
| Storage account | `spi<env><partition>` | 1 |
| Storage containers | (5 names) | 5 |

## Primary Partition

The first partition in the list hosts the **system database**:

```hcl
locals {
  primary_partition = var.data_partitions[0]
}
```

System containers (Authority, EntityType, SchemaInfo, Source, WorkflowV2) are created
only on the primary partition's CosmosDB account.

## Terraform Patterns

### Per-Partition Resources

```hcl
resource "azurerm_cosmosdb_account" "sql" {
  for_each = toset(var.data_partitions)
  name     = "${local.cluster_name}-${each.key}"
  # ...
}
```

### Partition x Resource Flattening

When a resource has per-partition instances AND per-instance sub-resources (e.g.,
partition → topic → subscription), use a triple-nested flatten:

```hcl
locals {
  partition_sb_subscriptions = merge([
    for p in var.data_partitions : merge([
      for tname, tspec in local.servicebus_topics : {
        for sname, sspec in tspec.subscriptions :
        "${p}/${tname}/${sname}" => {
          partition    = p
          topic        = tname
          subscription = sname
        }
      }
    ]...)
  ]...)
}
```

Key format: `"<partition>/<topic>/<subscription>"` enables unique for_each keys.

### Primary-Only Resources

```hcl
resource "azurerm_cosmosdb_sql_container" "system" {
  for_each = local.system_db_containers
  # These are only created on the primary partition's account
  account_name = azurerm_cosmosdb_account.sql[local.primary_partition].name
}
```

## Adding a New Partition

1. Add the partition name to `data_partitions`:
   ```bash
   azd env set TF_VAR_data_partitions '["opendes","newpartition"]'
   ```
2. Run `azd provision` — Terraform creates all per-partition resources
3. The OSDU Partition service must also be configured to recognize the new partition
   (this is a service-level operation, not infrastructure)

## Removing a Partition

**Warning:** Removing a partition from the list will destroy its CosmosDB account,
Service Bus namespace, and Storage account. This is irreversible.

1. Back up any data in the partition's resources
2. Remove the partition name from `data_partitions`
3. Run `azd provision` — Terraform destroys the partition's resources
