---
name: maven
allowed-tools: Bash, Read, Glob
description: >-
  Maven dependency version checking and security vulnerability scanning. Check Maven artifact versions, find updates, scan for CVEs with Trivy, and analyze POM files.
  Use when the user asks about Maven dependency versions, needs to check for updates, wants to scan for vulnerabilities in a Java project, or needs POM file analysis.
  Not for: building or running Java tests (use build-runner or acceptance-test), or general Java project setup.
---

# Maven Skill

## IMPORTANT: Intent Detection

Parse user input to determine intent:

| User Input | Intent | Action |
|------------|--------|--------|
| `help`, `how to use`, `usage`, `format` | Help | Respond with usage info below |
| `check <dependency>` or version check | Check Version | Run check.py check |
| `batch` or multiple dependencies | Batch Check | Run check.py batch |
| `list` or available versions | List Versions | Run check.py list |
| `scan` or security/vulnerabilities | Security Scan | Run scan.py scan |
| `analyze` or POM analysis | Analyze POM | Run scan.py analyze |

---

## Version Checking (`/maven check`)

Check Maven artifact versions and find available updates.

### Usage

```
/maven check spring-core 5.3.0
/maven check org.springframework:spring-core 5.3.10
/maven batch '[ {"dependency": "spring-core", "version": "5.3.0"} ]'
/maven list spring-core
```

### Examples

| Command | What It Does |
|---------|--------------|
| `/maven check spring-core 5.3.0` | Check if version exists and find updates |
| `/maven check org.springframework:spring-core 5.3.10 --json` | JSON output for parsing |
| `/maven batch --file deps.json` | Check multiple dependencies from file |
| `/maven list org.apache.commons:commons-lang3` | List all available versions |

### Options

| Option | Description |
|--------|-------------|
| `--dependency` | Maven coordinate (groupId:artifactId) |
| `--version` | Version to check |
| `--packaging` | Package type (jar, pom, war). Default: jar |
| `--json` | Output as JSON |

---

## Security Scanning (`/maven scan`)

Scan Maven projects for security vulnerabilities using Trivy.

### Usage

```
/maven scan /path/to/project
/maven scan /path/to/pom.xml --severity high,critical
/maven analyze /path/to/pom.xml
```

### Examples

| Command | What It Does |
|---------|--------------|
| `/maven scan .` | Scan current directory for vulnerabilities |
| `/maven scan --path /project --severity critical` | Only show critical vulnerabilities |
| `/maven analyze pom.xml` | Parse POM and show dependencies |
| `/maven analyze pom.xml --check-versions` | Show dependencies with update info |

### Options

| Option | Description |
|--------|-------------|
| `--path` | Path to project directory or pom.xml |
| `--severity` | Filter by severity: critical, high, medium, low |
| `--json` | Output as JSON |
| `--check-versions` | Also check for version updates (analyze only) |

### Prerequisites

Security scanning requires Trivy to be installed:
```bash
# macOS
brew install trivy

# Linux
sudo apt-get install trivy
```

---

## AI Execution (Internal)

### Version Check

```bash
uv run skills/maven/scripts/check.py check \
  --dependency "org.springframework:spring-core" \
  --version "5.3.0" \
  [--packaging jar] \
  [--json]
```

### Batch Check

```bash
uv run skills/maven/scripts/check.py batch \
  --dependencies '[{"dependency": "org.springframework:spring-core", "version": "5.3.0"}]' \
  [--json]
```

### List Versions

```bash
uv run skills/maven/scripts/check.py list \
  --dependency "org.springframework:spring-core" \
  [--json]
```

### Security Scan

```bash
uv run skills/maven/scripts/scan.py scan \
  --path "/path/to/project" \
  [--severity "critical,high"] \
  [--json]
```

### POM Analysis

```bash
uv run skills/maven/scripts/scan.py analyze \
  --path "/path/to/pom.xml" \
  [--check-versions] \
  [--json]
```

### Output Presentation

**Present the script output directly to the user.** Do NOT summarize unless requested.

---

## Command Quick Reference

| Command | Description |
|---------|-------------|
| `check` | Check single dependency version and updates |
| `batch` | Check multiple dependencies at once |
| `list` | List all available versions for a dependency |
| `scan` | Scan project for security vulnerabilities |
| `analyze` | Parse and analyze POM file structure |

## Reference Files

- [reference/commands.md](reference/commands.md) - Full CLI command reference
- [reference/troubleshooting.md](reference/troubleshooting.md) - Error solutions
- [reference/multi-profile-builds.md](reference/multi-profile-builds.md) - Multi-profile Maven build guidance
- [scripts/check.py](scripts/check.py) - Version checking script
- [scripts/scan.py](scripts/scan.py) - Security scanning script
- [scripts/javatest.py](scripts/javatest.py) - OSDU Java project test runner with auto profile detection
