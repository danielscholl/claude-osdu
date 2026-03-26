---
name: iac
allowed-tools: Bash, Read, Glob, Grep, Edit, Write
description: >-
  Infrastructure as Code for Azure — Terraform modules, Azure Verified Modules (AVM),
  Helm/Kustomize deployments, AKS Deployment Safeguards, azd integration, and
  systematic debugging.
  Use when working with Terraform, AVM, azurerm, azapi,
  helm_release, kubernetes_manifest, AKS safeguards, deployment failures, policy
  violations, infrastructure verification, or any IaC architecture decisions.
  Also use for debugging infrastructure issues and verifying deployments are complete.
  Not for: application code, OSDU service APIs, CI/CD pipeline execution, or
  project-specific setup (use the setup skill for missing CLI tools).
---

# Infrastructure as Code

Terraform, Helm, and Kubernetes infrastructure for Azure, with systematic debugging
and evidence-based verification.

## Quick Start

Before first use, verify tools are available:
```bash
terraform --version && helm version --short && kubectl version --client
```
If any command is not found, **stop and use the `setup` skill** to install missing dependencies.
Do NOT attempt to install tools yourself — the setup skill handles installation with the correct
sources, user approval, and verification.

If installed, go straight to the section you need below.

## Project Architecture

Two-layer Terraform architecture managed by azd:

```
project-root/
├── azure.yaml              # azd project definition
├── infra/                  # Layer 1: Azure infrastructure (azd-managed)
│   ├── main.tf             # Root module — calls AVM modules
│   ├── variables.tf        # Input variables
│   ├── outputs.tf          # Outputs consumed by platform layer
│   ├── versions.tf         # Provider version constraints
│   ├── provider.tf         # Provider configuration + backend
│   └── modules/            # Local modules wrapping AVM
├── platform/               # Layer 2: Kubernetes workloads
│   ├── main.tf             # Helm releases, K8s resources
│   └── kustomize/          # Postrender overlays
└── scripts/                # PowerShell automation (azd hooks)
```

**Key separation:**
- **infra/** — Azure resources (AKS, networking, storage). State managed by azd.
- **platform/** — Kubernetes workloads (Helm charts, operators). Local state.
- Cross-layer values flow through environment variables, never direct state references.

---

## Terraform Patterns

### Azure Verified Modules (AVM)

Always prefer AVM over hand-written resources:

```hcl
module "aks" {
  source  = "Azure/avm-res-containerservice-managedcluster/azurerm"
  version = "0.5.2"

  name                = "aks-${var.environment}"
  resource_group_name = azurerm_resource_group.this.name
  location            = var.location
  managed_identities  = { system_assigned = true }
  tags                = var.tags
}
```

AVM standard interfaces: `tags`, `managed_identities`, `diagnostic_settings`,
`role_assignments`, `lock`, `private_endpoints`, `customer_managed_key`.

**For detailed AVM patterns:** [references/avm-patterns.md](references/avm-patterns.md)

### Provider Configuration

```hcl
terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = ">= 4.0, < 5.0" }
    azapi   = { source = "Azure/azapi", version = ">= 2.0, < 3.0" }
  }
}
```

Use `azapi` for day-zero resources or features not yet in azurerm.

### Code Standards

**Resource block ordering:** count/for_each → required args → optional args → tags → depends_on → lifecycle

**Naming:** `azurerm_resource_group.this` (singleton), `var.resource_group_name`, underscores not hyphens.

**Count vs for_each:** count for boolean toggles, for_each for named collections.

### azd Integration

```yaml
# azure.yaml
name: my-project
infra:
  provider: terraform
```

azd runs `terraform init/plan/apply`, passes env vars as `TF_VAR_*`, stores state at `.azure/<env>/infra/terraform.tfstate`.

**For complete azd details:** [references/azd-integration.md](references/azd-integration.md)

---

## Helm & Kustomize

### Helm Release Pattern

```hcl
resource "helm_release" "nginx_ingress" {
  count            = var.enable_nginx_ingress ? 1 : 0
  name             = "ingress-nginx"
  repository       = "https://kubernetes.github.io/ingress-nginx"
  chart            = "ingress-nginx"
  version          = "4.8.3"
  namespace        = "ingress-nginx"
  create_namespace = true

  values = [templatefile("${path.module}/values/nginx-ingress.yaml", {
    replica_count = var.ingress_replicas
  })]
}
```

### Postrender + Kustomize for AKS Safeguards

Charts that don't expose safeguard fields need postrender:

```hcl
resource "helm_release" "operator" {
  name  = "my-operator"
  chart = "my-operator"
  postrender {
    binary_path = "${path.module}/kustomize/postrender.sh"
  }
}
```

**For complete Helm/Kustomize patterns:** [references/helm-kustomize.md](references/helm-kustomize.md)

---

## AKS Deployment Safeguards

AKS Automatic enforces safeguards that **cannot be bypassed**. All workloads must comply:

| Requirement | Applies to |
|-------------|-----------|
| `readinessProbe` + `livenessProbe` | ALL containers |
| `resources.requests` (cpu + memory) | ALL containers |
| Specific image tag (no `:latest`) | ALL containers |
| `seccompProfile: RuntimeDefault` | Pod spec |
| `topologySpreadConstraints` or `podAntiAffinity` | Replicas > 1 |
| No privileged containers | ALL pods |

**What does NOT work:** `az aks safeguards update --level Warn`, namespace exclusions, policy exemptions, Gatekeeper constraint modifications.

**For detailed safeguards:** [references/aks-safeguards.md](references/aks-safeguards.md)

---

## Debugging Infrastructure Issues

### The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

Quick fixes mask deeper problems. A "working" deployment you don't understand will break again.

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
terraform state list
terraform plan 2>&1 | tee plan-output.txt

# Kubernetes state
kubectl get pods -A | grep -v Running
kubectl describe pod <failing-pod> -n <namespace>

# AKS Safeguards
kubectl get constraints -o wide

# Azure Activity Log
az monitor activity-log list --resource-group <rg> --status Failed --max-events 10
```

### Phase 2: Check Recent Changes

```bash
git log --oneline -10
git diff HEAD~3 -- infra/ platform/ scripts/
helm history <release> -n <namespace>
```

### Phase 3: Form and Test Hypothesis

> "The deployment fails because [specific cause] which results in [observed symptom]"

Change ONE variable at a time. Use `terraform plan` before `apply`. If 3+ hypotheses fail, question your architecture.

### Red Flags

| Thought | Reality |
|---------|---------|
| "Let me just try this quick fix" | You don't understand the problem |
| "I'll add a retry/sleep" | You're masking the real issue |
| "This is the 4th thing I've tried" | Step back, question architecture |

### Common Issues

| Issue | Investigation | Root cause |
|-------|--------------|------------|
| Pods stuck Pending | `kubectl get constraints -o wide` | Missing probes, resources, or anti-affinity |
| "Resource already exists" | `terraform state list` | Manual changes outside Terraform |
| Helm stuck pending-install | `helm history <release>` | Failed previous install, needs rollback |
| Gatekeeper not ready | `kubectl get pods -n gatekeeper-system` | Azure Policy eventual consistency |

---

## Verifying Deployments

### The Iron Law

```
NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE
```

"Terraform apply succeeded" does not mean it works. "No errors" does not mean correct.

### Verification Process

```
1. IDENTIFY  → What command(s) prove this claim?
2. RUN       → Execute the command(s) fresh
3. READ      → Full output, check exit codes
4. VERIFY    → Does output actually confirm the claim?
5. ONLY THEN → Make the claim with evidence
```

### Verification Commands

```bash
# Cluster health
kubectl get nodes                                    # All Ready
kubectl get pods -A | grep -v Running | grep -v Completed  # Should be empty
kubectl get constraints -o wide                      # 0 violations

# Terraform state
terraform plan                                       # No unexpected changes
terraform output                                     # Values correct

# Pre-PR checks
terraform fmt -check -recursive ./infra
terraform fmt -check -recursive ./platform
```

### Checklist by Task Type

**After deploying:** pods Running, 0 constraint violations, component health check, logs clean.

**After fixing a bug:** original error gone, no new errors, related components still work.

**Before creating PR:** fmt passes, no secrets in code, docs updated, all components healthy.

---

## Reference Guides

- [AVM Patterns](references/avm-patterns.md) — Module interfaces, usage, version management
- [azd Integration](references/azd-integration.md) — Project setup, environments, state
- [Helm & Kustomize](references/helm-kustomize.md) — Chart deployments, postrender, providers
- [AKS Safeguards](references/aks-safeguards.md) — Compliance rules, probes, constraints
- [GitLab CI](references/gitlab-ci.md) — Pipeline templates, environment promotion
