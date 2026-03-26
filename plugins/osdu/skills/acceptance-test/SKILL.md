---
name: acceptance-test
allowed-tools: Bash, Read, Glob
description: >-
  Run Java acceptance or integration tests from an OSDU service repository against a live deployed environment. Resolves environment configuration, auth credentials, and SSL truststore automatically.
  Use when the user says 'run acceptance tests for partition', 'test the storage service against my environment', 'execute integration tests for legal', or 'verify partition with acceptance tests'.
  Not for: test reliability analysis (use osdu-quality), building services (use build-runner), checking environment health (use health), or unit tests without a live service.
---

# Acceptance Test Runner

Run Java acceptance and integration tests from OSDU service repositories against a live cimpl environment. The `javatest_acceptance.py` script handles environment resolution, Config.java parsing, secure credential handling, SSL truststore setup, and surefire result parsing automatically.

## When to Use This Skill

- User asks to run acceptance tests, integration tests, or e2e tests for an OSDU service
- User wants to verify a service against their deployed cimpl environment
- User asks to test a specific service (partition, storage, legal, etc.) against a live endpoint
- User says "acceptance test", "integration test", or "service test" for a named service

## When NOT to Use This Skill

| Request | Use Instead |
|---------|-------------|
| Run Postman/Newman API test collections | osdu-qa |
| Build or compile a service | build-runner |
| Check environment health | health |
| Run unit tests (no live service needed) | build-runner |
| Check test reliability/flakiness | osdu-quality |
| Acceptance test parity/coverage gap analysis | osdu-quality |

## Quick Start

```bash
# Verify required tools
java --version 2>/dev/null
mvn --version 2>/dev/null
```

If either command is not found, **stop and use the `setup` skill** to install missing dependencies.

## Usage

```bash
# Run acceptance tests for a service
uv run skills/acceptance-test/scripts/javatest_acceptance.py --service <name>

# Preview what would run (no execution)
uv run skills/acceptance-test/scripts/javatest_acceptance.py --service <name> --dry-run

# Override workspace or provisioning repo path
uv run skills/acceptance-test/scripts/javatest_acceptance.py --service <name> \
  --workspace /path/to/osdu-workspace \
  --provisioning-dir /path/to/cimpl-azure-provisioning

# Force a specific test pattern
uv run skills/acceptance-test/scripts/javatest_acceptance.py --service <name> --pattern A
```

| Option | Description |
|--------|-------------|
| `--service` | OSDU service name (partition, storage, legal, etc.) |
| `--provisioning-dir` | Override path to cimpl-azure-provisioning repo |
| `--workspace` | Override OSDU workspace path (default: `$OSDU_WORKSPACE`) |
| `--pattern` | Force test pattern: `A` (acceptance-test) or `B` (test-azure). Default: auto-detect |
| `--skip-ssl-setup` | Skip SSL truststore creation |
| `--dry-run` | Show resolved config and commands without executing |

## What the Script Does

1. **Resolves environment** from `.azure/<env>/.env` in the provisioning repo (same logic as the osdu extension's `azd-env.mjs`)
2. **Finds service repo** under `$OSDU_WORKSPACE/<service>` (supports worktree layout)
3. **Detects test pattern**: Pattern A (`<service>-acceptance-test/`) preferred for cimpl (uses OIDC auth), Pattern B (`testing/<service>-test-azure/`) as fallback
4. **Parses Config.java** and auth utility files to discover required env vars via `System.getenv()` calls
5. **Maps azd values** to test env vars (service URLs, tenant, OIDC credentials)
6. **Creates SSL truststore** with full cert chains for both OSDU and Keycloak endpoints (handles Let's Encrypt staging certs; cached for 24h at `~/.osdu-acceptance-test/truststore.jks`)
7. **Auto-detects community Maven settings** (`.mvn/community-maven.settings.xml`) and passes `-s` to Maven
8. **Builds test-core** if Pattern B, then runs tests via Maven
8. **Parses surefire XML** reports and prints structured results

**Security:** Credentials are passed to Maven via subprocess environment variables — they never appear on the command line or in log output. The `--dry-run` output masks all sensitive values.

## AI Execution (Internal)

**Always use `--dry-run` first** to show the user what will be executed and let them confirm.

```bash
# Step 1: Preview
uv run skills/acceptance-test/scripts/javatest_acceptance.py --service partition --dry-run

# Step 2: Execute (after user confirms)
uv run skills/acceptance-test/scripts/javatest_acceptance.py --service partition
```

**Present the script output directly to the user.** Do NOT summarize unless requested.

## Error Handling

| Error | Action |
|-------|--------|
| Service repo not found | Offer to clone with `clone` skill |
| No acceptance tests found | Report — not all services have them |
| Provisioning repo not found | Ask user for provisioning repo path or set `$OSDU_WORKSPACE` |
| Auth failure (401/403) | Check client secret, verify Keycloak is running via health skill |
| Service unreachable | Check service is deployed via health skill |
| Test-core build fails | Report build error, check for version mismatches |
| Maven not found | Delegate to setup skill |
| SSL/PKIX errors | Run without `--skip-ssl-setup`, ensure openssl and keytool are available |

## Multiple Services

When asked to test multiple services (e.g., "run acceptance tests for partition and storage"):
1. Run the script once per service
2. Provide a combined summary table at the end

## Integration

**Before running tests**, consider using `osdu-quality tests --project <service> --output json` to check
acceptance test parity. This shows what the CI pipeline already runs per provider and highlights
coverage gaps between CSP integration tests and cimpl acceptance tests. If the user asks about
test gaps or parity, route to the `osdu-quality` skill instead.

After reporting results:
- If the `brain` skill is available, offer to store the report in the vault
- If failures occur, suggest using the specific service's logs or health skill to investigate
- If all tests pass, this confirms the service is functioning correctly against the live environment

## References

- [environment-resolution.md](references/environment-resolution.md) — How env vars are resolved from azd
- [service-test-patterns.md](references/service-test-patterns.md) — Pattern A vs B test structures
- [scripts/javatest_acceptance.py](scripts/javatest_acceptance.py) — The test runner script
