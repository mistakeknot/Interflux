# Shared Contracts (referenced by launch.md and launch-codex.md)

## Output Format: Findings Index

All agents (Task-dispatched or Codex-dispatched) produce the same output format:

### Agent Output File Structure

Each agent writes to `{OUTPUT_DIR}/{agent-name}.md` with this structure:

1. **Findings Index** (first block — machine-parsed by synthesis):
   ```
   ### Findings Index
   - SEVERITY | ID | "Section Name" | Title
   Verdict: safe|needs-changes|risky
   ```

2. **Prose sections** (after Findings Index):
   - Summary (3-5 lines)
   - Issues Found (numbered, with severity and evidence)
   - Improvements (numbered, with rationale)

3. **Zero-findings case**: Empty Findings Index with just header + Verdict line.

## Completion Signal

- Agents write to `{OUTPUT_DIR}/{agent-name}.md.partial` during work
- Add `<!-- flux-drive:complete -->` as the last line
- Rename `.md.partial` to `.md` as the final action
- Orchestrator detects completion by checking for `.md` files (not `.partial`)

## Error Stub Format

When an agent fails after retry:
```
### Findings Index
Verdict: error

Agent failed to produce findings after retry. Error: {error message}
```

## Prompt Trimming Rules

Before including an agent's system prompt in the task prompt, strip:
1. All `<example>...</example>` blocks (including nested `<commentary>`)
2. Output Format sections (titled "Output Format", "Output", "Response Format")
3. Style/personality sections (tone, humor, directness)

Keep: role definition, review approach/checklist, pattern libraries, language-specific checks.

**Scope**: Trimming applies to Project Agents (manual paste) and Codex AGENT_IDENTITY sections. Plugin Agents load system prompts via `subagent_type` — the orchestrator cannot strip those.

## Content Slicing Contracts

See `phases/slicing.md` for complete diff and document slicing contracts, including:
- Routing patterns (which file/section patterns map to which agents)
- Agent content access rules (which agents get full vs sliced content)
- Slicing metadata format (slicing_map, section_map)
- Synthesis rules (convergence adjustment, out-of-scope findings, no penalty for silence)

## Monitoring Contract

After dispatching agents, poll for completion:
- Check `{OUTPUT_DIR}/` for `.md` files every 30 seconds
- Report each completion with elapsed time
- Report running count: `[N/M agents complete]`
- Timeout: 5 minutes (Task), 10 minutes (Codex)
- After timeout, report pending agents
