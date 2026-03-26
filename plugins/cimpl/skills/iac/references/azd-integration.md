# azd + Terraform Integration

> **Part of:** [terraform skill](../SKILL.md)
> **Purpose:** Azure Developer CLI integration patterns for Terraform projects

---

## Table of Contents

1. [Project Setup](#project-setup)
2. [Environment Management](#environment-management)
3. [Variable Mapping](#variable-mapping)
4. [State Management](#state-management)
5. [Hooks and Scripts](#hooks-and-scripts)
6. [Key Commands](#key-commands)

---

## Project Setup

### azure.yaml

The project root must contain `azure.yaml` with Terraform configured:

```yaml
name: my-project
infra:
  provider: terraform
  path: infra          # Directory containing .tf files (default: infra)
  module: main         # Terraform module to use (default: main)
```

### Required Directory Structure

```
project-root/
+-- azure.yaml
+-- infra/
|   +-- main.tf
|   +-- variables.tf
|   +-- outputs.tf
|   +-- versions.tf
|   +-- provider.tf
|   +-- main.tfvars.json    # Default variable values
+-- .azure/
    +-- <env-name>/
        +-- .env            # Environment-specific values
        +-- infra/
            +-- terraform.tfstate  # Local state (if not using remote)
```

### Minimal main.tf for azd

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = ">= 4.0, < 5.0"
    }
  }
}

provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
}

# azd always provides these variables
variable "environment_name" {
  description = "Name of the azd environment"
  type        = string
}

variable "location" {
  description = "Azure region for resources"
  type        = string
}

variable "subscription_id" {
  description = "Azure subscription ID"
  type        = string
}
```

---

## Environment Management

### Creating Environments

```bash
# Create a new environment
azd env new dev

# Set environment-specific values
azd env set RS_STORAGE_ACCOUNT mystorageaccount
azd env set RS_CONTAINER_NAME tfstate
azd env set RS_RESOURCE_GROUP rg-terraform-state

# Switch environments
azd env select staging

# List environments
azd env list

# Refresh environment from Azure
azd env refresh -e dev
```

### Environment Variables

azd automatically maps certain values to Terraform variables via `TF_VAR_*`:

| azd Variable | Terraform Variable | Source |
|-------------|-------------------|--------|
| `AZURE_ENV_NAME` | `var.environment_name` | `azd env new` |
| `AZURE_LOCATION` | `var.location` | `azd env set` or prompt |
| `AZURE_SUBSCRIPTION_ID` | `var.subscription_id` | `az account show` |

Custom variables set via `azd env set KEY value` are available as environment variables in hooks.

---

## Variable Mapping

### main.tfvars.json

Default variable values for all environments:

```json
{
  "resource_group_name": "rg-${AZURE_ENV_NAME}",
  "aks_node_count": 3,
  "aks_vm_size": "Standard_D4s_v5"
}
```

azd substitutes `${AZURE_ENV_NAME}` and other env vars before passing to Terraform.

### Outputs

Terraform outputs are captured by azd and stored in `.azure/<env>/.env`:

```hcl
# outputs.tf
output "AKS_CLUSTER_NAME" {
  description = "AKS cluster name for platform layer"
  value       = module.aks.name
}

output "AKS_HOST" {
  description = "AKS API server endpoint"
  value       = module.aks.host
  sensitive   = true
}

output "ACR_LOGIN_SERVER" {
  description = "Container registry login server"
  value       = module.acr.login_server
}
```

Output names become environment variable names. Use UPPER_SNAKE_CASE for consistency with shell conventions.

---

## State Management

### Local State (Default)

azd stores state at `.azure/<env>/infra/terraform.tfstate`. Simple for development, not suitable for teams.

### Remote State (Azure Storage)

**Step 1:** Create storage account for state (outside this project):

```bash
az group create -n rg-terraform-state -l eastus2
az storage account create -n stterraformstate -g rg-terraform-state -l eastus2 --sku Standard_LRS
az storage container create -n tfstate --account-name stterraformstate
```

**Step 2:** Configure backend in `provider.tf`:

```hcl
terraform {
  backend "azurerm" {}
}
```

**Step 3:** Create `infra/provider.conf.json`:

```json
{
  "storage_account_name": "${RS_STORAGE_ACCOUNT}",
  "container_name": "${RS_CONTAINER_NAME}",
  "key": "azd/${AZURE_ENV_NAME}.tfstate",
  "resource_group_name": "${RS_RESOURCE_GROUP}"
}
```

**Step 4:** Set env vars:

```bash
azd env set RS_STORAGE_ACCOUNT stterraformstate
azd env set RS_CONTAINER_NAME tfstate
azd env set RS_RESOURCE_GROUP rg-terraform-state
```

azd detects `provider.conf.json` and passes `-backend-config` to `terraform init`.

---

## Hooks and Scripts

### azd Hooks

azd supports pre/post hooks for lifecycle events:

```yaml
# azure.yaml
hooks:
  preprovision:
    shell: pwsh
    run: scripts/pre-provision.ps1
  postprovision:
    shell: pwsh
    run: scripts/post-provision.ps1
```

### Common Hook Patterns

**Post-provision: Deploy platform layer**

```powershell
# scripts/post-provision.ps1
$ErrorActionPreference = "Stop"

# Platform layer uses infra outputs as inputs
Push-Location platform
terraform init
terraform apply -auto-approve -var-file="../.azure/$env:AZURE_ENV_NAME/platform.tfvars"
Pop-Location
```

**Post-provision: Configure kubectl**

```powershell
# scripts/configure-kubectl.ps1
$ErrorActionPreference = "Stop"

$clusterName = $env:AKS_CLUSTER_NAME
$resourceGroup = $env:AZURE_RESOURCE_GROUP

az aks get-credentials --resource-group $resourceGroup --name $clusterName --overwrite-existing
if ($LASTEXITCODE -ne 0) { throw "Failed to get AKS credentials" }
```

---

## Key Commands

| Command | Description |
|---------|-------------|
| `azd init` | Initialize project from template |
| `azd provision` | Run terraform init/plan/apply |
| `azd deploy` | Deploy application code |
| `azd up` | provision + deploy in one step |
| `azd down` | Destroy all provisioned resources |
| `azd env new <name>` | Create new environment |
| `azd env set <key> <value>` | Set environment variable |
| `azd env get-values` | Show all env values |
| `azd env refresh` | Refresh env from deployed resources |

### Troubleshooting

**"Backend configuration changed"**: Delete `.azure/<env>/infra/.terraform` and re-run `azd provision`.

**State lock errors**: Check if another process is running. Use `terraform force-unlock <lock-id>` only as last resort.

**Variable not found**: Ensure variables are defined in `variables.tf` and mapped correctly in `main.tfvars.json` or via `azd env set`.

---

**Back to:** [Main Skill File](../SKILL.md)
