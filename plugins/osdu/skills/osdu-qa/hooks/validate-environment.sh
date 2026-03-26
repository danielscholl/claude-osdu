#!/bin/bash
# OSDU QA Pre-Test Environment Validation Hook
# This hook runs before test execution to validate the environment is ready

set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

# Read JSON input from stdin (tool input is passed as JSON)
INPUT=$(cat)

# Extract the command being run
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")

# Only validate for osdu_test.py run commands
if [[ "$COMMAND" != *"osdu_test.py"* ]] || [[ "$COMMAND" != *"run"* ]]; then
    exit 0
fi

# Check if environment is configured
if ! uv run "$SKILL_DIR/scripts/env_manager.py" status --quiet 2>/dev/null; then
    echo "Error: No OSDU environment configured." >&2
    echo "Run '/osdu-qa env use <environment>' first." >&2
    echo "" >&2
    echo "Run '/osdu-qa env' to see available environments." >&2
    exit 2  # Exit code 2 blocks the operation
fi

# Check connectivity (warning only, don't block)
if ! uv run "$SKILL_DIR/scripts/osdu_test.py" check --quiet 2>/dev/null; then
    echo "Warning: Environment connectivity issues detected." >&2
    echo "Tests may fail due to authentication or network problems." >&2
    # Exit 0 to continue (just a warning)
fi

exit 0
