---
name: Environment Management
description: OSDU QA Testing - Environment - Instructions for handling `/osdu-qa env` commands.
---

Instructions for handling `/osdu-qa env` commands.

## Commands

| Command | Action |
|---------|--------|
| `env` | List available environments |
| `env list` | List available environments |
| `env use <target>` | Switch to an environment |
| `env status` | Show current configuration |
| `env audit` | Audit all environments (list format) |
| `env audit --check` | Audit with API health checks |
| `env add <target>` | Add a new environment |
| `env remove <target>` | Remove an environment |

## CLI Entry Point

```bash
uv run skills/osdu-qa/scripts/env_manager.py <command>
```

## Intent Mapping

| User Says | Command |
|-----------|---------|
| `env` | `list` |
| `env list` | `list` |
| `env use <platform>/<env>` | `use <platform>/<env>` |
| `env status` | `status` |
| `env add <platform>/<env> --host ...` | `add <platform>/<env> --host ... --partition ... --auth-type ...` |
| `env remove <platform>/<env>` | `remove <platform>/<env> --confirm` |

## Environments

Environments are user-local configuration stored in `config/environments.json` (gitignored).
Run `env list` to see configured environments.

### Adding Environments

```bash
# Azure AD environment
uv run skills/osdu-qa/scripts/env_manager.py add azure/myenv \
  --host osdu-myenv.example.com \
  --partition opendes \
  --auth-type azure-ad

# Keycloak environment
uv run skills/osdu-qa/scripts/env_manager.py add cimpl/qa \
  --host osdu.qa.example.org \
  --partition osdu \
  --auth-type keycloak \
  --cluster cluster-name \
  --namespace qa \
  --credential-var EXAMPLE_TEST_COLLECTION_CONFIG
```

Or copy `reference/environments.example.json` to `config/environments.json` and customize.

### Removing Environments

```bash
uv run skills/osdu-qa/scripts/env_manager.py remove <platform>/<env> --confirm
```

## First-Time Setup

1. Add your environments using `env add` or by copying the example config
2. Sync credentials from GitLab:

```bash
uv run skills/osdu-qa/scripts/sync_credentials.py sync
```
