---
name: build-runner
allowed-tools: Bash, Read, Glob
description: >-
  Execute build/test commands and return structured summaries. Use for Maven, Node, or
  Python builds during dependency remediation.
  Use when the user says "build", "compile", "test", "verify", "run tests", "maven verify",
  "unit tests", or "build summary".
  Not for: deployment, CI/CD pipeline management, or code generation.
---

# Build Runner

Execute build commands and return concise summaries to preserve main agent context during dependency remediation.

## Purpose

When running builds, the output can be 5,000+ lines. This skill:
1. Executes the appropriate build command
2. Captures all output internally
3. Parses for key information
4. Returns only a structured summary (~10 lines)

This preserves the main agent's context for decision-making across multiple build cycles. The `@osdu` agent spawns build-runner as a sub-agent for exactly this reason.

## Path Resolution

Projects are found in the OSDU workspace:
- `$OSDU_WORKSPACE/<service-name>/` (regular clone)
- `$OSDU_WORKSPACE/<service-name>/master/` (worktree clone)
- Default: current working directory if OSDU_WORKSPACE is not set

The `javatest.py` script is part of this plugin at `skills/maven/scripts/javatest.py`.

## Pre-Flight Checks

### 1. Find the project

Check if the service exists in the workspace:

```bash
OSDU_WORKSPACE="${OSDU_WORKSPACE:-$(pwd)}"
ls "$OSDU_WORKSPACE/<service-name>/pom.xml" 2>/dev/null || \
ls "$OSDU_WORKSPACE/<service-name>/master/pom.xml" 2>/dev/null
```

If the project is not found, **use the `clone` skill to clone it first**, then continue with the build.

### 2. Check build tools

```bash
java --version 2>/dev/null && mvn --version 2>/dev/null
```

If build tools are missing, **stop and use the `setup` skill** to install them.

## Supported Build Systems

| System | Detection | Preferred Tool | Fallback |
|--------|-----------|---------------|----------|
| Maven (OSDU) | `pom.xml` + OSDU structure | `javatest.py` | `mvn` directly |
| Maven (generic) | `pom.xml` | — | `mvn compile/test/verify` |
| Node | `package.json` | — | `npm test`, `npm run build` |
| Python | `pyproject.toml` | — | `pytest`, `pip install` |

## Execution

### For OSDU Maven Projects (Preferred)

Use the `javatest.py` script for reliable, cross-platform execution with automatic profile handling.

```bash
# Use the javatest.py script from the maven skill
uv run skills/maven/scripts/javatest.py --project <name> --validate

# Compile only
uv run skills/maven/scripts/javatest.py --project <name> --compile

# Run tests
uv run skills/maven/scripts/javatest.py --project <name> --test

# Package
uv run skills/maven/scripts/javatest.py --project <name> --package
```

**If script not found:** Fall back to generic Maven commands (see below).

**Key features:**
- `--validate` automatically detects shared modules and builds with ALL profiles
- Cross-platform (Windows, Linux, macOS)
- Automatic service discovery
- Structured error handling

**When to use `--validate`:**
- After modifying shared modules (names containing: core, common, shared, api, model)
- When request mentions "shared module" or "all profiles"
- For pre-commit validation of dependency changes

### Worktree Build Fix

When building in a bare clone + worktree layout, the `git-commit-id` Maven plugin fails because it can't find `.git/`. **Always add this flag for worktree builds:**

```bash
-Dmaven.gitcommitid.skip=true
```

Detect worktree layout by checking if `.git` is a file (not a directory):

```bash
# If .git is a file → worktree layout → skip git-commit-id
[ -f .git ] && GIT_SKIP="-Dmaven.gitcommitid.skip=true" || GIT_SKIP=""
```

### For Generic Maven Projects

```bash
# Compile only
cd <project-path> && mvn compile -q $GIT_SKIP 2>&1

# Compile + unit tests
cd <project-path> && mvn test -q $GIT_SKIP 2>&1

# Full build with all tests
cd <project-path> && mvn verify -q $GIT_SKIP 2>&1
```

### For Node Projects

```bash
cd <project-path> && npm test 2>&1
cd <project-path> && npm run build 2>&1
```

### For Python Projects

```bash
cd <project-path> && pytest 2>&1
cd <project-path> && pip install -e . 2>&1
```

## Response Format

ALWAYS respond with this exact structure:

```
Build: <project-name>
Command: <command-run>
Status: PASSED | FAILED
Duration: <time>

Tests: <passed> passed, <failed> failed, <skipped> skipped

Failures (if any):
  - <TestClass>#<method>: <brief error, max 100 chars>

Compilation Errors (if any):
  - <file>:<line>: <brief error>
```

### Example: Successful Build

```
Build: partition
Command: javatest.py --project partition --validate
Status: PASSED
Duration: 2m 15s

Tests: 147 passed, 0 failed, 2 skipped
Profiles validated: core, azure, gc, aws, ibm
```

### Example: Failed Build

```
Build: partition
Command: javatest.py --project partition --validate
Status: FAILED
Duration: 1m 42s

Tests: 145 passed, 2 failed, 2 skipped

Failures:
  - AuthServiceTest#testLogin: NullPointerException at AuthService.java:42
  - UserRepoTest#testSave: AssertionError - expected 1 but was 0
```

### Example: Compilation Error

```
Build: partition
Command: javatest.py --project partition --compile
Status: FAILED
Duration: 0m 23s

Compilation Errors:
  - src/main/java/AuthService.java:42: cannot find symbol - method getUser()
  - src/main/java/UserRepo.java:15: incompatible types
```

## Parsing Tips

### Maven Output Parsing

Look for these patterns:
- `BUILD SUCCESS` or `BUILD FAILURE` — overall status
- `Tests run: X, Failures: Y, Errors: Z, Skipped: W` — test counts
- `[ERROR]` lines — compilation or test errors
- `Time elapsed:` — duration

### Test Failure Details

Extract from surefire reports or console output:
- Test class and method name
- Exception type
- Brief error message (first line only)

## Important Rules

1. **Always return structured summary** — never dump raw output
2. **Keep summaries brief** — max 10-15 lines
3. **Include test counts** — main agent needs these for baseline comparison
4. **List all failures** — but keep descriptions brief (max 100 chars each)
5. **Report compilation errors** — with file:line references
6. **Include duration** — helps identify performance issues
7. **Use javatest.py for OSDU** — it handles profiles automatically
8. **Use --validate for shared modules** — ensures all profiles are tested
9. **Missing tools → setup skill** — don't try to install Java/Maven inline
