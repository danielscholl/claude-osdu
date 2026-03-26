# Azure Verified Modules (AVM) Patterns

> **Part of:** [terraform skill](../SKILL.md)
> **Purpose:** Detailed guidance on using Azure Verified Modules in Terraform

---

## Table of Contents

1. [Module Discovery](#module-discovery)
2. [Module Usage Patterns](#module-usage-patterns)
3. [Required Interfaces](#required-interfaces)
4. [Version Management](#version-management)
5. [Common AVM Modules](#common-avm-modules)

---

## Module Discovery

### Finding AVM Modules

1. **AVM Index:** https://azure.github.io/Azure-Verified-Modules/indexes/terraform/
2. **Terraform Registry:** Search `Azure/avm-` in the registry
3. **GitHub:** Repositories under `Azure/terraform-azurerm-avm-*`

### Module Naming

```
Registry:  Azure/avm-res-{provider}-{type}/azurerm
GitHub:    Azure/terraform-azurerm-avm-res-{provider}-{type}
```

**Resource modules** (`avm-res-*`): Single Azure resource with full interface support
**Pattern modules** (`avm-ptn-*`): Multi-resource solutions combining AVM resource modules

### When No AVM Module Exists

If an AVM module doesn't exist for your resource:
1. Check if it's in "Proposed" status on the AVM index
2. Use `azurerm_*` resources directly following AVM conventions
3. Consider `azapi_resource` for brand-new Azure features
4. Never use non-AVM community modules when an AVM exists

---

## Module Usage Patterns

### Basic Usage

```hcl
module "resource_group" {
  source  = "Azure/avm-res-resources-resourcegroup/azurerm"
  version = "0.2.1"

  name     = "rg-${var.project}-${var.environment}-${var.location}"
  location = var.location
  tags     = var.tags
}
```

### With Full Interface

```hcl
module "keyvault" {
  source  = "Azure/avm-res-keyvault-vault/azurerm"
  version = "0.10.0"

  name                = "kv-${var.project}-${var.environment}"
  resource_group_name = module.resource_group.name
  location            = var.location
  tenant_id           = data.azurerm_client_config.current.tenant_id

  # Managed Identity
  managed_identities = {
    system_assigned = true
  }

  # Diagnostic Settings
  diagnostic_settings = {
    to_law = {
      workspace_resource_id = module.log_analytics.resource_id
      name                  = "diag-keyvault"
    }
  }

  # Role Assignments
  role_assignments = {
    admin = {
      role_definition_id_or_name = "Key Vault Administrator"
      principal_id               = data.azurerm_client_config.current.object_id
    }
  }

  # Lock
  lock = var.environment == "prod" ? {
    kind = "CanNotDelete"
    name = "nodelete-keyvault"
  } : null

  # Private Endpoints
  private_endpoints = var.enable_private_endpoints ? {
    vault = {
      subnet_resource_id            = module.vnet.subnets["private-endpoints"].resource_id
      subresource_name              = "vault"
      private_dns_zone_resource_ids = [module.private_dns_keyvault.resource_id]
    }
  } : {}

  tags = var.tags
}
```

### Composing Modules

```hcl
# Pattern: Infrastructure module composing AVM resource modules
module "aks" {
  source  = "Azure/avm-res-containerservice-managedcluster/azurerm"
  version = "0.5.2"

  name                = "aks-${var.project}-${var.environment}"
  resource_group_name = module.resource_group.name
  location            = var.location

  managed_identities = {
    system_assigned = true
  }

  diagnostic_settings = {
    to_law = {
      workspace_resource_id = module.log_analytics.resource_id
    }
  }

  tags = var.tags
}

# Cross-module reference pattern
module "acr" {
  source  = "Azure/avm-res-containerregistry-registry/azurerm"
  version = "0.6.0"

  name                = "acr${var.project}${var.environment}"
  resource_group_name = module.resource_group.name
  location            = var.location

  role_assignments = {
    aks_pull = {
      role_definition_id_or_name = "AcrPull"
      principal_id               = module.aks.cluster_identity.principal_id
    }
  }

  tags = var.tags
}
```

---

## Required Interfaces

### Tags

```hcl
variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default     = null
}
```

Tags propagate automatically to child, extension, and cross-referenced resources.

### Managed Identities

```hcl
variable "managed_identities" {
  description = "Managed identity configuration"
  type = object({
    system_assigned            = optional(bool, false)
    user_assigned_resource_ids = optional(set(string), [])
  })
  default = {}
}
```

### Diagnostic Settings

```hcl
variable "diagnostic_settings" {
  description = "Diagnostic settings destinations"
  type = map(object({
    name                                     = optional(string)
    log_categories                           = optional(set(string))
    log_groups                               = optional(set(string))
    metric_categories                        = optional(set(string))
    workspace_resource_id                    = optional(string)
    storage_account_resource_id              = optional(string)
    event_hub_authorization_rule_resource_id = optional(string)
    marketplace_partner_resource_id          = optional(string)
  }))
  default = {}
}
```

Do not hardcode allowed log/metric categories - AVM modules handle this dynamically.

### Role Assignments

```hcl
variable "role_assignments" {
  description = "RBAC role assignments on this resource"
  type = map(object({
    role_definition_id_or_name             = string
    principal_id                           = string
    description                            = optional(string)
    skip_service_principal_aad_check       = optional(bool, false)
    condition                              = optional(string)
    condition_version                      = optional(string)
    delegated_managed_identity_resource_id = optional(string)
    principal_type                         = optional(string)
  }))
  default = {}
}
```

### Lock

```hcl
variable "lock" {
  description = "Resource lock configuration"
  type = object({
    kind = string  # "CanNotDelete" or "ReadOnly"
    name = optional(string)
  })
  default = null
}
```

### Private Endpoints

```hcl
variable "private_endpoints" {
  description = "Private endpoint configuration"
  type = map(object({
    subnet_resource_id            = string
    subresource_name              = string
    private_dns_zone_resource_ids = optional(set(string), [])
    name                          = optional(string)
    tags                          = optional(map(string))
    role_assignments              = optional(map(object({...})))
    lock                          = optional(object({...}))
  }))
  default = {}
}
```

### Customer Managed Key

```hcl
variable "customer_managed_key" {
  description = "Customer managed key for encryption"
  type = object({
    key_vault_resource_id = string
    key_name              = string
    key_version           = optional(string)
    user_assigned_identity = optional(object({
      resource_id = string
    }))
  })
  default = null
}
```

---

## Version Management

### Pinning Strategy

```hcl
# Pin AVM modules to exact version in production
module "vnet" {
  source  = "Azure/avm-res-network-virtualnetwork/azurerm"
  version = "0.17.1"  # Exact version for stability
}

# Allow patch updates in development
module "vnet" {
  source  = "Azure/avm-res-network-virtualnetwork/azurerm"
  version = "~> 0.17"  # Any 0.17.x
}
```

### Updating Modules

1. Check the AVM index for latest versions
2. Review the module's CHANGELOG on GitHub
3. Update version in code
4. Run `terraform init -upgrade`
5. Run `terraform plan` to review changes
6. Test in dev before promoting to prod

---

## Common AVM Modules

| Module | Registry Name | Use Case |
|--------|--------------|----------|
| Resource Group | `avm-res-resources-resourcegroup` | Resource grouping |
| Virtual Network | `avm-res-network-virtualnetwork` | Networking |
| AKS | `avm-res-containerservice-managedcluster` | Kubernetes clusters |
| Key Vault | `avm-res-keyvault-vault` | Secrets & certificates |
| Storage Account | `avm-res-storage-storageaccount` | Object/blob storage |
| Container Registry | `avm-res-containerregistry-registry` | Container images |
| Log Analytics | `avm-res-operationalinsights-workspace` | Monitoring |
| PostgreSQL Flexible | `avm-res-dbforpostgresql-flexibleserver` | Managed PostgreSQL |
| Cosmos DB | `avm-res-documentdb-databaseaccount` | NoSQL database |
| Service Bus | `avm-res-servicebus-namespace` | Messaging |

Browse the full index at: https://azure.github.io/Azure-Verified-Modules/indexes/terraform/tf-resource-modules/

---

**Back to:** [Main Skill File](../SKILL.md)
