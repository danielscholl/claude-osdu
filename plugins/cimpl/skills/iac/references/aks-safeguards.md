# AKS Deployment Safeguards

> **Part of:** [terraform skill](../SKILL.md)
> **Purpose:** Non-negotiable compliance rules for AKS Automatic clusters

AKS Automatic clusters enforce Deployment Safeguards that cannot be bypassed, relaxed, or excluded by namespace. Make workloads compliant - do not attempt to bypass.

---

## Table of Contents

1. [Compliance Requirements](#compliance-requirements)
2. [Probe Patterns](#probe-patterns)
3. [Resource Requests](#resource-requests)
4. [Security Context](#security-context)
5. [Pod Distribution](#pod-distribution)
6. [Helm Chart Compliance](#helm-chart-compliance)
7. [Postrender Pattern](#postrender-pattern)
8. [Checking Compliance](#checking-compliance)
9. [Common Issues](#common-issues)
10. [Constraint Reference](#constraint-reference)

---

## Compliance Requirements

Every container/pod deployed to AKS Automatic must meet these requirements:

| Requirement | Status | Applies To |
|-------------|--------|-----------|
| `readinessProbe` | Required | ALL containers |
| `livenessProbe` | Required | ALL containers |
| `resources.requests` | Required | ALL containers |
| Specific image tag | Required (no `:latest`) | ALL containers |
| `seccompProfile: RuntimeDefault` | Required | Pod spec |
| Anti-affinity | Required (if replicas > 1) | Pod spec |
| `runAsNonRoot` | Required | Pod security context |
| No privileged containers | Required | ALL pods |
| No `NET_ADMIN`/`NET_RAW` | Required | ALL containers |
| No `hostNetwork: true` | Required | ALL pods |
| No `hostPID: true` | Required | ALL pods |
| Unique service selectors | Required | ALL services |

---

## Probe Patterns

ALL containers must have both `readinessProbe` and `livenessProbe`. Init containers are exempt.

### HTTP Probes (most common)

```yaml
containers:
  - name: my-container
    readinessProbe:
      httpGet:
        path: /healthz
        port: 8080
      initialDelaySeconds: 10
      periodSeconds: 5
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      initialDelaySeconds: 15
      periodSeconds: 10
```

### Exec Probes (for containers without HTTP)

```yaml
readinessProbe:
  exec:
    command:
      - cat
      - /tmp/healthy
  initialDelaySeconds: 5
  periodSeconds: 5
livenessProbe:
  exec:
    command:
      - cat
      - /tmp/healthy
  initialDelaySeconds: 15
  periodSeconds: 10
```

### TCP Probes (for database/network services)

```yaml
readinessProbe:
  tcpSocket:
    port: 5432
  initialDelaySeconds: 10
  periodSeconds: 5
livenessProbe:
  tcpSocket:
    port: 5432
  initialDelaySeconds: 15
  periodSeconds: 10
```

---

## Resource Requests

ALL containers must specify resource requests. Limits are optional but recommended.

```yaml
containers:
  - name: my-container
    resources:
      requests:
        memory: "128Mi"
        cpu: "100m"
      limits:           # Optional but recommended
        memory: "256Mi"
        cpu: "200m"
```

### Minimum Viable Requests

For lightweight sidecars or utility containers:

```yaml
resources:
  requests:
    memory: "64Mi"
    cpu: "10m"
```

---

## Security Context

### Pod-Level Security

```yaml
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault
```

### Container-Level Security

```yaml
containers:
  - name: my-container
    securityContext:
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true  # If possible
      capabilities:
        drop:
          - ALL
```

### Image Tags

```yaml
# WRONG
image: nginx:latest
image: myrepo/myimage        # No tag = latest

# CORRECT
image: nginx:1.25.3
image: myrepo/myimage:v1.2.3
image: myrepo/myimage@sha256:abc123...
```

---

## Pod Distribution

Deployments with replicas > 1 must spread across nodes.

### Option A: topologySpreadConstraints (preferred)

```yaml
spec:
  topologySpreadConstraints:
    - maxSkew: 1
      topologyKey: kubernetes.io/hostname
      whenUnsatisfiable: ScheduleAnyway
      labelSelector:
        matchLabels:
          app: my-app
```

### Option B: podAntiAffinity

```yaml
spec:
  affinity:
    podAntiAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          podAffinityTerm:
            labelSelector:
              matchLabels:
                app: my-app
            topologyKey: kubernetes.io/hostname
```

---

## Helm Chart Compliance

### Setting Values in Terraform

```hcl
resource "helm_release" "my_app" {
  name       = "my-app"
  repository = "https://charts.example.com"
  chart      = "my-app"
  version    = "1.2.3"  # Always pin version
  namespace  = "my-namespace"

  # Probes
  set {
    name  = "readinessProbe.enabled"
    value = "true"
  }
  set {
    name  = "livenessProbe.enabled"
    value = "true"
  }

  # Resources
  set {
    name  = "resources.requests.memory"
    value = "128Mi"
  }
  set {
    name  = "resources.requests.cpu"
    value = "100m"
  }

  # Security context
  set {
    name  = "podSecurityContext.seccompProfile.type"
    value = "RuntimeDefault"
  }

  # Image tag (never latest)
  set {
    name  = "image.tag"
    value = "1.2.3"
  }
}
```

### Using Values Files (preferred for complex charts)

```hcl
resource "helm_release" "my_app" {
  name  = "my-app"
  chart = "my-app"

  values = [templatefile("${path.module}/values/my-app.yaml", {
    image_tag     = "1.2.3"
    replica_count = var.replicas
  })]
}
```

```yaml
# values/my-app.yaml
replicaCount: ${replica_count}
image:
  tag: "${image_tag}"
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    cpu: 500m
    memory: 256Mi
podSecurityContext:
  runAsNonRoot: true
  seccompProfile:
    type: RuntimeDefault
containerSecurityContext:
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
```

---

## Postrender Pattern

When charts don't support required fields natively, use Kustomize postrender to inject them.

### Terraform Configuration

```hcl
resource "helm_release" "my_operator" {
  name             = "my-operator"
  repository       = "https://charts.example.com"
  chart            = "my-operator"
  version          = "2.12.1"
  namespace        = "operator-system"
  create_namespace = true

  postrender {
    binary_path = "${path.module}/kustomize/my-operator-postrender.sh"
  }
}
```

### Postrender Script

```bash
#!/bin/bash
# kustomize/my-operator-postrender.sh
set -euo pipefail
cat > /tmp/helm-input.yaml
kustomize build "${KUSTOMIZE_DIR:-./kustomize/my-operator}" --load-restrictor=LoadRestrictionsNone
```

### Kustomize Overlay

```yaml
# kustomize/my-operator/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - /tmp/helm-input.yaml
patches:
  - target:
      kind: Deployment
      name: my-operator
    patch: |-
      - op: add
        path: /spec/template/spec/securityContext/seccompProfile
        value:
          type: RuntimeDefault
      - op: add
        path: /spec/template/spec/containers/0/readinessProbe
        value:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5
      - op: add
        path: /spec/template/spec/containers/0/livenessProbe
        value:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 15
          periodSeconds: 10
      - op: add
        path: /spec/template/spec/containers/0/resources
        value:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 1000m
            memory: 512Mi
```

### Workflow for New Helm Charts

1. Check chart documentation for probe/security options
2. Set all required values in the helm_release resource
3. Run `terraform plan` and review rendered manifests
4. If chart lacks options, create postrender with Kustomize
5. Deploy and verify: `kubectl get constraints -o wide`
6. Document any special handling in the .tf file comments

---

## Checking Compliance

### Before Deployment

```bash
# Render Helm chart and check for required fields
helm template my-release my-chart -n my-namespace | \
  grep -E "(readinessProbe|livenessProbe|requests|seccompProfile|:latest)"
```

### After Deployment

```bash
# Check for violations
kubectl get constraints -o wide

# Specific constraint types
kubectl get k8sazurev2containerenforceprob -o wide
kubectl describe k8sazurev2containerenforceprob

# Find pods missing probes
kubectl get pods -A -o json | \
  jq '.items[] | select(.spec.containers[].readinessProbe == null) | .metadata.name'

# Find pods with :latest tags
kubectl get pods -A -o json | \
  jq '.items[] | select(.spec.containers[].image | test(":latest$|:[^:]*$" | not)) | .metadata.name'
```

---

## Common Issues

### Chart doesn't support probes

Use postrender with Kustomize patches (see Postrender Pattern above).

### Init containers need probes

Init containers are exempt from probe requirements. Only regular containers need probes.

### Sidecar injection adds non-compliant containers

Configure sidecar injector to add probes, or use mesh-native health checks.

### Operator-managed resources

Configure the operator CRD to generate compliant resources:

```yaml
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
spec:
  nodeSets:
    - podTemplate:
        spec:
          securityContext:
            seccompProfile:
              type: RuntimeDefault
```

### Admission webhook rejection

Check which constraint rejected the resource:

```bash
# Get recent events for rejections
kubectl get events -A --field-selector reason=FailedCreate | grep -i safeguard

# Describe the failing pod/deployment for details
kubectl describe deployment my-app -n my-namespace
```

---

## Constraint Reference

| Constraint Type | What It Checks |
|-----------------|----------------|
| `k8sazurev2containerenforceprob` | Probes on containers |
| `k8sazurev3containerlimits` | Resource requests |
| `k8sazurev1antiaffinityrules` | Anti-affinity for HA |
| `k8sazurev1blockdefaulttags` | No `:latest` tags |
| `k8sazurev1containernoprivilege` | No privileged containers |
| `k8sazurev1disallowedcapabilities` | Capability restrictions |

### What Does NOT Work

These approaches will NOT bypass safeguards on AKS Automatic:

| Approach | Result |
|----------|--------|
| `az aks safeguards update --level Warn` | Rejected on AKS Automatic |
| `az aks safeguards update --excluded-ns` | Rejected on AKS Automatic |
| Namespace annotations | No effect |
| Policy exemptions | Cannot exempt AKS Automatic policies |
| Gatekeeper constraint modifications | Managed by Azure, reverts automatically |

---

**Back to:** [Main Skill File](../SKILL.md)
