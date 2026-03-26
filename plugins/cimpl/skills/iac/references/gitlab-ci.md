# GitLab CI/CD for Terraform

> **Part of:** [terraform skill](../SKILL.md)
> **Purpose:** GitLab CI pipeline templates for Terraform on Azure

---

## Table of Contents

1. [Pipeline Structure](#pipeline-structure)
2. [Environment Promotion](#environment-promotion)
3. [Security Scanning](#security-scanning)
4. [Merge Request Workflows](#merge-request-workflows)
5. [Troubleshooting](#troubleshooting)

---

## Pipeline Structure

### Basic Pipeline

```yaml
# .gitlab-ci.yml
stages:
  - validate
  - plan
  - apply

variables:
  TF_ROOT: ${CI_PROJECT_DIR}/infra

.terraform_template:
  image: hashicorp/terraform:latest
  before_script:
    - cd ${TF_ROOT}
    - az login --service-principal -u $ARM_CLIENT_ID -p $ARM_CLIENT_SECRET --tenant $ARM_TENANT_ID
    - export ARM_SUBSCRIPTION_ID=$ARM_SUBSCRIPTION_ID
    - terraform init -backend-config="provider.conf.json"

validate:
  extends: .terraform_template
  stage: validate
  script:
    - terraform fmt -check -recursive
    - terraform validate

plan:
  extends: .terraform_template
  stage: plan
  script:
    - terraform plan -out=tfplan
  artifacts:
    paths:
      - ${TF_ROOT}/tfplan
    expire_in: 1 week
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "dev"

apply:
  extends: .terraform_template
  stage: apply
  script:
    - terraform apply -auto-approve tfplan
  dependencies:
    - plan
  rules:
    - if: $CI_COMMIT_BRANCH == "dev"
  when: manual
  environment:
    name: development
```

### Required CI Variables

Set these in GitLab > Settings > CI/CD > Variables:

| Variable | Description | Masked | Protected |
|----------|-------------|--------|-----------|
| `ARM_CLIENT_ID` | Service principal app ID | No | Yes |
| `ARM_CLIENT_SECRET` | Service principal secret | Yes | Yes |
| `ARM_TENANT_ID` | Azure AD tenant ID | No | Yes |
| `ARM_SUBSCRIPTION_ID` | Target subscription | No | Yes |
| `RS_STORAGE_ACCOUNT` | Terraform state storage account | No | Yes |
| `RS_CONTAINER_NAME` | Terraform state container | No | Yes |
| `RS_RESOURCE_GROUP` | State storage resource group | No | Yes |

### PowerShell Syntax Check

```yaml
powershell-lint:
  stage: validate
  image: mcr.microsoft.com/powershell:latest
  script:
    - |
      pwsh -Command '
        $scripts = Get-ChildItem -Path ./scripts -Filter "*.ps1"
        foreach ($s in $scripts) {
          $null = [System.Management.Automation.PSParser]::Tokenize(
            (Get-Content $s.FullName -Raw), [ref]$null
          )
        }
      '
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
      changes:
        - scripts/**/*.ps1
```

---

## Environment Promotion

### Two-Branch Model

Matching the project's branching model: `feature/* -> dev -> main`

```yaml
# Plan runs on MRs and dev branch
plan:dev:
  extends: .terraform_template
  stage: plan
  variables:
    TF_VAR_environment_name: "dev"
  script:
    - terraform plan -out=tfplan
  artifacts:
    paths:
      - ${TF_ROOT}/tfplan
    expire_in: 1 week
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == "dev"

# Apply to dev (manual gate)
apply:dev:
  extends: .terraform_template
  stage: apply
  variables:
    TF_VAR_environment_name: "dev"
  script:
    - terraform apply -auto-approve tfplan
  dependencies:
    - plan:dev
  rules:
    - if: $CI_COMMIT_BRANCH == "dev"
  when: manual
  environment:
    name: development

# Production
apply:prod:
  extends: .terraform_template
  stage: apply
  variables:
    TF_VAR_environment_name: "prod"
  script:
    - terraform plan -out=tfplan
    - terraform apply -auto-approve tfplan
  rules:
    - if: $CI_COMMIT_BRANCH == "main"
  when: manual
  environment:
    name: production
```

### Per-Environment Backend Config

```yaml
.terraform_template:
  before_script:
    - cd ${TF_ROOT}
    - az login --service-principal -u $ARM_CLIENT_ID -p $ARM_CLIENT_SECRET --tenant $ARM_TENANT_ID
    - |
      terraform init \
        -backend-config="storage_account_name=${RS_STORAGE_ACCOUNT}" \
        -backend-config="container_name=${RS_CONTAINER_NAME}" \
        -backend-config="key=${TF_VAR_environment_name}.tfstate" \
        -backend-config="resource_group_name=${RS_RESOURCE_GROUP}"
```

---

## Security Scanning

### Trivy for Terraform

```yaml
security-scan:
  stage: validate
  image:
    name: aquasec/trivy:latest
    entrypoint: [""]
  script:
    - trivy config --severity HIGH,CRITICAL ./infra
    - trivy config --severity HIGH,CRITICAL ./platform
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  allow_failure: false
```

### Checkov

```yaml
checkov-scan:
  stage: validate
  image:
    name: bridgecrew/checkov:latest
    entrypoint: [""]
  script:
    - checkov -d ./infra --framework terraform --quiet
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
  allow_failure: true  # Advisory initially, enforce later
```

### Secret Detection

```yaml
secrets-scan:
  stage: validate
  image: trufflesecurity/trufflehog:latest
  script:
    - trufflehog filesystem --directory . --only-verified
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
```

---

## Merge Request Workflows

### Plan Output as MR Comment

```yaml
plan:
  extends: .terraform_template
  stage: plan
  script:
    - terraform plan -out=tfplan -no-color 2>&1 | tee plan_output.txt
    - |
      # Post plan output as MR comment
      if [ "$CI_PIPELINE_SOURCE" == "merge_request_event" ]; then
        PLAN_OUTPUT=$(cat plan_output.txt | tail -50)
        curl --request POST \
          --header "PRIVATE-TOKEN: ${GITLAB_API_TOKEN}" \
          --data-urlencode "body=## Terraform Plan\n\`\`\`\n${PLAN_OUTPUT}\n\`\`\`" \
          "${CI_API_V4_URL}/projects/${CI_PROJECT_ID}/merge_requests/${CI_MERGE_REQUEST_IID}/notes"
      fi
  artifacts:
    paths:
      - ${TF_ROOT}/tfplan
      - ${TF_ROOT}/plan_output.txt
```

### Terraform Format Check with Diff

```yaml
fmt-check:
  extends: .terraform_template
  stage: validate
  script:
    - |
      if ! terraform fmt -check -recursive -diff; then
        echo "Run 'terraform fmt -recursive' to fix formatting"
        exit 1
      fi
```

---

## Troubleshooting

### Tests Fail in CI but Pass Locally

**Cause:** Different Terraform/provider versions or missing auth.

**Fix:**
```yaml
# Pin Terraform version in CI
.terraform_template:
  image: hashicorp/terraform:1.9.0  # Match local version
```

### State Lock Errors

**Cause:** Previous pipeline failed without releasing lock.

**Fix:**
```bash
# Get the lock ID from the error message
terraform force-unlock <lock-id>
```

### Backend Init Fails

**Cause:** Incorrect storage account credentials or missing container.

**Fix:**
```bash
# Verify storage account exists and credentials work
az storage container list --account-name $RS_STORAGE_ACCOUNT --auth-mode login
```

### Provider Authentication Fails

**Cause:** Expired service principal secret or wrong tenant.

**Fix:**
```bash
# Verify credentials
az login --service-principal -u $ARM_CLIENT_ID -p $ARM_CLIENT_SECRET --tenant $ARM_TENANT_ID
az account show
```

---

**Back to:** [Main Skill File](../SKILL.md)
