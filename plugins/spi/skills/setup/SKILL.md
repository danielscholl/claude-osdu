---
name: setup
allowed-tools: Bash, Read
description: >-
  Check and install CLI tool dependencies required by SPI skills.
  Use when the user says "setup", "check dependencies", "what do I need installed",
  or when a skill fails with "command not found". This does NOT set up a specific
  project. It ensures the tools needed by SPI skills are present on the machine.
  Not for: project-specific setup, IDE configuration, or environment provisioning.
---

# Setup

Check whether the CLI tools SPI skills depend on are installed, and help install
what's missing.

## When to Use

- User says "setup", "check my tools", "what do I need installed"
- A skill fails because a CLI tool isn't found
- First time using the SPI skills after install
- User asks "why isn't X working" and the issue is a missing tool

## Dependency Tiers

| Tier | Skills | Tools |
|------|--------|-------|
| **core** | All plugin scripts | git, python3, uv |
| **infrastructure** | iac | terraform, helm, kubectl, kustomize |
| **platform** | iac, forks | az, azd, gh, pwsh |

### Quick Check

```bash
# Check all SPI dependencies at once
for tool in git python3 uv terraform helm kubectl kustomize az azd gh pwsh; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "  $tool: OK"
  else
    echo "  $tool: MISSING"
  fi
done
```

## Installation Guide

### Core Tools

| Tool | macOS | Linux | Windows |
|------|-------|-------|---------|
| git | `xcode-select --install` | `apt install -y git` | `winget install Git.Git` |
| python3 | `brew install python@3.11` | `apt install -y python3` | `winget install Python.Python.3.11` |
| uv | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | same | same |

### Infrastructure Tools

| Tool | macOS | Linux | Windows |
|------|-------|-------|---------|
| terraform | `brew install terraform` | `brew install terraform` | `winget install Hashicorp.Terraform` |
| helm | `brew install helm` | `brew install helm` | `winget install Helm.Helm` |
| kubectl | `brew install kubectl` | `brew install kubectl` | `winget install Kubernetes.kubectl` |
| kustomize | `brew install kustomize` | `brew install kustomize` | `winget install Kubernetes.kustomize` |

### Platform Tools

| Tool | macOS | Linux | Windows |
|------|-------|-------|---------|
| az | `brew install azure-cli` | `curl -sL https://aka.ms/InstallAzureCLIDeb \| sudo bash` | `winget install Microsoft.AzureCLI` |
| azd | `brew install azure/azd/azd` | `curl -fsSL https://aka.ms/install-azd.sh \| bash` | `winget install microsoft.azd` |
| gh | `brew install gh` | `brew install gh` | `winget install GitHub.cli` |
| pwsh | `brew install powershell/tap/powershell` | `apt install -y powershell` | `winget install Microsoft.PowerShell` |

### Why PowerShell?

The osdu-spi-infra repository uses PowerShell 7.4+ for all azd lifecycle hooks
(`scripts/*.ps1`). Without `pwsh`, you cannot run `azd up` or debug deployment scripts.

### Why `gh` (not `glab`)?

SPI repos live on GitHub, not GitLab. The `gh` CLI is used for all PR operations,
workflow dispatch, issue management, and API calls against osdu-spi-* repos.

## Workflow

1. Run the quick check above
2. Review which tools are missing
3. Ask the user which missing tools to install
4. Install with their approval
5. Re-check to confirm
6. Resume the original task
