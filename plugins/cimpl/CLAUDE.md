# CIMPL Infrastructure Plugin

## Scope

The @cimpl agent is the infrastructure specialist for the `cimpl-azure-provisioning` repository.

**Handles:** Terraform, Helm, Kustomize, AKS Safeguards, azd provisioning, deployment debugging, verification.

**Does NOT handle:** OSDU platform services, GitLab analytics, QA testing, dependency management. Those belong to the osdu plugin.

## Deployment Layers

| Layer | Path | Technology |
|-------|------|-----------|
| L1 — Infrastructure | `infra/` | Terraform + AVM modules |
| L2 — Platform foundation | `infra/` | Terraform (identities, networking) |
| L3 — Software stack | `software/` | Helm + Kustomize |

## Quality Checks

Before shipping infrastructure changes:
- `terraform fmt -check` on all `.tf` files
- `helm lint` on chart directories
- `kustomize build` for overlay validation
