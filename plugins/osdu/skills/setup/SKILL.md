---
name: setup
allowed-tools: Bash, Read
description: >-
  Check and install CLI tool dependencies required by these skills.
  Use when the user says "setup", "check dependencies", "what do I need installed",
  or when a skill fails with "command not found". This does NOT set up a specific
  project. It ensures the tools needed by skills are present on the machine.
  Not for: project-specific setup, IDE configuration, or environment provisioning.
---

# Setup

Check whether the CLI tools these skills depend on are installed, and help install what's missing.

## When to Use

- User says "setup", "check my tools", "what do I need installed"
- A skill fails because a CLI tool isn't found
- First time using the skills after install
- User asks "why isn't X working" and the issue is a missing tool

## Quick Start

```bash
# Check if the check script is available
uv --version
```

If `uv` is installed, skip exploration and go to the dependency check.

## Dependency Check

Run the dependency checker and present results to the user:

```bash
# Check all plugin dependencies
uv run tests/scripts/check_deps.py

# Check with install commands shown
uv run tests/scripts/check_deps.py --fix

# Check only what a specific skill needs
uv run tests/scripts/check_deps.py --skill iac
uv run tests/scripts/check_deps.py --skill glab

# Check a tier
uv run tests/scripts/check_deps.py --tier core
uv run tests/scripts/check_deps.py --tier infrastructure

# JSON output (for programmatic use)
uv run tests/scripts/check_deps.py --json
```

## Dependency Tiers

Not every tool is needed by every skill. Dependencies are grouped by tier:

| Tier | Skills | Tools |
|------|--------|-------|
| **core** | All plugin scripts | git, python3, uv |
| **infrastructure** | iac, health | terraform, helm, kubectl, kustomize |
| **platform** | glab, send, osdu-*, briefing, fossa | az, glab, osdu-activity, osdu-quality, osdu-engagement |
| **build** | maven, dependencies, dependency-scan, remediate | java, mvn, trivy |
| **knowledge** | brain | node |
| **qa** | osdu-qa | newman |

Users only need to install tools for the skills they plan to use.

### Optional: OSDU MCP Server

The OSDU MCP server provides live platform access (search, storage, schema, legal, entitlements, partition, health). Install it for skills that query the OSDU platform:

```bash
pip install osdu-mcp-server
```

The MCP server is pre-configured in the plugin's `.mcp.json`. Set the required environment variables:

```bash
export OSDU_MCP_SERVER_URL="https://your-osdu-instance.com"
export OSDU_MCP_SERVER_DATA_PARTITION="opendes"
```

Authentication uses automatic cloud credential discovery (Azure, AWS, GCP). No additional auth config is needed if your cloud CLI is already authenticated.

### Optional: QMD (macOS/Linux only)

The QMD search engine provides hybrid search over the knowledge vault. Install it manually if you want vault search:

```bash
npm install -g @tobilu/qmd
```

The QMD MCP server can be configured in `.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "qmd": {
      "command": "qmd",
      "args": ["mcp"]
    }
  }
}
```

QMD is not supported on Windows. The brain skill still works without it — vault reads and writes function normally, but semantic search is unavailable.

## Workflow

1. **Run the check:** `uv run tests/scripts/check_deps.py --fix`
2. **Review results** — grouped by tier with pass/fail per tool
3. **Ask the user** which missing tools to install (offer "install all missing" as an option)
4. **Install with approval** — run the install commands from `--fix` output
5. **Fix PATH if needed** — tools installed via `uv tool install` go to `~/.local/bin`. If the tool is installed but not found, run:
   ```bash
   export PATH="$HOME/.local/bin:$PATH"
   ```
   Then advise the user to add this to their shell profile (`~/.zshrc`, `~/.bashrc`).
6. **Re-check** to confirm: `uv run tests/scripts/check_deps.py`
7. **Resume the original task** — if setup was triggered by a missing tool in another skill, retry the original request after installation succeeds.

## Windows Notes

### Maven
Maven is not available via winget. Download from https://maven.apache.org/download.cgi, extract to `C:\tools\apache-maven-<version>`, and add the `bin` directory to your PATH. Set `JAVA_HOME` to your JDK install path.

### Trivy
Windows Defender may quarantine `trivy.exe` as a false positive. Fix with an admin PowerShell prompt:
```powershell
Add-MpPreference -ExclusionPath "C:\Users\<username>\AppData\Local\Microsoft\WinGet\Packages\AquaSecurity.Trivy_Microsoft.Winget.Source_8wekyb3d8bbwe\trivy.exe"
winget install --id AquaSecurity.Trivy --force
```

### QMD
The `qmd` tool is not supported on Windows. The brain skill still works for reading and writing notes, but semantic search (`qmd-query`) is unavailable.

## Manifest

The full dependency map is in `skills/setup/deps.json`. Each entry specifies:
- `check` — command to verify the tool is installed
- `tier` — which tier it belongs to
- `required_by` — which skills need it
- `install` — platform-specific install commands (darwin, linux, or * for universal)

When adding a new skill that requires a CLI tool, add the tool to `deps.json`.
