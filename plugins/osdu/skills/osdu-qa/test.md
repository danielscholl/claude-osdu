# Test Execution

Instructions for handling `/osdu-qa test` commands.

## Behavior

This command has four modes based on arguments:

### Mode 1: No Arguments (`test`)
Generate a **Test Plan Report** showing:
1. Environment info and connectivity status
2. Coverage & Risk Snapshot (executive summary)
3. Service Coverage Matrix (capability breakdown)
4. CI Execution Guide (pipeline mapping)
5. Service Test Profiles (compressed details)

### Mode 2: With Service (`test <service>`)
Execute tests and generate a **Test Results Report** showing:
1. Environment context
2. Pass/fail summary with metrics
3. Failure analysis with patterns and possible causes

### Mode 3: Versions (`test versions`)
Generate a **Service Versions Report** showing:
1. Current environment context
2. Version information for all OSDU services
3. Build details and release information

### Mode 4: Compare Environments (`test compare <env1> <env2>`)
Run tests on multiple environments **in parallel** and generate comparison report:
1. Launch parallel subagents (one per environment)
2. Execute full test suite on each environment simultaneously
3. Generate individual environment reports
4. Generate comparison report with winners analysis

---

## CLI Entry Points

**Note:** These are for reference. For test execution, always use the `qa-runner` agent.

```bash
# Environment status (OK to run directly)
uv run skills/osdu-qa/scripts/env_manager.py status

# Connectivity check (OK to run directly)
uv run skills/osdu-qa/scripts/osdu_test.py check

# List all tests (OK to run directly)
uv run skills/osdu-qa/scripts/osdu_test.py list

# Get service versions (OK to run directly)
uv run skills/osdu-qa/scripts/service_versions.py

# Run tests - USE qa-runner AGENT INSTEAD
# uv run skills/osdu-qa/scripts/osdu_test.py run <service>
```

---

## Mode 1: Test Plan Report (No Arguments)

When user runs `test` with no arguments, generate a comprehensive report.

### Step 1: Get Environment Status
```bash
uv run skills/osdu-qa/scripts/env_manager.py status
uv run skills/osdu-qa/scripts/osdu_test.py check
```

### Step 2: Get Test Catalog
```bash
uv run skills/osdu-qa/scripts/osdu_test.py list
```

### Step 3: Generate Full Report

See [reference/test-plan-template.md](reference/test-plan-template.md) for the full report format.

Key sections:
- Environment info
- Coverage & Risk Snapshot
- Top Gaps & Recommended Actions
- Service Coverage Matrix
- CI Execution Guide
- Service Test Profiles (Core, Data, Ingestion, DDMS)
- Quick Start guide

---

## Mode 2: Test Results Report (With Service Argument)

When user runs `test <service>`, **delegate to the qa-runner agent**.

### Why Use qa-runner Agent?
- Returns structured summary instead of raw Newman output
- Runs in background (non-blocking)
- Provides pass rates and actionable next steps
- Uses haiku model (cost-effective)

### Step 1: Delegate to qa-runner Agent

```
Use Task tool with:
  subagent_type: "qa-runner"
  prompt: "Run the <service> tests on the current environment and provide a structured summary"
```

Example:
```
Agent(
  subagent_type="qa-runner",
  description="Run smoke tests",
  prompt="Run the smoke tests on the current environment and provide a structured summary with pass rates and any failures"
)
```

### Step 2: Report Results from Agent

Select format based on results:

| Condition | Format |
|-----------|--------|
| Single env, all pass | Minimal (1-line summary) |
| Single env, failures | Failure-first (details on what broke) |
| Multi env, all pass | Scoreboard with "Differences: None" |
| Multi env, some fail | Scoreboard + difference analysis |

### Output Principles

1. **Instant verdict first** - Pass/fail visible in first 2 lines
2. **Differences always shown** - Even if "None"
3. **Actionable next steps** - What command to run next
4. **Artifacts listed** - Where to find detailed reports

---

## Mode 3: Service Versions Report (`test versions`)

### Step 1: Get Environment Info
```bash
uv run skills/osdu-qa/scripts/env_manager.py status
```

### Step 2: Query Service Info Endpoints
```bash
uv run skills/osdu-qa/scripts/service_versions.py
```

### Step 3: Generate Versions Report

Show version information for:
- Core Services (Legal, Storage, Search, Entitlements, Schema, Partition)
- Data Management (File, Dataset, Unit, Indexer)
- Workflow & Integration
- Domain Services (DDMS)
- Connected Services (ElasticSearch version)
- Services Not Responding

---

## Mode 4: Compare Environments (Parallel Testing)

When user runs `test compare <env1> <env2>`:

### Step 1: Parse Arguments

Support both forms:
- Short: `qa temp` → `<platform>/qa` and `<platform>/temp` (within same platform)
- Full: `<platform>/env1 <platform>/env2`

### Step 2: Launch Parallel Subagents

Use the Task tool with `qa-runner` agent or Bash subagents to run tests on both environments simultaneously.

### Step 3: Generate Reports

Create three files in `reports/`:
1. `qa-test-results-{env1}-{date}.md` - Results for env1
2. `qa-test-results-{env2}-{date}.md` - Results for env2
3. `qa-test-comparison-{env1}-vs-{env2}-{date}.md` - Comparison

Or delegate to `qa-comparator` agent for intelligent comparison.

---

## Service Aliases

### Smoke - Pre-flight
| Alias | Collection | Tests |
|-------|------------|-------|
| `smoke` | Core Smoke Test | 153 |

### P0 - Core Platform
| Alias | Collection | Tests |
|-------|------------|-------|
| `legal` | Legal API | 94 |
| `entitlements` | Entitlements API | 268 |
| `schema` | Schema API | 52 |
| `storage` | Storage API | 149 |
| `file` | File API | 39 |
| `search` | Search API R3 v2.0 | 119 |
| `secret` | Secret Service | 23 |

### P1 - Core+
| Alias | Collection | Tests |
|-------|------------|-------|
| `unit` | Unit API | 332 |
| `crs-catalog` | CRS Catalog API v1.0 | 302 |
| `crs-conversion` | CRS Conversion API v1.0 | 41 |
| `dataset` | Dataset API | 36 |
| `registration` | Registration API | 94 |
| `workflow` | Workflow API | 100 |
| `ingestion` | Manifest Ingestion | 99 |
| `csv-ingestion` | CSV Ingestion Workflow | 85 |
| `ingestion-ref` | Ingestion By Reference | 69 |

### P2 - DDMS & Domain
| Alias | Collection | Tests |
|-------|------------|-------|
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

### Tier / Group Aliases
| Group | Expands To |
|-------|-----------|
| `p0` / `core` | legal, entitlements, schema, storage, file, search, secret |
| `p1` / `core+` | unit, crs-catalog, crs-conversion, dataset, registration, workflow, ingestion, csv-ingestion, ingestion-ref |
| `p2` / `ddms` | wellbore-ddms, well-delivery, well-data, wellbore-wf, markers, welllog, trajectory, seismic, segy-zgy, segy-openvds, witsml, energyml |
| `well-all` | wellbore-ddms, well-delivery, well-data, wellbore-wf, markers, welllog, welllog-las, trajectory |
| `seismic-all` | seismic, segy-zgy, segy-openvds |
| `ingestion-all` | ingestion, csv-ingestion, ingestion-ref, witsml, welllog-las |

### Secondary Aliases (multi-file folder disambiguation)
| Alias | Points To | Reason |
|-------|----------|--------|
| `crs-catalog-v3` | CRS Catalog V3 (9 tests) | Minimal V3 subset in same folder |
| `crs-conv-v3` | CRS Conversion V3 (5 tests) | Minimal V3 subset in same folder |
| `search-v1` | Search R3 v1.0 (119 tests) | Older version of search collection |

### Backward Compatibility Aliases
| Alias | Points To | Reason |
|-------|----------|--------|
| `wellbore` | wellbore-ddms | Short name backward compat |
| `crs` | crs-catalog | Old combined alias, now points to larger collection |

---

## Analysis Logic

When generating reports, diagnose errors:

| Error Pattern | Root Cause | Fix Command |
|---------------|------------|-------------|
| All/most 401 | Token expired/invalid | `env use {env}` then refresh |
| All/most 403 | Missing permissions | Check entitlements/ACLs |
| All/most 404 | Resources not found | Verify test data exists |
| All/most 500 | Backend error | Check service health |
| Mixed 4xx/5xx | Multiple issues | Start with `test smoke` |
| Timeout errors | Network/perf | Check connectivity |
