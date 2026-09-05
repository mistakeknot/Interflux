# Phase 2: Launch (Codex Dispatch)

**Condition**: Use this file when `DISPATCH_MODE = codex`. Review uses the Clavain CLI dispatcher; the resolved validation role may choose another backend to remain independent of the producer.
**Shared contracts**: See `phases/shared-contracts.md` for output format, completion signals, prompt trimming, and monitoring.

## Resolve paths (with guards)

```bash
DISPATCH=$(find ~/.claude/plugins/cache -path '*/clavain/*/scripts/dispatch.sh' 2>/dev/null | head -1)
[[ -z "$DISPATCH" ]] && DISPATCH=$(find ~/projects/Sylveste/os/Clavain -name dispatch.sh -path '*/scripts/*' 2>/dev/null | head -1)
[[ -z "$DISPATCH" ]] && { echo "FATAL: dispatch.sh not found"; exit 1; }

REVIEW_TEMPLATE="${CLAUDE_PLUGIN_ROOT}/skills/flux-engine/templates/role-review-agent.md"
[[ -f "$REVIEW_TEMPLATE" ]] || { echo "FATAL: role-review-agent.md template not found"; exit 1; }
```

If either path resolution fails, stop this review lane and report the configuration error. Do not select an unvalidated backend as a fallback.

Obtain `PRODUCER_IDENTITY` from the producing dispatch's resolved profile/result
packet and retain it in the compose plan. Do not infer it from `DISPATCH_MODE`, a
tier, or the current parent model. If provenance is missing, request it before
launching consequential review. The resolver rejects missing/unknown identities
and excludes the producing model from every candidate in the validation chain.

## Project Agent bootstrap (codex mode only)

Before dispatching Project Agents, check if they exist and are current:

```bash
FD_AGENTS=$(ls .claude/agents/fd-*.md 2>/dev/null)

if [[ -z "$FD_AGENTS" ]]; then
  BOOTSTRAP=true
else
  CURRENT_HASH=$(sha256sum CLAUDE.md AGENTS.md 2>/dev/null | sha256sum | cut -d' ' -f1)
  STORED_HASH=$(cat .claude/agents/.fd-agents-hash 2>/dev/null || echo "none")
  if [[ "$CURRENT_HASH" != "$STORED_HASH" ]]; then
    echo "Project Agents are stale (project docs changed) — regenerating"
    BOOTSTRAP=true
  else
    BOOTSTRAP=false
  fi
fi
```

When `BOOTSTRAP=true`, dispatch a **blocking** Codex agent to create Project Agents:

```bash
BOOTSTRAP_TEMPLATE=$(find ~/.claude/plugins/cache -path '*/clavain/*/skills/interserve-engine/templates/create-review-agent.md' 2>/dev/null | head -1)
[[ -z "$BOOTSTRAP_TEMPLATE" ]] && BOOTSTRAP_TEMPLATE=$(find ~/projects/Sylveste/os/Clavain -path '*/skills/interserve-engine/templates/create-review-agent.md' 2>/dev/null | head -1)
[[ -z "$BOOTSTRAP_TEMPLATE" ]] && { echo "WARNING: create-review-agent.md not found — skipping Project Agent bootstrap"; BOOTSTRAP=false; }
```

Dispatch **without `run_in_background`** so it blocks until complete. Use `--tier fast` (scoped generation task). Set `timeout: 300000` (5 minutes). If bootstrap fails or times out, skip Project Agents for this run — do NOT block the rest of the review.

## Create temp directory and task description files

```bash
FLUX_TMPDIR=$(mktemp -d /tmp/flux-drive-XXXXXX)
```

For each selected agent, write a task description file to `$FLUX_TMPDIR/{agent-name}.md`.

**IMPORTANT**: Each section header (`PROJECT:`, `AGENT_IDENTITY:`, etc.) must be on its own line with the colon at end-of-line. Content goes on subsequent lines. This matches dispatch.sh's `^[A-Z_]+:$` section parser.

```
PROJECT:
{project name} — review task (read-only)

AGENT_IDENTITY:
{paste the agent's full system prompt from the agent .md file}

REVIEW_PROMPT:
{the same prompt template from phases/launch.md, with trimmed document content, focus area, and output requirements}

AGENT_NAME:
{agent-name}

TIER:
{project|adaptive|cross-ai}
(Note: This TIER field is review-category metadata. The validation role handles model selection.)

OUTPUT_FILE:
{OUTPUT_DIR}/{agent-name}.md
```

Prompt trimming for `AGENT_IDENTITY` uses the shared contract in `phases/shared-contracts.md`.

## Dispatch all agents in parallel

Launch all Codex agents via parallel Bash calls in a single message:

```bash
: "${PRODUCER_IDENTITY:?Resolved producer identity is required for independent review}"
CLAVAIN_DISPATCH_PROFILE=clavain bash "$DISPATCH" \
  --template "$REVIEW_TEMPLATE" \
  --prompt-file "$FLUX_TMPDIR/{agent-name}.md" \
  -C "$PROJECT_ROOT" \
  -s read-only \
  -o "$OUTPUT_DIR/{agent-name}.md" \
  --role validation \
  --producer-identity "$PRODUCER_IDENTITY" \
  --phase=flux-review
```

This replaces the old fixed-tier review exception: a tier cannot prove model
independence. `config/routing.yaml` owns the validation profile and ordered
fallbacks. `--phase=flux-review` remains audit context. Scout/bootstrap and bulk
mirror economics are unchanged; this contract applies to acceptance review.

Notes:
- Set `run_in_background: true` and `timeout: 600000` on each Bash call
- Do NOT use `--inject-docs` — Codex reads CLAUDE.md natively via `-C`
- The reviewer returns the complete report in its final response; `-o` captures it outside the model sandbox. Never enable file-mutation tools merely to write the report. Codex uses `read-only`; Claude uses the dispatcher's restrictive reviewer tool policy; Kimi uses its no-tools profile and therefore requires the complete review material in the prompt.
- **Cross-AI (Oracle)**: Unchanged — already dispatched via Bash

Monitor using the shared monitoring contract. Codex timeout is 10 minutes.

## Error handling

After all background Bash calls complete, check for missing findings files. For any agent whose `{OUTPUT_DIR}/{agent-name}.md` does not exist:
1. Check the background Bash exit code — if non-zero, log the error
2. Read the dispatch failure class and recorded route decision. The dispatcher already owns bounded 429 retries and explicit-unavailability fallback.
3. Never replay policy/configuration denials or independently substitute Task/another model. Preserve the missing review as an unresolved gate.
4. Report the failure and evidence to the main integrator for explicit disposition. A missing findings file is not a clean review.

## Cleanup

After Phase 3 synthesis completes, remove the temp directory:
```bash
rm -rf "$FLUX_TMPDIR"
```
