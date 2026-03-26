# OSDU Claude Plugins

![AI: Enabled](https://img.shields.io/badge/AI-enabled-purple.svg)
![Status: Experimental](https://img.shields.io/badge/status-experimental-orange.svg)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

### An agentic system for OSDU, built for Claude Code

A Claude Code marketplace that bundles specialized agents, skills, and live platform access into two installable plugins for infrastructure automation, platform analytics, QA testing, and knowledge management across OSDU Community Implementation environments on Azure.

Built for OSDU maintainers, platform engineers, QA contributors, and community operators.

| Plugin | Components | What you use it for |
|---|---|---|
| **osdu** | @osdu agent, 21 skills | Builds, dependencies, MRs, tests, live platform queries, knowledge management |
| **cimpl** | @cimpl agent, 3 skills | Terraform, Helm, AKS, debugging, verification |

## Getting Started

Requires [Claude Code](https://claude.ai/claude-code).

```bash
# Install from marketplace
claude plugin marketplace add https://github.com/danielscholl/claude-osdu
claude plugin install osdu
claude plugin install cimpl
```

### Try It Out

```
> give me a morning briefing
> what pipelines are failing across OSDU?
> check the health of my environment
> run acceptance tests for partition
> review MR !845
```

## What's Inside

**2 plugins**, **24 skills**, and **7 agents** for broad platform operations and deep infrastructure workflows.

### osdu plugin

| Category | Skills |
|---|---|
| Knowledge | brain, briefing, learn, consolidate |
| Analytics | osdu-activity, osdu-engagement, osdu-quality |
| Build & Deps | maven, dependency-scan, build-runner, remediate |
| QA Testing | osdu-qa, acceptance-test |
| Git Workflow | send, mr-review, contribute, glab, fossa, maintainer |
| Workspace | clone, setup |

**Agents:** osdu (orchestrator), build-runner, qa-runner, qa-analyzer, qa-comparator, qa-reporter

**MCP Server:** Uses [osdu-mcp-server](https://pypi.org/project/osdu-mcp-server/) for live OSDU platform access (31 tools across search, storage, schema, entitlements, legal, partition)

### cimpl plugin

| Category | Skills |
|---|---|
| Infrastructure | iac, health, setup |

**Agent:** cimpl (infrastructure specialist)

## Testing

Uses the [skilltest](https://github.com/danielscholl/claude-sdlc) four-layer test framework.

```bash
make test                    # L1 + L2 + pytest (fast)
make lint                    # L1: Structure validation
make unit                    # L2: Trigger eval dry-run
make integration P=osdu      # L3: Multi-turn session tests
make benchmark P=osdu S=brain  # L4: Skill value comparison
make report                  # Test inventory
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow.

## License

Licensed under the [Apache License 2.0](LICENSE).
