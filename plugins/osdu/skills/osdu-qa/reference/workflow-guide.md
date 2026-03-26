# OSDU QA Workflow Guide

This guide defines the standard workflow for OSDU QA testing, from initial setup through report generation and stakeholder presentations.

---

## Workflow Overview

```
┌─────────────────┐
│ Phase 0         │
│ Environment     │
│ Setup           │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Phase 1         │
│ Health Check    │──── FAIL ──→ Infrastructure Investigation
│ & Versions      │
└────────┬────────┘
         │ PASS
         ▼
┌─────────────────┐
│ Phase 2         │
│ Smoke Tests     │──── FAIL ──→ /qa-report detailed → RCA
│ (153 tests)     │
└────────┬────────┘
         │ PASS
         ▼
┌─────────────────┐
│ Phase 3         │
│ Gate Suite      │──── FAIL ──→ /qa-report detailed → RCA
│ (Legal/Storage/ │
│  Entitlements)  │
└────────┬────────┘
         │ PASS
         ▼
┌─────────────────┐
│ Phase 4         │
│ Generate Report │
│ /qa-report      │
└────────┬────────┘
         ▼
┌─────────────────┐
│ Phase 5         │
│ Extended Tests  │ (optional, non-blocking)
│ DDMS/Ingestion  │
└─────────────────┘
```

---

## Phase 0: Environment Setup

Before running any tests, ensure you're targeting the correct environment.

### Check Current Environment

```bash
# View active environment configuration
uv run skills/osdu-qa/scripts/env_manager.py status
```

Or use the skill command:
```
/osdu-qa env status
```

### Switch Environment

```bash
# Switch to a different environment
uv run skills/osdu-qa/scripts/env_manager.py use <platform>/<env>
```

Or use the skill command:
```
/osdu-qa env use <platform>/<env>
```

### Available Environments

Run `/osdu-qa env` to see configured environments.
Add with: `/osdu-qa env add <platform>/<name> --host <host> --partition <partition> --auth-type <type>`

See `reference/environments.example.json` for the configuration schema.

---

## Phase 1: Connectivity & Health Check

Verify platform connectivity and gather baseline service information.

### Quick Connectivity Check

```bash
# Verify Newman, repository, config, and authentication
uv run skills/osdu-qa/scripts/osdu_test.py check
```

Or use the skill command:
```
/osdu-qa check
```

### Get Service Versions (Critical Baseline)

```bash
# Get all service versions, branches, and build dates
uv run skills/osdu-qa/scripts/service_versions.py
```

Or use the skill command:
```
/osdu-qa test versions
```

**This step is critical** - service versions establish the baseline for your report and help identify version-related issues.

### Decision Point

| Result | Action |
|--------|--------|
| All services responding | Proceed to Phase 2 |
| Services not responding | Investigate infrastructure before proceeding |
| Authentication failed | Check credentials, re-authenticate |

---

## Phase 2: Smoke Testing

Run the Core Smoke Test collection for fast validation of platform functionality.

### Run Smoke Tests

```bash
# Run core smoke tests
uv run skills/osdu-qa/scripts/osdu_test.py run 01_CICD_CoreSmokeTest
```

Or use the skill command:
```
/osdu-qa test smoke
```

### What Smoke Tests Cover

| Category | Tests | What It Validates |
|----------|-------|-------------------|
| Auth | Token refresh | Authentication working |
| Legal | 13 assertions | Legal tag CRUD |
| Entitlements | 14 assertions | Group management |
| Storage | 17 assertions | Record CRUD |
| Schema | 6 assertions | Schema registration |
| Search | 54 assertions | Query operations |
| Unit | 34 assertions | Unit conversions |
| CRS Catalog | 39 assertions | Coordinate systems |
| CRS Conversion | 6 assertions | Coordinate transforms |
| Manifest Ingestion | 13 assertions | Bulk ingestion |

### Decision Point

| Result | Action |
|--------|--------|
| 100% pass rate | Proceed to Phase 3 (Gate Testing) |
| Failures detected | Generate failure report, investigate root cause |

### On Failure

```
/qa-report detailed
```

This generates a comprehensive report with:
- Critical Issue Analysis
- Root Cause Hypotheses
- Investigation Steps
- Recommended Actions

---

## Phase 3: Gate Collection Testing

Run the full gate suite to validate deployment readiness.

### Gate Collections

| Collection | ID | Tests | Signal |
|------------|----|-------|--------|
| Core Smoke | `01_CICD_CoreSmokeTest` | 153 | Strong |
| Legal API | `11_CICD_Setup_LegalAPI` | 94 | Strong |
| Storage API | `12_CICD_Setup_StorageAPI` | 149 | Strong |
| Entitlements API | `14_CICD_Setup_EntitlementAPI` | 268 | Strong |

### Run Gate Collections

```bash
# Run each gate collection
uv run skills/osdu-qa/scripts/osdu_test.py run 11_CICD_Setup_LegalAPI
uv run skills/osdu-qa/scripts/osdu_test.py run 12_CICD_Setup_StorageAPI
uv run skills/osdu-qa/scripts/osdu_test.py run 14_CICD_Setup_EntitlementAPI
```

Or use the skill commands:
```
/osdu-qa test legal
/osdu-qa test storage
/osdu-qa test entitlements
```

### Using the qa-runner Agent (Recommended)

For parallel execution:
```
Use qa-runner agent to execute Legal, Storage, and Entitlements collections in parallel
```

### Decision Point

| Result | Action |
|--------|--------|
| All gate collections pass | Environment is READY - proceed to report generation |
| Any gate collection fails | Generate detailed report with RCA |

---

## Phase 4: Report Generation

Generate reports for documentation and stakeholder communication.

### Report Types

| Argument | Sections Included | Use Case |
|----------|-------------------|----------|
| `summary` | Executive Summary, Actions, Conclusion | Quick status update |
| `detailed` | All 9 sections | Full documentation |
| `slides` | All sections + PPTX presentation | Stakeholder meetings |

### Generate Reports

```
# Quick summary
/qa-report summary

# Full detailed report (default)
/qa-report detailed

# Full report with PowerPoint presentation
/qa-report slides
```

### Report Sections (Detailed Mode)

1. **Executive Summary** - Status overview, key findings
2. **Detailed Test Results** - Per-environment breakdown with service versions
3. **Critical Issue Analysis** - Failure chains (if failures exist)
4. **Root Cause Hypotheses** - Investigation theories (if failures exist)
5. **Environment Configuration Comparison** - Multi-env differences
6. **Investigation Steps** - Commands for debugging (if failures exist)
7. **Recommended Actions** - P0/P1/P2 prioritized tasks
8. **Test Execution Details** - Collection breakdown
9. **Conclusion** - Summary and next steps

### Report Output

Reports are saved to:
```
reports/qa-report-{environment}-{date}.md
```

---

## Phase 5: Extended Testing (Optional)

Run additional collections for comprehensive coverage. These are non-blocking for deployment.

### Domain-Specific Collections

```bash
# WITSML Setup
uv run skills/osdu-qa/scripts/osdu_test.py run 41_CICD_Setup_WITSML

# SEGY/ZGY Conversion
uv run skills/osdu-qa/scripts/osdu_test.py run 42_CICD_SEGY_ZGY_Conversion

# Ingestion By Reference
uv run skills/osdu-qa/scripts/osdu_test.py run 47_CICD_IngestionByReference
```

### Extended Collection Categories

| Priority | Collections | Purpose |
|----------|-------------|---------|
| P1 | Schema, Search, Workflow, Ingestion | Important functionality |
| P2 | Unit, Dataset, Wellbore DDMS | Standard coverage |
| P3 | CRS Catalog V3, WITSML, Seismic | Specialized functionality |

---

## Multi-Environment Workflow

When testing across multiple environments for comparison.

### Sequential Testing

```bash
# Test each environment in sequence (replace with your configured environments)
for env in $(uv run skills/osdu-qa/scripts/env_manager.py list --names); do
    uv run skills/osdu-qa/scripts/env_manager.py use $env
    uv run skills/osdu-qa/scripts/osdu_test.py run 01_CICD_CoreSmokeTest
done
```

### Generate Comparison Report

After testing multiple environments:
```
/qa-report detailed
```

The report will include the **Environment Configuration Comparison** section showing differences across environments.

### Using qa-comparator Agent

```
Use qa-comparator agent to compare test results between <platform>/<env1> and <platform>/<env2>
```

---

## Failure Investigation Workflow

When tests fail, follow this investigation sequence.

### 1. Generate Detailed Report

```
/qa-report detailed
```

### 2. Review Critical Issue Analysis

The report identifies:
- Primary failure point (HTTP method, URL, response)
- Failure chain (how failures cascade)
- Services confirmed working

### 3. Use qa-analyzer Agent

```
Use qa-analyzer agent to investigate the Storage test failures
```

### 4. Execute Investigation Commands

The report provides specific commands:
```bash
# Example: Check pod logs
kubectl logs -l app=storage-service -n osdu --tail=100

# Example: Check database connectivity
kubectl exec -it <pod> -- curl http://localhost:8080/actuator/health
```

### 5. Document Findings

Update the report or create an RCA document in `reports/`.

---

## PowerPoint Presentation Workflow

When you need to present QA results to stakeholders.

### Generate Slides

```
/qa-report slides
```

This:
1. Generates the full detailed report
2. Saves markdown to `reports/qa-report-{env}-{date}.md`
3. Invokes the pptx-generator skill with azure-engineering brand
4. Creates presentation at `output/azure-engineering/qa-release-gate-{date}.pptx`

### Slide Layouts Used

| Slide | Layout | Content |
|-------|--------|---------|
| 1 | title-slide | Report title and date |
| 2 | environment-status-slide | Environment health overview |
| 3 | test-results-slide | Test breakdown with pass/fail bars |
| 4 | priority-actions-slide | P0/P1/P2 recommendations |
| 5 | closing-slide | Summary and next steps |

### Additional Slides (Failure Scenarios)

| Slide | Layout | When Used |
|-------|--------|-----------|
| failure-cascade-slide | Root cause and cascading failures | When failures exist |
| comparison-matrix-slide | Environment differences | Multi-environment comparison |

---

## Quick Reference Commands

### Environment

| Command | Purpose |
|---------|---------|
| `/osdu-qa env` | List all environments |
| `/osdu-qa env use {name}` | Switch environment |
| `/osdu-qa env status` | Show current config |

### Testing

| Command | Purpose |
|---------|---------|
| `/osdu-qa check` | Quick connectivity check |
| `/osdu-qa test smoke` | Run smoke tests |
| `/osdu-qa test legal` | Run Legal API tests |
| `/osdu-qa test storage` | Run Storage API tests |
| `/osdu-qa test entitlements` | Run Entitlements API tests |
| `/osdu-qa test versions` | Show service versions |
| `/osdu-qa list` | List all test collections |

### Reporting

| Command | Purpose |
|---------|---------|
| `/qa-report summary` | Executive summary only |
| `/qa-report detailed` | Full 9-section report |
| `/qa-report slides` | Full report + PowerPoint |

---

## Checklist: Complete QA Cycle

Use this checklist for a full QA testing cycle:

- [ ] **Phase 0: Setup**
  - [ ] Verify correct environment is active
  - [ ] Switch environment if needed

- [ ] **Phase 1: Health Check**
  - [ ] Run connectivity check (`/osdu-qa check`)
  - [ ] Get service versions (`/osdu-qa test versions`)
  - [ ] Verify all services responding

- [ ] **Phase 2: Smoke Tests**
  - [ ] Run smoke tests (`/osdu-qa test smoke`)
  - [ ] Verify 100% pass rate
  - [ ] If failures: generate report, investigate

- [ ] **Phase 3: Gate Testing**
  - [ ] Run Legal tests (`/osdu-qa test legal`)
  - [ ] Run Storage tests (`/osdu-qa test storage`)
  - [ ] Run Entitlements tests (`/osdu-qa test entitlements`)
  - [ ] Verify all gate collections pass

- [ ] **Phase 4: Reporting**
  - [ ] Generate detailed report (`/qa-report detailed`)
  - [ ] Review findings and recommendations
  - [ ] Generate slides if presenting (`/qa-report slides`)

- [ ] **Phase 5: Extended (Optional)**
  - [ ] Run domain-specific collections
  - [ ] Document any additional findings

---

## Tips and Best Practices

1. **Always get service versions first** - This establishes your baseline and helps identify version-related issues

2. **Use agents for parallel execution** - The qa-runner agent can execute multiple collections simultaneously

3. **Check reports/ directory** - Existing reports provide historical context for your analysis

4. **Investigate transient failures** - Multiple runs help distinguish between systematic and transient issues

5. **Keep reports in version control** - Reports document platform state at specific points in time

6. **Use slides for stakeholder communication** - Visual presentations are more effective for non-technical audiences
