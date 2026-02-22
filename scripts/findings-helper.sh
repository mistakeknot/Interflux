#!/usr/bin/env bash
# findings-helper.sh — read/write helpers for flux-drive intermediate findings
# Usage:
#   findings-helper.sh write <findings_file> <severity> <agent> <category> <summary> [file_refs...]
#   findings-helper.sh read <findings_file> [--severity blocking|notable|all]
set -euo pipefail

cmd="${1:-}"
shift || true

case "$cmd" in
  write)
    findings_file="$1"; shift
    severity="$1"; shift
    agent="$1"; shift
    category="$1"; shift
    summary="$1"; shift
    # Remaining args are file_refs
    refs="[]"
    if [[ $# -gt 0 ]]; then
      refs=$(printf '%s\n' "$@" | jq -R . | jq -s .)
    fi
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    # Build JSON line in memory, then write as single atomic append (< PIPE_BUF)
    line=$(jq -n -c \
      --arg sev "$severity" \
      --arg agt "$agent" \
      --arg cat "$category" \
      --arg sum "$summary" \
      --arg ts "$timestamp" \
      --argjson refs "$refs" \
      '{severity:$sev, agent:$agt, category:$cat, summary:$sum, file_refs:$refs, timestamp:$ts}')
    echo "$line" >> "$findings_file"
    ;;
  read)
    findings_file="$1"; shift
    filter="${1:-all}"
    if [[ ! -f "$findings_file" ]]; then
      echo "[]"
      exit 0
    fi
    # Safe read: filter out incomplete trailing lines before parsing
    safe_content=$(grep -a '^{' "$findings_file" || true)
    if [[ -z "$safe_content" ]]; then
      echo "[]"
      exit 0
    fi
    case "$filter" in
      blocking) echo "$safe_content" | jq -s '[.[] | select(.severity == "blocking")]' ;;
      notable)  echo "$safe_content" | jq -s '[.[] | select(.severity == "notable")]' ;;
      all)      echo "$safe_content" | jq -s '.' ;;
      *)        echo "$safe_content" | jq -s '.' ;;
    esac
    ;;
  *)
    echo "Usage: findings-helper.sh {write|read} <findings_file> ..." >&2
    exit 1
    ;;
esac
