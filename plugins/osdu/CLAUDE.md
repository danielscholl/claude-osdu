# OSDU Platform Plugin

## Delegation Model

The default context **observes, plans, and ships**. The `osdu:osdu` agent **operates** on platform services.

```
Default ──→ osdu:osdu (platform operations)
```

**Simple queries** (MR lists, pipeline status, contribution stats): Handle directly using CLI tools — no need to spawn an agent.

**Procedural skills** (clone, setup, send, glab, mr-review, contribute, osdu-data-load): Execute inline. These skills contain step-by-step procedures — run them directly in the current context. Do NOT delegate them to an agent.

**Complex operations** (test runs, builds, failure analysis, dependency remediation): Delegate to `osdu:osdu` via the Agent tool.

## Agent Inventory

When delegating to an agent, use the **fully qualified type** (plugin:agent format).

| `subagent_type` | Purpose | When to spawn |
|-----------------|---------|---------------|
| `osdu:osdu` | Platform orchestrator | Builds, test runs, dependency remediation, complex multi-step operations |
| `osdu:build-runner` | Build execution | Context isolation for Maven/Node builds (output is massive) |
| `osdu:qa-runner` | Test execution | Parallel QA test runs across environments |
| `osdu:qa-analyzer` | Failure analysis | Root cause analysis of test failures |
| `osdu:qa-comparator` | Environment comparison | Cross-environment result deltas |
| `osdu:qa-reporter` | Report generation | QA dashboards and formatted reports |

## Skill Ownership

### Shared Skills (execute directly in current context — do NOT delegate)

brain, briefing, learn, consolidate, glab, send, mr-review, contribute, clone, setup,
osdu-activity, osdu-engagement, osdu-quality, osdu-data-load

### Specialist Skills (loaded by `osdu:osdu` only)

maven, dependency-scan, build-runner, remediate, acceptance-test, osdu-qa,
fossa, maintainer

## Rules

1. **Observe vs operate** is the key boundary. Understanding state, planning, or shipping → stay in default. Changing platform services → delegate to `osdu:osdu`.
2. **When two agents could handle it**, pick the one whose domain is the primary concern.
3. **Ambiguous?** State the inferred route in one line before proceeding.
