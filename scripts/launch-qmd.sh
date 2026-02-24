#!/usr/bin/env bash
# Launcher for qmd MCP server: checks if qmd is installed before starting.
# On a new machine, qmd may not be available — emit a helpful error instead
# of letting Claude Code fail silently.
set -euo pipefail

if ! command -v qmd &>/dev/null; then
    echo "qmd not found — install with: bun install -g qmd" >&2
    echo "interflux will work without qmd but semantic doc search will be unavailable." >&2
    # Exit cleanly so Claude Code doesn't retry in a loop
    exit 0
fi

exec qmd "$@"
