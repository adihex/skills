#!/usr/bin/env bash
# audit-dev-logs.sh — list every `// dev-log` line under a path.
#
# Usage:
#   audit-dev-logs.sh <path> [<path> ...]
#
# Default path is the current directory. Run before committing — for each
# match, decide: keep & untag (remove `// dev-log`), delete the line, or
# downgrade level (info -> debug).

set -euo pipefail

PATHS=("$@")
if [[ ${#PATHS[@]} -eq 0 ]]; then
  PATHS=(".")
fi

for path in "${PATHS[@]}"; do
  if [[ ! -e "$path" ]]; then
    echo "audit-dev-logs: path does not exist: $path" >&2
    exit 2
  fi
  if [[ ! -r "$path" ]]; then
    echo "audit-dev-logs: path is not readable: $path" >&2
    exit 2
  fi
done

PATTERN='// dev-log'
GLOBS=(--glob '*.ts' --glob '*.tsx' --glob '!**/node_modules/**' --glob '!**/dist/**' --glob '!**/build/**')

if command -v rg >/dev/null 2>&1; then
  set +e
  rg --line-number --color=always "${GLOBS[@]}" -- "$PATTERN" "${PATHS[@]}"
  status=$?
  set -e
  case "$status" in
    0) ;;
    1)
      echo "No dev-log markers found in: ${PATHS[*]}"
      exit 0
      ;;
    *)
      echo "audit-dev-logs: rg failed with exit $status for: ${PATHS[*]}" >&2
      exit "$status"
      ;;
  esac
else
  EXCLUDES=(
    --exclude-dir=node_modules
    --exclude-dir=dist
    --exclude-dir=build
    --include='*.ts'
    --include='*.tsx'
  )
  set +e
  grep -rn "${EXCLUDES[@]}" -- "$PATTERN" "${PATHS[@]}"
  status=$?
  set -e
  case "$status" in
    0) ;;
    1)
      echo "No dev-log markers found in: ${PATHS[*]}"
      exit 0
      ;;
    *)
      echo "audit-dev-logs: grep failed with exit $status for: ${PATHS[*]}" >&2
      exit "$status"
      ;;
  esac
fi

echo
echo "Action checklist for each match above:"
echo "  keep    -> remove the '// dev-log' suffix (log survives in production)"
echo "  delete  -> remove the entire line (scaffolding only)"
echo "  downgrade -> change level (e.g. info -> debug) and untag"
echo
echo "Re-run this script until nothing remains in your staged hunks."
