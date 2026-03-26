# OSDU Platform Plugin

## Delegation Model

The default context **observes, plans, and ships**. The @osdu agent **operates** on platform services.

```
Default ──→ @osdu (platform operations)
```

**Simple queries** (MR lists, pipeline status, contribution stats): Handle directly using CLI tools — no need to spawn @osdu.

**Complex operations** (test runs, builds, failure analysis, dependency remediation): Delegate to @osdu via the Agent tool.

## Agent Inventory

| Agent | Purpose | When to spawn |
|-------|---------|---------------|
| @osdu | Platform orchestrator | Builds, test runs, dependency remediation, complex multi-step operations |
| build-runner | Build execution | Context isolation for Maven/Node builds (output is massive) |
| qa-runner | Test execution | Parallel QA test runs across environments |
| qa-analyzer | Failure analysis | Root cause analysis of test failures |
| qa-comparator | Environment comparison | Cross-environment result deltas |
| qa-reporter | Report generation | QA dashboards and formatted reports |

## Skill Ownership

### Shared Skills (available to default context and @osdu)

brain, briefing, learn, consolidate, glab, send, mr-review, contribute, clone, setup,
osdu-activity, osdu-engagement, osdu-quality

### Specialist Skills (loaded by @osdu only)

maven, dependency-scan, build-runner, remediate, acceptance-test, osdu-qa,
fossa, maintainer

## Rules

1. **Observe vs operate** is the key boundary. Understanding state, planning, or shipping → stay in default. Changing platform services → delegate to @osdu.
2. **When two agents could handle it**, pick the one whose domain is the primary concern.
3. **Ambiguous?** State the inferred route in one line before proceeding.
