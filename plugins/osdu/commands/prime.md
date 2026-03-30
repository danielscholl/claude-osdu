---
description: >-
  Prime understanding of the OSDU workspace -- discover cloned repos, available
  tools, plugin capabilities, and current context. Quick, low-token overview.
---

Build a lightweight understanding of the current OSDU workspace state.

**IMPORTANT:** Minimize context usage -- aim for under 15k tokens total. Do NOT read
source code, test files, or agent definitions. Do NOT launch subagents.

## Argument Handling

Parse `$ARGUMENTS` to determine mode:

- **No argument**: Full workspace scan (all phases below).
- **Repo name provided** (e.g., `osdu-spi-infra`): Focus on that single repo. Skip Phase 1
  full scan and Phase 4 plugin inventory. Run Phases 2, 3 (targeted), and 5 (targeted).

When a repo name is given, resolve its path:
```bash
OSDU_WORKSPACE="${OSDU_WORKSPACE:-$(pwd)}"
REPO_NAME="<argument>"  # from $ARGUMENTS
REPO_PATH=""

# Check worktree layout first
if [ -d "$OSDU_WORKSPACE/$REPO_NAME/.bare" ]; then
  REPO_PATH="$OSDU_WORKSPACE/$REPO_NAME"
  LAYOUT="worktree"
  # Find the default worktree (main, master, or first available)
  for branch in main master; do
    if [ -d "$REPO_PATH/$branch" ]; then
      WORK_DIR="$REPO_PATH/$branch"
      break
    fi
  done
  [ -z "$WORK_DIR" ] && WORK_DIR=$(ls -d "$REPO_PATH"/*/ 2>/dev/null | grep -v '/\.' | head -1)
elif [ -d "$OSDU_WORKSPACE/$REPO_NAME/.git" ]; then
  REPO_PATH="$OSDU_WORKSPACE/$REPO_NAME"
  WORK_DIR="$REPO_PATH"
  LAYOUT="standard"
fi
```

If the repo is not found, report the error and list available repos.

## Phase 1: Workspace Discovery (skip if repo argument given)

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

## Phase 3: Repo Context

**If a repo argument was given**, show detailed context for that repo:

```bash
# Run from the resolved WORK_DIR
git -C "$WORK_DIR" branch --show-current 2>/dev/null
git -C "$WORK_DIR" --no-pager status --short 2>/dev/null
git -C "$WORK_DIR" --no-pager log --oneline -5 2>/dev/null
```

Also show:
- **Worktree branches**: list all worktree directories if worktree layout
- **Remote URL**: `git -C "$WORK_DIR" remote get-url origin 2>/dev/null`
- **Build system**: check for pom.xml, package.json, Makefile, build.gradle
- **CLAUDE.md**: note if present (do not read contents)
- **Key directories**: `ls` top-level dirs only (one line)

**If no argument and inside a specific repo** (not at workspace root), show:

```bash
git branch --show-current 2>/dev/null
git --no-pager status --short 2>/dev/null
git --no-pager log --oneline -3 2>/dev/null
```

If at workspace root with no argument, skip this phase.

## Phase 4: Plugin Inventory (skip if repo argument given)

List what the osdu plugin provides -- **names only**, do not read contents.

- **Commands**: clone, prime, qa, ship
- **Skills**: list directory names under `skills/`
- **Agents**: list filenames under `agents/`
- **MCP**: note if osdu-mcp-server is configured

## Phase 5: Summary

**If a repo argument was given**, present a focused repo overview:

```
Repo:       <name> (<worktree|standard> layout)
Path:       <path>
Branch:     <current branch>
Worktrees:  <list of worktree branches, if applicable>
Remote:     <origin URL>
Build:      <Maven|Node|Make|Gradle|unknown>
Status:     <clean | N modified files>
Recent:     <last 3 commit subjects>

Suggested next actions:
  - <based on repo state>
```

**If no argument**, present a compact workspace overview:

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
