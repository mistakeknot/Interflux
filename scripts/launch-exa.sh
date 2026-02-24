#!/usr/bin/env bash
# Launcher for exa-mcp-server: checks prerequisites before starting.
# Needs npx (Node.js) and EXA_API_KEY to function.
set -euo pipefail

if ! command -v npx &>/dev/null; then
    echo "npx not found — install Node.js to use the Exa search MCP server." >&2
    echo "interflux will work without Exa but web search will be unavailable." >&2
    exit 0
fi

if [[ -z "${EXA_API_KEY:-}" ]]; then
    echo "EXA_API_KEY not set — Exa search MCP server disabled." >&2
    echo "Set EXA_API_KEY in your environment to enable web search in research agents." >&2
    exit 0
fi

exec npx -y exa-mcp-server "$@"
