#!/bin/bash
# OSDU QA Post-Test Result Saving Hook
# This hook runs after test execution to save results for historical tracking

set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RESULTS_DIR="$SKILL_DIR/results"

# Read JSON input from stdin
INPUT=$(cat)

# Extract the command that was run
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")

# Only save results for osdu_test.py run commands
if [[ "$COMMAND" != *"osdu_test.py"* ]] || [[ "$COMMAND" != *"run"* ]]; then
    exit 0
fi

# Extract the tool output (test results)
OUTPUT=$(echo "$INPUT" | jq -r '.tool_output // empty' 2>/dev/null || echo "")

# If we have output, try to save it
if [[ -n "$OUTPUT" ]]; then
    # Get current environment
    ENV=$(uv run "$SKILL_DIR/scripts/env_manager.py" status --json 2>/dev/null | jq -r '.environment // "unknown"' || echo "unknown")
    ENV_SAFE=$(echo "$ENV" | tr '/' '_')

    # Generate timestamp
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)

    # Create results directory if needed
    mkdir -p "$RESULTS_DIR"

    # Save results
    RESULT_FILE="$RESULTS_DIR/${TIMESTAMP}_${ENV_SAFE}.txt"
    echo "$OUTPUT" > "$RESULT_FILE"

    echo "Results saved to: $RESULT_FILE" >&2
fi

exit 0
