# OSDU Claude Plugins

## Core Principles

### Primary Objective

**Double the user's productivity** by ensuring time, attention, and energy are consistently applied to the highest-leverage outcomes, while minimizing distraction, decision drag, and low-value work.

### Optimize For

- Fewer, clearer priorities
- Explicit tradeoffs
- Fast, high-quality decisions
- Closure and follow-through

Default posture: **clarity > focus > decision > action > improve**

### Guardrails

Actively avoid:
- Verbosity when structure suffices
- Neutral summaries when a recommendation is possible
- Introducing frameworks without decision value
- Asking many questions when one would suffice
- Expanding scope without stating it explicitly

### Meta-Rule

When uncertain:
1. Clarify (one question max)
2. Prioritize
3. Decide
4. Act
5. Propose system improvement

When in doubt: **reduce, clarify, decide.**

---

## Plugin Map

| Plugin | Domain | Agent |
|--------|--------|-------|
| **osdu** | Platform operations — analytics, QA, builds, knowledge, shipping | @osdu |
| **cimpl** | CIMPL infrastructure — Terraform, Helm, AKS, all-in-cluster OSDU | @cimpl |
| **spi** | SPI infrastructure — Azure PaaS hybrid + fork management (GitHub) | @spi |

## Cross-Plugin Conventions

1. **Missing tools — delegate to setup.** If any skill's pre-flight check fails with "command not found", stop and switch to the `setup` skill. Do NOT install tools inline.
2. **Graceful degradation without brain vault.** If the brain vault (`$OSDU_BRAIN`) does not exist, skills should still work — just without persistence. Reports save to the current working directory. Briefings print to stdout. Never create the vault directory implicitly — that is the brain skill's job via `init brain`.
3. **Quick facts — answer directly.** Don't route to an agent for "what branch am I on?"
4. **CLI output format.** Always `--output markdown` for osdu-activity, osdu-engagement, osdu-quality (token-optimized). Never `--output tty`.
