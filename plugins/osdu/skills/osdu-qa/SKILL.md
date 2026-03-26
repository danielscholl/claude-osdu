---
name: osdu-qa
allowed-tools: Bash, Read, Glob, Grep
description: >-
  OSDU QA Testing - Environment management, API test execution, failure analysis, and
  report generation.
  Use when running OSDU API tests, analyzing failures, comparing environments, generating
  QA reports, or managing test environments.
  Not for: unit testing application code or build compilation (use build-runner instead).
---

# OSDU QA

Route based on the first argument:

| First Arg | Action | Details |
|-----------|--------|---------|
| `env` | Environment management | See [env.md](env.md) |
| `env audit` | Audit all environments | List format with cluster/credentials info |
| `test` | Run tests | See [test.md](test.md) |
| `check` | Quick connectivity check | Run `osdu_test.py check` |
| `list` | List available tests | Run `osdu_test.py list` |
| `report` | Generate reports | Delegate to `qa-reporter` agent |
| (none) | Show status | Display current environment and options |

**Arguments received:** $ARGUMENTS

---

## Getting Started

**New to OSDU QA?** See the [Workflow Guide](reference/workflow-guide.md) for the complete testing process from setup through report generation and PowerPoint presentations.

**Quick workflow:** Environment Setup → Health Check → Smoke Tests → Gate Tests → Report Generation

---

## Quick Reference

### Environment Commands
```
/osdu-qa env                    # List environments
/osdu-qa env use <platform>/<env> # Switch environment
/osdu-qa env status             # Show current config
/osdu-qa env audit              # Audit all environments (list format)
/osdu-qa env audit --check      # Audit with API health checks
```

### Test Commands
```
/osdu-qa test                   # Show test plan
/osdu-qa test smoke             # Run smoke tests
/osdu-qa test legal             # Run legal API tests
/osdu-qa test versions          # Show service versions
/osdu-qa test compare qa temp   # Compare environments
```

### Quick Commands
```
/osdu-qa check                  # Connectivity check
/osdu-qa list                   # List all test collections
/osdu-qa report                 # Generate QA report
```

---

## CLI Scripts

All commands map to Python scripts:

```bash
# Environment management
uv run skills/osdu-qa/scripts/env_manager.py <command>

# Test execution
uv run skills/osdu-qa/scripts/osdu_test.py <command>

# Service versions
uv run skills/osdu-qa/scripts/service_versions.py

# Report generation
uv run skills/osdu-qa/scripts/generate_report.py --format both
```

---

## Specialized Agents

**IMPORTANT: Always delegate to agents for test execution and analysis.** Direct CLI is only for debugging.

| Agent | Use For | When to Use |
|-------|---------|-------------|
| `qa-runner` | Test execution (single or multiple collections) | **Always** for running tests |
| `qa-analyzer` | Failure analysis and root cause identification | When tests fail |
| `qa-comparator` | Cross-environment comparison | When comparing environments |
| `qa-reporter` | Report and dashboard generation | When generating reports |

### How to Delegate

Use the `Agent` tool to spawn a sub-agent. Never simulate or inline a sub-agent's work.

```
Agent(
  subagent_type="qa-runner",
  description="Run smoke tests on cimpl/qa",
  prompt="Run the smoke tests on cimpl/qa and provide a structured summary with pass rates and any failures"
)
```

Replace `subagent_type` with the appropriate agent (`qa-runner`, `qa-analyzer`, `qa-comparator`, or `qa-reporter`) and adjust the prompt to match the request. The sub-agent runs independently and returns a structured summary.

### Examples
```
# Single test collection - USE AGENT
Use qa-runner to run the smoke tests

# Multiple collections - USE AGENT
Use qa-runner to execute all P0 collections in parallel

# Failure investigation - USE AGENT
Use qa-analyzer to investigate the Storage test failures

# Reports - USE AGENT
Use qa-reporter to generate an HTML dashboard
```

### When to Use Direct CLI
Only use direct CLI (`osdu_test.py`) for:
- Debugging script issues
- Quick connectivity checks (`check` command)
- Listing available tests (`list` command)

---

## Environments

Environments are user-local configuration stored in `config/environments.json` (gitignored).

Run `/osdu-qa env` to see configured environments.
Add with: `/osdu-qa env add <platform>/<name> --host <host> --partition <partition> --auth-type <azure-ad|keycloak>`
Remove with: `/osdu-qa env remove <platform>/<name> --confirm`

See `reference/environments.example.json` for the configuration schema.


---

## Test Collections (30 aliases, 33 collection files, ~2,295 tests)

### Smoke - Pre-flight (1 collection, 153 tests)
| Alias | Collection | Tests |
|-------|-----------|-------|
| `smoke` | Core Smoke Test | 153 |

### P0 - Core Platform (7 collections, 745 tests)
| Alias | Collection | Tests |
|-------|-----------|-------|
| `legal` | Legal API | 94 |
| `entitlements` | Entitlements API | 268 |
| `schema` | Schema API | 52 |
| `storage` | Storage API | 149 |
| `file` | File API | 39 |
| `search` | Search API R3 v2.0 | 119 |
| `secret` | Secret Service | 23 |

### P1 - Core+ (9 collections, 958 tests)
| Alias | Collection | Tests |
|-------|-----------|-------|
| `unit` | Unit API | 332 |
| `crs-catalog` | CRS Catalog API v1.0 | 302 |
| `crs-conversion` | CRS Conversion API v1.0 | 41 |
| `dataset` | Dataset API | 36 |
| `registration` | Registration API | 94 |
| `workflow` | Workflow API | 100 |
| `ingestion` | Manifest Ingestion | 99 |
| `csv-ingestion` | CSV Ingestion Workflow | 85 |
| `ingestion-ref` | Ingestion By Reference | 69 |

### P2 - DDMS & Domain (13 collections, 608 tests)
| Alias | Collection | Tests |
|-------|-----------|-------|
| `wellbore-ddms` | Wellbore DDMS | 82 |
| `well-delivery` | Well Delivery DDMS | 46 |
| `well-data` | Well R3 Workflow | 30 |
| `wellbore-wf` | Wellbore R3 Workflow | 29 |
| `markers` | Markers R3 Workflow | 28 |
| `welllog` | WellLog R3 | 28 |
| `welllog-las` | WellLog LAS Ingest | 36 |
| `trajectory` | Trajectory R3 Workflow | 32 |
| `seismic` | Seismic R3 | 59 |
| `segy-zgy` | SEGY-ZGY Conversion | 27 |
| `segy-openvds` | SEGY-OpenVDS Conversion | 28 |
| `witsml` | WITSML Ingestion | 121 |
| `energyml` | Energyml Converter | 24 |

### Group Aliases
| Group | Expands To |
|-------|-----------|
| `p0` / `core` | legal, entitlements, schema, storage, file, search, secret |
| `p1` / `core+` | unit, crs-catalog, crs-conversion, dataset, registration, workflow, ingestion, csv-ingestion, ingestion-ref |
| `p2` / `ddms` | wellbore-ddms, well-delivery, well-data, wellbore-wf, markers, welllog, trajectory, seismic, segy-zgy, segy-openvds, witsml, energyml |
| `well-all` | wellbore-ddms, well-delivery, well-data, wellbore-wf, markers, welllog, welllog-las, trajectory |
| `seismic-all` | seismic, segy-zgy, segy-openvds |
| `ingestion-all` | ingestion, csv-ingestion, ingestion-ref, witsml, welllog-las |

---

## Supporting Files

- [env.md](env.md) - Environment management details
- [test.md](test.md) - Test execution details
- [reference/workflow-guide.md](reference/workflow-guide.md) - **Complete QA workflow process**
- [reference/collections.md](reference/collections.md) - Full collection catalog
- [reference/troubleshooting.md](reference/troubleshooting.md) - Common issues

---

## File Structure

```
skills/osdu-qa/
├── SKILL.md              # This file (routing)
├── env.md                # Environment management instructions
├── test.md               # Test execution instructions
├── scripts/              # Python CLI tools
├── config/               # Runtime configuration
├── templates/            # Report templates
└── reference/            # Documentation
    ├── workflow-guide.md # Complete QA workflow process
    ├── collections.md    # Full collection catalog
    └── troubleshooting.md # Common issues

agents/                   # Specialized agents
├── qa-runner.agent.md
├── qa-analyzer.agent.md
├── qa-comparator.agent.md
└── qa-reporter.agent.md
```
