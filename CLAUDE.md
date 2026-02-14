# Interflux

> See `AGENTS.md` for full development guide.

## Overview

Multi-agent document review engine — 7 agents, 2 commands, 1 skill, 1 MCP server. Companion plugin for Clavain. Provides scored triage, domain detection, content slicing, and knowledge injection.

## Quick Commands

```bash
# Test locally
claude --plugin-dir /root/projects/Interflux

# Validate structure
ls skills/*/SKILL.md | wc -l          # Should be 1
ls agents/review/*.md | wc -l         # Should be 7
ls commands/*.md | wc -l              # Should be 2
python3 -c "import json; json.load(open('.claude-plugin/plugin.json'))"  # Manifest check
```

## Design Decisions (Do Not Re-Ask)

- Namespace: `interflux:` (companion to Clavain)
- 7 core review agents (fd-architecture, fd-safety, fd-correctness, fd-quality, fd-user-product, fd-performance, fd-game-design) — each auto-detects language
- Phase tracking is the **caller's** responsibility — Interflux commands do not source lib-gates.sh
- Knowledge compounding writes to Interflux's `config/flux-drive/knowledge/` directory
- qmd MCP server provides semantic search for project documentation
