# Helm & Kustomize via Terraform

> **Part of:** [terraform skill](../SKILL.md)
> **Purpose:** Patterns for deploying Helm charts and Kustomize overlays through Terraform

---

## Table of Contents

1. [Provider Setup for AKS](#provider-setup-for-aks)
2. [Helm Release Patterns](#helm-release-patterns)
3. [Kustomize Postrender](#kustomize-postrender)
4. [AKS Safeguards Compliance](#aks-safeguards-compliance)
5. [Kubernetes Resources via Terraform](#kubernetes-resources-via-terraform)
6. [Common Patterns](#common-patterns)

---

## Provider Setup for AKS

### Authentication to AKS

```hcl
# versions.tf
terraform {
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    kubectl = {
      source  = "alekc/kubectl"
      version = "~> 2.0"
    }
  }
}
```

### Using AKS Credentials (Platform Layer)

```hcl
# provider.tf - Platform layer gets AKS details from env vars
provider "helm" {
  kubernetes {
    host                   = var.aks_host
    cluster_ca_certificate = base64decode(var.aks_cluster_ca_certificate)

    # Option 1: Client certificate auth
    client_certificate = base64decode(var.aks_client_certificate)
    client_key         = base64decode(var.aks_client_key)

    # Option 2: Exec-based auth (kubelogin)
    # exec {
    #   api_version = "client.authentication.k8s.io/v1beta1"
    #   command     = "kubelogin"
    #   args        = ["get-token", "--login", "azurecli", "--server-id", "6dae42f8-4368-4678-94ff-3960e28e3630"]
    # }
  }
}

provider "kubernetes" {
  host                   = var.aks_host
  cluster_ca_certificate = base64decode(var.aks_cluster_ca_certificate)
  client_certificate     = base64decode(var.aks_client_certificate)
  client_key             = base64decode(var.aks_client_key)
}
```

---

## Helm Release Patterns

### Standard Chart Deployment

```hcl
resource "helm_release" "cert_manager" {
  count = var.enable_cert_manager ? 1 : 0

  name             = "cert-manager"
  repository       = "https://charts.jetstack.io"
  chart            = "cert-manager"
  version          = "1.14.4"
  namespace        = "cert-manager"
  create_namespace = true

  set {
    name  = "installCRDs"
    value = "true"
    type  = "string"
  }

  tags = var.tags
}
```

### Values File Pattern (Preferred)

Prefer `values` with `templatefile()` over many inline `set` blocks:

```hcl
resource "helm_release" "ingress_nginx" {
  count = var.enable_nginx_ingress ? 1 : 0

  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.9.1"
  namespace        = "ingress-nginx"
  create_namespace = true

  values = [
    templatefile("${path.module}/values/nginx-ingress.yaml", {
      replica_count       = var.ingress_replicas
      load_balancer_ip    = var.ingress_load_balancer_ip
      internal_lb         = var.ingress_internal
    })
  ]

  tags = var.tags
}
```

```yaml
# values/nginx-ingress.yaml
controller:
  replicaCount: ${replica_count}
  service:
    annotations:
      service.beta.kubernetes.io/azure-load-balancer-internal: "${internal_lb}"
    loadBalancerIP: "${load_balancer_ip}"
  resources:
    requests:
      cpu: 100m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 256Mi
```

### Helm Set Type Gotcha

When setting boolean values via `set`, always use `type = "string"`:

```hcl
# Correct - Helm receives the string "true"
set {
  name  = "controller.service.annotations.service\\.beta\\.kubernetes\\.io/azure-load-balancer-internal"
  value = "true"
  type  = "string"
}

# Wrong - Helm may misinterpret the type
set {
  name  = "someFlag"
  value = true  # Without type = "string", may cause issues
}
```

### OCI Registry Charts

```hcl
resource "helm_release" "eso" {
  count = var.enable_external_secrets ? 1 : 0

  name             = "external-secrets"
  repository       = "oci://ghcr.io/external-secrets/charts"
  chart            = "external-secrets"
  version          = "0.9.13"
  namespace        = "external-secrets"
  create_namespace = true
}
```

### Wait and Timeout

```hcl
resource "helm_release" "operator" {
  name    = "my-operator"
  chart   = "my-operator"

  wait          = true       # Wait for all resources to be ready (default: true)
  wait_for_jobs = true       # Also wait for Jobs to complete
  timeout       = 600        # Seconds (default: 300)

  # For CRD-heavy operators, sometimes you need to disable wait
  # wait = false
}
```

---

## Kustomize Postrender

### Why Postrender?

Third-party Helm charts often don't include fields required by AKS Deployment Safeguards. Postrender lets you inject these fields without forking the chart.

For the full list of AKS safeguard requirements and postrender examples, see [AKS Safeguards Reference](aks-safeguards.md).

### Postrender Script Pattern

```hcl
resource "helm_release" "eck_operator" {
  count = var.enable_eck ? 1 : 0

  name             = "elastic-operator"
  repository       = "https://helm.elastic.co"
  chart            = "eck-operator"
  version          = "2.12.1"
  namespace        = "elastic-system"
  create_namespace = true

  postrender {
    binary_path = "${path.module}/kustomize/eck-operator-postrender.sh"
  }
}
```

### Postrender Shell Script

```bash
#!/bin/bash
# kustomize/eck-operator-postrender.sh
set -euo pipefail
cat > /tmp/helm-input.yaml
kustomize build "${KUSTOMIZE_DIR:-./kustomize/eck-operator}" --load-restrictor=LoadRestrictionsNone
```

---

## Kubernetes Resources via Terraform

### Namespaces

```hcl
resource "kubernetes_namespace" "app" {
  metadata {
    name = var.app_namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
}
```

### Secrets from Key Vault

```hcl
# Create K8s secret from Azure Key Vault
data "azurerm_key_vault_secret" "app_secret" {
  name         = "app-connection-string"
  key_vault_id = var.key_vault_id
}

resource "kubernetes_secret" "app" {
  metadata {
    name      = "app-secrets"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    CONNECTION_STRING = data.azurerm_key_vault_secret.app_secret.value
  }

  type = "Opaque"
}
```

### ConfigMaps

```hcl
resource "kubernetes_config_map" "app" {
  metadata {
    name      = "app-config"
    namespace = kubernetes_namespace.app.metadata[0].name
  }

  data = {
    "config.yaml" = templatefile("${path.module}/configs/app.yaml", {
      environment = var.environment
      log_level   = var.log_level
    })
  }
}
```

---

## Common Patterns

### Dependency Ordering

```hcl
# CRDs must be installed before custom resources
resource "helm_release" "operator" {
  name  = "my-operator"
  chart = "my-operator-chart"
}

resource "helm_release" "operator_config" {
  name  = "my-operator-config"
  chart = "my-operator-config-chart"

  depends_on = [helm_release.operator]
}
```

### Feature Toggles

```hcl
variable "enable_monitoring" {
  description = "Deploy monitoring stack (Prometheus + Grafana)"
  type        = bool
  default     = true
}

resource "helm_release" "prometheus" {
  count = var.enable_monitoring ? 1 : 0
  # ...
}

resource "helm_release" "grafana" {
  count = var.enable_monitoring ? 1 : 0
  depends_on = [helm_release.prometheus]
  # ...
}
```

### Multiple Value Files

```hcl
resource "helm_release" "app" {
  name  = "my-app"
  chart = "./charts/my-app"

  # Base values + environment-specific overrides
  values = [
    file("${path.module}/values/base.yaml"),
    file("${path.module}/values/${var.environment}.yaml"),
  ]
}
```

---

**Back to:** [Main Skill File](../SKILL.md)
