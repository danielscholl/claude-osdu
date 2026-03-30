---
description: >-
  Prime understanding of the OSDU workspace -- discover cloned repos, available
  tools, plugin capabilities, and current context. Quick, low-token overview.
---

Build a lightweight understanding of the current OSDU workspace state.

**IMPORTANT:** Minimize context usage -- aim for under 15k tokens total. Do NOT read
source code, test files, or agent definitions. Do NOT launch subagents.

## Phase 1: Workspace Discovery

Determine the workspace root and scan for cloned repos.

```bash
OSDU_WORKSPACE="${OSDU_WORKSPACE:-$(pwd)}"
echo "Workspace: $OSDU_WORKSPACE"
```

**Detect cloned repos** -- look for bare clone (worktree) and standard layouts:
```bash
# Worktree repos (.bare/ directory)
for d in "$OSDU_WORKSPACE"/*/; do
  if [ -d "$d/.bare" ]; then
    repo=$(basename "$d")
    branches=$(ls -d "$d"/*/ 2>/dev/null | xargs -I{} basename {} | grep -v '^\.' | tr '\n' ' ')
    echo "  $repo (worktree): $branches"
  elif [ -d "$d/.git" ] && [ ! -f "$d/.git" ]; then
    repo=$(basename "$d")
    branch=$(git -C "$d" branch --show-current 2>/dev/null)
    echo "  $repo (standard): $branch"
  fi
done
```

Report: repo count, layout type (worktree vs standard), branches per repo.

## Phase 2: Tool Check

Check which tools are available. Report only presence/absence -- do not run `--version`.

```bash
for tool in wt git glab gh aipr osdu-activity osdu-engagement osdu-quality uv trivy; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "  $tool: available"
  else
    echo "  $tool: not found"
  fi
done
```

## Phase 3: Current Context

If inside a specific repo (not at workspace root), show:

```bash
git branch --show-current 2>/dev/null
git --no-pager status --short 2>/dev/null
git --no-pager log --oneline -3 2>/dev/null
```

If at workspace root, skip this phase.

## Phase 4: Plugin Inventory

List what the osdu plugin provides -- **names only**, do not read contents.

- **Commands**: clone, prime, qa, ship
- **Skills**: list directory names under `skills/`
- **Agents**: list filenames under `agents/`
- **MCP**: note if osdu-mcp-server is configured

## Phase 5: Summary

Present a compact overview:

```
Workspace:  <path> — <N> repos (<worktree|standard> layout)
Repos:      <comma-separated list>
Tools:      <available tools>
Missing:    <missing tools, if any>
Context:    <current repo/branch if applicable>
Plugin:     <N> skills, <N> agents, <N> commands

Suggested next actions:
  - <based on what's available and missing>
```

Keep suggestions actionable: "clone core" if no repos, "run acceptance tests" if repos
are cloned, "/setup" if tools are missing.

$ARGUMENTS
