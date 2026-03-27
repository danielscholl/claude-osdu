# Contributing

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Claude Code](https://claude.ai/claude-code)
- Node.js 18+ (for MCP server)

## Project Layout

```
claude-osdu/
├── .claude-plugin/marketplace.json    # Marketplace registry
├── CLAUDE.md                          # Cross-cutting instructions
├── Makefile                           # Test runner
├── plugins/
│   ├── osdu/                          # Platform operations plugin
│   │   ├── .claude-plugin/plugin.json
│   │   ├── .mcp.json                  # MCP server config (osdu-mcp-server from PyPI)
│   │   ├── CLAUDE.md
│   │   ├── agents/                    # 6 agents
│   │   ├── commands/                  # Slash commands
│   │   ├── skills/                    # 21 skills
│   │   ├── reference/                 # Shared reference data
│   │   └── tests/                     # Evals and unit tests
│   └── cimpl/                         # Infrastructure plugin
│       ├── .claude-plugin/plugin.json
│       ├── CLAUDE.md
│       ├── agents/                    # 1 agent
│       ├── skills/                    # 3 skills
│       └── tests/                     # Evals and unit tests
```

## Test Framework

Four-layer test framework using [skilltest](https://github.com/danielscholl/claude-sdlc) scripts.

### L1 — Structure Validation

Checks plugin.json, agent/skill frontmatter, naming conventions, cross-references.

```bash
make lint              # All plugins
make lint P=osdu       # One plugin
```

### L2 — Trigger Accuracy

Validates that skill descriptions trigger for the right prompts. Each skill needs a trigger eval JSON at `tests/evals/triggers/{skill-name}.json` with 8+ positive and 8+ negative queries.

```bash
make unit              # Dry-run all evals
make unit P=osdu       # One plugin
```

### L3 — Integration Sessions

Multi-turn conversation tests validating routing and context retention.

```bash
make integration P=osdu S=brain   # One skill
make integration P=osdu           # All osdu scenarios
```

### L4 — Value Benchmarking

Compares skill performance (with skill vs without) to determine if the skill adds value.

```bash
make benchmark P=osdu S=brain
```

### Quick Check

```bash
make test              # L1 + L2 + pytest (run after every change)
```

## Adding a New Skill

1. Create `plugins/{plugin}/skills/{name}/SKILL.md` with frontmatter:
   ```yaml
   ---
   name: my-skill
   allowed-tools: Bash, Read, Glob
   description: >-
     What this skill does.
     Use when [trigger conditions].
     Not for: [exclusions].
   ---
   ```
2. Add scripts, reference docs, and templates as needed in subdirectories
3. Create `tests/evals/triggers/{name}.json` with 8+ positive and 8+ negative queries
4. Run `make lint P={plugin}` to validate structure
5. Run `make unit P={plugin}` to validate trigger eval balance
6. Optionally create a session scenario at `tests/evals/scenarios/{name}-workflow.json`

## Adding a New Agent

1. Create `plugins/{plugin}/agents/{name}.md` with frontmatter:
   ```yaml
   ---
   name: my-agent
   description: >-
     What this agent does and when to use it.
   tools: Read, Glob, Grep, Bash
   model: sonnet
   ---
   ```
2. Register in `.claude-plugin/plugin.json` agents array
3. Create `tests/evals/triggers/{name}.json` for trigger accuracy testing
4. Run `make test P={plugin}` to validate

## Version Management

Three files carry version numbers that must stay in sync:
- `.claude-plugin/marketplace.json` — marketplace version
- `plugins/osdu/.claude-plugin/plugin.json` — osdu plugin version
- `plugins/cimpl/.claude-plugin/plugin.json` — cimpl plugin version

**Rule:** when a plugin's files change, its version must be bumped. The marketplace version is always the max of all plugin versions.

### Quick Commands

```bash
./scripts/version.sh check          # Verify bumps (runs in CI on PRs)
./scripts/version.sh bump patch     # Bump all plugins
./scripts/version.sh bump minor osdu  # Bump one plugin
./scripts/version.sh sync           # Sync marketplace to max plugin version
```

### CI Enforcement

- **PRs to main** automatically run the version check. If you changed plugin files without bumping, the check fails.
- **Manual bump** via GitHub Actions: run the "Version Bump" workflow from the Actions tab.

## Conventions

- Skill names: lowercase kebab-case, must match directory name
- Agent names: lowercase kebab-case, must match filename (without `.md`)
- Descriptions: 20-1024 characters, include "Use when" and "Not for" clauses
- Scripts: Python 3.11+, use `uv run` for execution
- Tests: pytest for unit tests, JSON eval sets for trigger/session testing
