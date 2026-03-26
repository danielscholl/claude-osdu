---
name: osdu-quality
allowed-tools: Bash, Read
description: >-
  CI/CD test reliability analysis for OSDU platform projects. Detects flaky tests, calculates pass rates, provides cloud provider metrics, and analyzes acceptance test parity.
  Use when analyzing test health, pass rates, flaky tests, test reliability, CI quality, pipeline test results, test coverage gaps, or acceptance test parity.
  Not for: open MRs or pipeline status (use osdu-activity), contributor rankings (use osdu-engagement), running acceptance tests locally (use acceptance-test), or single-repo glab operations.
---

# OSDU Quality Skill

Analyze test reliability across OSDU platform CI/CD pipelines using the `osdu-quality` CLI.

For installation, authentication, output formats, and common troubleshooting, see the
[shared CLI reference](../../reference/osdu-cli-reference.md).

## Quick Start

Before first use, verify the tool is available:
```bash
osdu-quality --version
```
If the command is not found, **stop and use the `setup` skill** to install missing dependencies.
Do NOT attempt to install tools yourself — the setup skill handles installation with the correct
sources, user approval, and verification.

If installed, skip exploration and go straight to the intent detection table below.

## When to Use This Skill

- Test pass rates or reliability metrics
- Flaky or intermittent test failures
- Test status by stage (unit, integration, acceptance)
- Provider-specific test results (Azure, AWS, GCP, IBM, CIMPL)
- Test regressions or quality trends
- Acceptance test parity — what CSP integration tests cover that cimpl doesn't
- Test coverage gaps between providers

**Do NOT use for:**
- Open MRs, pipeline status, or issues → use `osdu-activity`
- Contributor rankings or review patterns → use `osdu-engagement`
- Single-repo GitLab operations → use `glab` directly
- Running acceptance tests locally against a live environment → use `acceptance-test`

## Intent Detection

| User Query | Command |
|------------|---------|
| "test reliability", "pass rates", "quality" | `osdu-quality analyze --output markdown` |
| "test status", "latest results" | `osdu-quality status --output markdown` |
| "flaky tests", "intermittent failures" | `osdu-quality analyze --output markdown` (look for flaky indicators) |
| "specific failures", "test breakdown" | `osdu-quality tests --project <name> --output markdown` |
| "integration/unit/acceptance tests" | `osdu-quality analyze --stage <stage> --output markdown` |
| "Azure/AWS tests", "provider comparison" | `osdu-quality analyze --provider <provider> --output markdown` |
| "test parity", "coverage gaps", "what's cimpl missing" | Parity analysis workflow (see below) |
| "acceptance test gaps", "bring cimpl in line with azure" | Parity analysis workflow (see below) |

## Commands

| Command | Purpose | Key Filters |
|---------|---------|-------------|
| `osdu-quality analyze` | Multi-project reliability analysis | `--project`, `--stage`, `--provider`, `--pipelines N` |
| `osdu-quality status` | Latest test status by stage | `--project`, `--venus`, `--no-release` |
| `osdu-quality tests` | Detailed test results from job logs | `--project` (required), `--pipeline` |

For full CLI options and JSON output structures, see [reference/commands.md](reference/commands.md).

## Output Handling

**Always pass `--output markdown`** for AI consumption. It produces token-optimized output
that's easy to summarize. Use `--output json` only when you need raw data for field extraction.
**Never omit the flag** — the default is `tty` which outputs ANSI codes that break parsing.

## Interpreting Results

**Pass Rate Thresholds:**

| Rate | Health |
|------|--------|
| 95%+ | Healthy |
| 80-95% | Needs attention |
| <80% | Concerning — investigate root cause |

**By Stage:**
- Unit tests should be near 100% — failures here indicate real bugs
- Integration tests typically 70-90% — some flakiness expected
- Acceptance tests are most variable — environment-dependent

**Flaky Test Signals:** Tests that alternate pass/fail across runs, high variance in pass
rates, or inconsistent results across providers all indicate flakiness.

## Workflow Examples

### "How healthy are partition tests?"

```bash
osdu-quality analyze --project partition --output markdown
```

Summarize: lead with the headline ("Partition unit tests are solid at 100%, but acceptance
is struggling at 60%"), show the stage breakdown, identify patterns, offer to dig into
specific failures.

### "What's failing on Azure across the platform?"

```bash
osdu-quality analyze --provider azure --output markdown
```

Group findings by service, highlight the worst offenders, note if failures are
provider-specific or cross-provider.

### "Show me the actual test failures for storage"

```bash
osdu-quality tests --project storage --output markdown
```

This parses job logs to show individual test class results and specific failure messages.

## Acceptance Test Parity Analysis

Compare what CSP integration tests cover vs what cimpl acceptance tests cover. This identifies coverage gaps — test classes that run in Azure/AWS/GCP CI but have no equivalent in cimpl.

### When to Use

- "what acceptance test gaps does partition have?"
- "how does cimpl test coverage compare to azure for storage?"
- "what's missing from cimpl acceptance tests?"
- "generate a parity report for partition"
- "what would it take to bring cimpl in line with azure integration tests?"

### Method

**Step 1: Fetch test data**

```bash
osdu-quality tests --project <service> --output json
```

**Step 2: Extract test classes by provider and stage**

From the JSON output, group test classes from `stages.acceptance` and `stages.integration` by `cloud_provider`. Each job contains a `test_classes` array with `short_name` and `tests_run`.

**Step 3: Compute the parity gap**

Compare class names:
- **cimpl classes**: all `short_name` values from jobs where `cloud_provider == "cimpl"`
- **CSP classes**: all `short_name` values from jobs where `cloud_provider` is the comparison target (typically `azure`)
- **Gap**: classes present in CSP but absent from cimpl
- **Overlap**: classes present in both

**Step 4: Present the report**

```
## Acceptance Test Parity: <service>

### Current Coverage
| Provider | Stage | Tests | Classes |
|----------|-------|-------|---------|
| cimpl | acceptance | 11 | 4 |
| azure | integration | 83 | 8 |

### Overlap (tested by both)
- GetPartitionByIdApiTest (cimpl: 4, azure: 6)
- HealthCheckApiTest (cimpl: 2, azure: 2)
- ...

### Gap (CSP has, cimpl missing)
| Test Class | CSP Tests | What It Covers |
|------------|-----------|----------------|
| TestCreatePartition | 8 | CRUD create operations |
| TestDeletePartition | 8 | CRUD delete operations |
| TestUpdatePartition | 8 | CRUD update operations |
| ...

### Implementation Plan
To close the gap:
1. The missing test classes exist in `testing/<service>-test-azure/`
2. They can be run locally against a cimpl environment using the `acceptance-test` skill
3. To add them to CI, the `cimpl-acceptance-test` pipeline job needs to run the
   `testing/<service>-test-azure/` module with Keycloak OIDC auth instead of Azure SP
```

### Key Context

- **cimpl acceptance tests** run the standalone `<service>-acceptance-test/` module (smoke-level)
- **CSP integration tests** (especially azure) run `testing/<service>-test-azure/` which includes deeper CRUD coverage
- The gap exists because cimpl CI uses the standalone acceptance module, not the provider-specific test module
- The `acceptance-test` skill can run the deeper tests locally against a cimpl environment right now
- Closing the CI gap requires updating the cimpl pipeline job to use the provider test module with Keycloak auth

### Multiple Services

When asked about parity across multiple services, run `osdu-quality tests` for each and present a summary table:

```
| Service | cimpl Tests | Azure Tests | Gap Classes | Coverage % |
|---------|-------------|-------------|-------------|------------|
| partition | 11 | 83 | 8 | 13% |
| storage | 154 | 280 | 5 | 55% |
| legal | 120 | 0 | 0 | — |
```

Coverage % = cimpl tests / max(cimpl, azure) tests.

## Cross-Domain Queries

For comprehensive project health, combine with sibling skills:

```bash
# Full health picture for a service
osdu-quality analyze --project partition --output markdown   # test reliability
osdu-activity mr --project partition --output markdown       # open MRs
osdu-activity pipeline --project partition --output markdown  # pipeline status
```

Synthesize into a unified health assessment.

## Reference Documentation

- [reference/commands.md](reference/commands.md) — Full CLI options, JSON output structures
- [reference/troubleshooting.md](reference/troubleshooting.md) — Quality-specific issues
- [../../reference/osdu-cli-reference.md](../../reference/osdu-cli-reference.md) — Installation, auth, output formats, common errors
