#!/usr/bin/env bash
# Version management helper for claude-osdu marketplace plugins.
# Usage:
#   version.sh check              — verify changed plugins have version bumps
#   version.sh bump <type> [plugin] — bump versions (patch|minor|major), optional plugin scope
#   version.sh sync               — sync marketplace version to max plugin version
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MARKETPLACE_JSON="$REPO_ROOT/.claude-plugin/marketplace.json"

# ── Helpers ──────────────────────────────────────────────────────────────────

get_version() {
  local file="$1"
  grep '"version"' "$file" | head -1 | sed 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/'
}

set_version() {
  local file="$1" new_version="$2"
  sed -i '' "s/\"version\"[[:space:]]*:[[:space:]]*\"[^\"]*\"/\"version\": \"$new_version\"/" "$file"
}

bump_version() {
  local current="$1" bump_type="$2"
  local major minor patch
  IFS='.' read -r major minor patch <<< "$current"
  case "$bump_type" in
    major) echo "$((major + 1)).0.0" ;;
    minor) echo "$major.$((minor + 1)).0" ;;
    patch) echo "$major.$minor.$((patch + 1))" ;;
    *) echo "ERROR: invalid bump type: $bump_type" >&2; exit 1 ;;
  esac
}

version_gt() {
  # Returns 0 if $1 > $2
  [ "$(printf '%s\n%s' "$1" "$2" | sort -V | tail -1)" = "$1" ] && [ "$1" != "$2" ]
}

max_version() {
  printf '%s\n' "$@" | sort -V | tail -1
}

list_plugins() {
  find "$REPO_ROOT/plugins" -maxdepth 1 -mindepth 1 -type d -exec basename {} \; | sort
}

plugin_json() {
  echo "$REPO_ROOT/plugins/$1/.claude-plugin/plugin.json"
}

# ── Commands ─────────────────────────────────────────────────────────────────

cmd_check() {
  local base_ref="${1:-origin/main}"
  local errors=0

  echo "Checking version bumps against $base_ref..."

  for plugin in $(list_plugins); do
    local pjson
    pjson="$(plugin_json "$plugin")"
    [ -f "$pjson" ] || continue

    # Check if any files in this plugin directory changed
    local changed
    changed=$(git diff --name-only "$base_ref" -- "plugins/$plugin/" 2>/dev/null || true)

    if [ -n "$changed" ]; then
      # Plugin has changes — check if version was bumped
      local old_version new_version
      old_version=$(git show "$base_ref:plugins/$plugin/.claude-plugin/plugin.json" 2>/dev/null | grep '"version"' | head -1 | sed 's/.*"version"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/' || echo "0.0.0")
      new_version=$(get_version "$pjson")

      if [ "$old_version" = "$new_version" ]; then
        echo "FAIL: plugin '$plugin' has changes but version is still $old_version"
        echo "  Changed files:"
        echo "$changed" | sed 's/^/    /'
        errors=$((errors + 1))
      else
        echo "OK: plugin '$plugin' bumped $old_version -> $new_version"
      fi
    else
      echo "SKIP: plugin '$plugin' has no changes"
    fi
  done

  # Check marketplace version is >= max plugin version
  local max_v mkt_v
  max_v="0.0.0"
  for plugin in $(list_plugins); do
    local pjson
    pjson="$(plugin_json "$plugin")"
    [ -f "$pjson" ] || continue
    local v
    v=$(get_version "$pjson")
    max_v=$(max_version "$max_v" "$v")
  done

  mkt_v=$(get_version "$MARKETPLACE_JSON")
  if version_gt "$max_v" "$mkt_v"; then
    echo "FAIL: marketplace version ($mkt_v) is behind max plugin version ($max_v)"
    errors=$((errors + 1))
  else
    echo "OK: marketplace version ($mkt_v) >= max plugin version ($max_v)"
  fi

  if [ "$errors" -gt 0 ]; then
    echo ""
    echo "Version check failed with $errors error(s)."
    echo "Run: ./scripts/version.sh bump patch [plugin-name]"
    exit 1
  fi

  echo ""
  echo "All version checks passed."
}

cmd_bump() {
  local bump_type="${1:-patch}"
  local target_plugin="${2:-}"

  for plugin in $(list_plugins); do
    if [ -n "$target_plugin" ] && [ "$plugin" != "$target_plugin" ]; then
      continue
    fi

    local pjson
    pjson="$(plugin_json "$plugin")"
    [ -f "$pjson" ] || continue

    local old_version new_version
    old_version=$(get_version "$pjson")
    new_version=$(bump_version "$old_version" "$bump_type")
    set_version "$pjson" "$new_version"
    echo "Bumped plugin '$plugin': $old_version -> $new_version"
  done

  # Sync marketplace
  cmd_sync
}

cmd_sync() {
  local max_v="0.0.0"
  for plugin in $(list_plugins); do
    local pjson
    pjson="$(plugin_json "$plugin")"
    [ -f "$pjson" ] || continue
    local v
    v=$(get_version "$pjson")
    max_v=$(max_version "$max_v" "$v")
  done

  local old_mkt
  old_mkt=$(get_version "$MARKETPLACE_JSON")
  set_version "$MARKETPLACE_JSON" "$max_v"
  echo "Synced marketplace version: $old_mkt -> $max_v"
}

# ── Main ─────────────────────────────────────────────────────────────────────

case "${1:-help}" in
  check) shift; cmd_check "$@" ;;
  bump)  shift; cmd_bump "$@" ;;
  sync)  shift; cmd_sync "$@" ;;
  *)
    echo "Usage: version.sh {check|bump|sync}"
    echo "  check [base-ref]        — verify changed plugins have version bumps"
    echo "  bump <patch|minor|major> [plugin] — bump version(s)"
    echo "  sync                    — sync marketplace version to max plugin version"
    exit 1
    ;;
esac
