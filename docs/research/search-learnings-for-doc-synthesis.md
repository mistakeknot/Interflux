# Institutional Learnings Search: Doc Synthesis & Token Reduction Pipeline

**Date:** 2026-02-27
**Search Context:** Planning a document synthesis and token reduction pipeline for Demarch monorepo
**Feature Scope:** Synthesize accumulated compound/reflect/research docs into categorized docs/solutions/ entries, create missing SKILL-compact.md files, archive processed originals, wire together intersynth/interknow/interlearn/interwatch/intersearch/tldr-swinton

---

## Search Strategy & Results

### Search Scope
- Files scanned: All of `/home/mk/projects/Demarch/interverse` (17 distinct `docs/solutions/` files across 6 plugins)
- Keywords: synth, token, compact, knowledge, lifecycle, archive, synthesis, frontmatter, YAML, compact-skill
- Specific modules searched: intersynth, interknow, interlearn, interwatch, intersearch, tldr-swinton

### Files Found & Analyzed
- **17 total** solutions/patterns files across interverse plugins
- **3 directly relevant** to this feature:
  1. ProjectIndex deduplication (tldr-swinton) — shared state threading pattern
  2. Awk YAML frontmatter parsing (interlearn) — frontmatter extraction gotcha
  3. Codex dispatch background mode (tldr-swinton) — integration lesson
- **4 critical CLAUDE.md/AGENTS.md files** read for ecosystem context:
  - intersynth: verdict library, multi-agent synthesis pattern
  - interknow: knowledge compounding with provenance, decay, archival
  - interlearn: shell-based institutional knowledge indexing
  - interwatch: doc freshness monitoring via signal-based scoring

---

## Critical Learnings for Your Feature

### 1. **Shared State Threading Pattern** (ProjectIndex Deduplication)

**File:** `/home/mk/projects/Demarch/interverse/tldr-swinton/docs/solutions/performance-issues/duplicated-index-builds-projectindex-20260211.md`

**The Problem:**
Every CLI command that calls multiple downstream functions rebuilds expensive shared state (like `ProjectIndex`) 2-4x per command. Each function was self-contained and unaware that other functions in the same orchestration would need the same data.

**The Solution Pattern — Underscore Prefix for Threading:**
```python
# Before: each function builds independently
def map_hunks_to_symbols(project, hunks, language="python"):
    idx = ProjectIndex.build(...)
    ...

# After: accept pre-built state, build only as fallback
def map_hunks_to_symbols(project, hunks, language="python", _project_index=None):
    idx = _project_index or ProjectIndex.build(...)  # Backward compatible
    ...

# At orchestration level (CLI):
_project_index = ProjectIndex.build(project, language, include_sources=True, ...)
signatures = get_diff_signatures(..., _project_index=_project_index)
full_pack = get_diff_context(..., _project_index=_project_index)
```

**Why This Matters for Your Pipeline:**
- Your feature synthesizes docs across multiple modules (intersynth, interknow, interlearn, intersearch)
- Each module likely builds its own indexes/caches independently
- **Apply the underscore-prefix pattern:** Build a unified `_synthesis_index` or `_doc_cache` at orchestration level, thread it through all downstream synthesis calls
- This prevents re-scanning the same files or rebuilding the same YAML/frontmatter parsers for each synthesis agent

**Key Pattern:** "Build once at orchestration level with superset flags, thread through all downstream calls"

---

### 2. **YAML Frontmatter Parsing Gotcha** (Awk Pattern Matching)

**File:** `/home/mk/projects/Demarch/interverse/interlearn/docs/solutions/patterns/awk-sub-pattern-fallthrough-20260221.md`

**The Problem:**
When parsing multi-line YAML in shell scripts (e.g., extracting `tags:` array), the awk script only returned the *first* tag instead of all tags. Root cause: `sub()` mutations in one pattern rule cause subsequent rules to evaluate against the modified `$0`, triggering unwanted early exit.

**The Gotcha:**
```awk
# BROKEN: Rule 1 modifies $0, causing Rule 2 to fire on same line
found && /^  - / { sub(/^  - */, ""); items = items "," $0 }     # sub() changes $0
found && !/^  - / { exit }  # Now checks modified $0 → exits!

# FIXED: Add 'next' to skip remaining rules
found && /^  - / { sub(/^  - */, ""); items = items "," $0; next }  # ← CRITICAL
found && !/^  - / { exit }
```

**Why This Matters for Your Pipeline:**
- Your feature processes YAML frontmatter extensively (title, tags, module, root_cause, component, etc.)
- **Prevention rule:** Whenever parsing multi-line YAML with awk, ALWAYS use `next` after rules that modify `$0`
- Test with multi-element inputs (0, 1, 3+ tags), not just single cases — single-tag inputs pass silently because awk reaches EOF
- See interlearn's `index-solutions.sh` (line 119) as reference implementation

**Key Pattern:** "Always `next` after `sub()`/`gsub()` in awk when subsequent rules check `$0` patterns"

---

### 3. **Multi-Agent Synthesis & Verdict Library** (Intersynth)

**File:** `/home/mk/projects/Demarch/interverse/intersynth/CLAUDE.md`

**The Pattern:**
Instead of the host agent reading N agent output files directly (flooding context), use a **synthesis subagent** that:
1. Collects findings from parallel agents (via verdict library)
2. Deduplicates and structures findings
3. Returns compact verdict (~10 lines) to host
4. Writes full report to `synthesis.md` for user

**Key Components:**
```bash
# Verdict library functions (from hooks/lib-verdict.sh):
verdict_init                              # Initialize verdict file
verdict_write "agent-name" verdict "CLEAN" "haiku" "message"
verdict_read                              # Parse verdict back
verdict_count_by_status                   # Roll up findings
verdict_parse_all                         # Aggregate across agents
verdict_total_tokens                      # Cost tracking
```

**Usage Pattern for Your Feature:**
```
Task(intersynth:synthesize-research):
  OUTPUT_DIR={synthesis_output_dir}
  VERDICT_LIB={path to lib-verdict.sh}
  MODE=knowledge-compounding
  CONTEXT="Synthesizing 12 accumulated research docs into 3 docs/solutions/ categories"
  → Returns: "PASS: 3 docs categorized, 2 archived" (~5 lines)
  → Writes: {OUTPUT_DIR}/synthesis.md (full dedup report)
  → Writes: .clavain/verdicts/{agent}.json (structured verdicts)
```

**Why This Matters:**
- Your feature coordinates multiple synthesis agents (one per docs/solutions/ category)
- Use the verdict library pattern to keep your orchestrator's context small
- Designate one synthesis agent per category, collect via verdicts, roll up costs

---

### 4. **Knowledge Compounding with Provenance & Decay** (Interknow)

**File:** `/home/mk/projects/Demarch/interverse/interknow/CLAUDE.md`

**The Pattern:**
Durable pattern repository with:
- **Provenance tracking:** `independent` vs `primed` prevents false-positive feedback loops
- **Temporal decay:** 10 reviews without independent confirmation → archive
- **Semantic search:** qmd MCP for querying across entries
- **Categorization:** domain tags for filtering

**Key Files:**
- `config/knowledge/*.md` — Knowledge entries (markdown with YAML frontmatter)
- `config/knowledge/README.md` — Format spec, provenance rules, decay rules
- `config/knowledge/archive/` — Aged-out entries (auto-archived)

**Application to Your Feature:**
When you synthesize docs/solutions/ entries and create SKILL-compact.md files:
1. Add provenance field tracking: "synthesized from 5 compound docs on 2026-02-27"
2. Track review count per entry (reuse interknow's decay mechanism)
3. Archive solutions that haven't been referenced in 60+ days (adjust decay window)
4. Use semantic search to detect duplicate synthesized entries

**Key Pattern:** "Provenance tracking prevents false learning; decay + archival prevent stale docs from bloating search results"

---

### 5. **Document Lifecycle Monitoring** (Interwatch)

**File:** `/home/mk/projects/Demarch/interverse/interwatch/CLAUDE.md`

**The Pattern:**
Signal-based scoring to detect drift between project state and documentation:
- Confidence tiers: Certain (auto-fix) → High (auto-fix+note) → Medium (suggest) → Low (report)
- Watchables registry in YAML (declarative, not hardcoded)
- State tracked in `.interwatch/` (per-project, gitignored)

**Application to Your Feature:**
Monitor these signals post-synthesis:
1. **Orphaned research docs:** Files in `docs/research/` older than 7 days without corresponding `docs/solutions/` entry
2. **Stale SKILL-compact.md:** Detect when SKILL.md changes but SKILL-compact.md not updated (use file mod times)
3. **Missing category directories:** Verify `docs/solutions/{category}/` exists for all frontmatter categories found
4. **Frontmatter drift:** Detect mismatches between extracted tags and actual file content (e.g., `tags: [auth]` but file mentions `database`)

**Key Pattern:** "Use signal-based scoring, not hardcoded heuristics, for drift detection"

---

### 6. **SKILL-Compact Generation Pattern** (Flux-Drive Reference)

**File:** `/home/mk/projects/Demarch/interverse/interflux/skills/flux-drive/SKILL-compact.md`

**The Pattern:**
Single-file compact version of a multi-file SKILL documentation that:
- Preserves all algorithm steps, formulas, scoring logic in condensed form
- Contains comment pointing to full docs for detailed reference
- Loads INSTEAD OF multi-file structure when present

**Example Structure:**
```markdown
# Flux Drive — Compact Review & Research Instructions

Multi-agent document/codebase review and research. Follow phases in order.

## Mode
- Invoked via `/interflux:flux-drive` → `MODE = review`
...

## Phase 1: Analyze + Triage
### Step 1.0: Project Understanding
### Step 1.0.1: Domain Detection
...

<!-- Reference: See phases/launch.md for synthesis details, phases/synthesize.md for dedup rules -->
```

**Files to Create:**
For each skill with SKILL.md:
1. Read full SKILL.md (~500+ lines)
2. Extract core algorithm, scoring, dispatch logic
3. Compress to ~250-350 lines in SKILL-compact.md
4. Add forward references: `<!-- See {path} for detailed {section} -->`
5. Test: Verify parser/launcher can follow references to SKILL.md without loading multi-file structure

**Key Pattern:** "Comment-only indirection for multi-file reference; compact version is the PRIMARY entry point"

---

## Architectural Patterns to Apply

### A. **Build-Once-at-Orchestration Pattern**
```
CLI entry point
  ↓ (Build comprehensive indices/caches)
  ↓ _doc_index = load all docs/solutions/ + research/
  ↓ _yaml_cache = parse all frontmatter (thread via param)
  ↓
  ├→ synthesis_agent_1(..., _doc_index, _yaml_cache)
  ├→ synthesis_agent_2(..., _doc_index, _yaml_cache)
  └→ synthesis_agent_3(..., _doc_index, _yaml_cache)
```

### B. **Verdict Library Orchestration**
```
For each synthesis agent:
  1. Dispatch via intersynth:synthesize-*
  2. Agent writes findings to OUTPUT_DIR/{agent}.md
  3. Host collects via verdict_parse_all()
  4. Roll up results, call synthesis.md
```

### C. **Archive-with-Provenance**
```
Processed doc:
  1. Add "synthesized_from: [list of source files]" to YAML
  2. Add "archived_date: YYYY-MM-DD" to YAML
  3. Move to docs/solutions/archive/{category}/{basename}
  4. Keep reference marker in original location (symlink or stub)
```

### D. **Multi-Line YAML Safe Parsing**
```bash
# Extract complex YAML fields (handle arrays/nested structures)
extract_yaml_array() {
  local field="$1" file="$2"
  awk -v field="$field:" '
    found && /^[^ ]/ { exit }           # Stop at next field
    $0 ~ field { found=1; next }        # Start collecting after field
    found && /^  - / {
      sub(/^  - */, "");
      gsub(/"/, "");
      items = items ? items "," $0 : $0
      next  # ← CRITICAL: skip remaining rules
    }
    found && !/^  - / { exit }          # Stop at non-array line
    END { print items }
  ' "$file"
}
```

---

## Token Optimization Considerations

### From Synthesis Spec:
**Two-tier collection strategy (from flux-drive-spec):**
```
Tier 1 — Structured Index (fast):
  Read Findings Index from outputs (~30 lines)
  Parse into metadata only

Tier 2 — Prose Fallback (lazy):
  Read full body only when:
  - User requests details
  - Agents conflict
  - Output was malformed
```

**Applies to Your Feature:**
- Extract frontmatter + summary from each docs/solutions/ entry (~50 lines)
- Load full prose only during deduplication pass
- Use content hash to detect duplicates without re-reading

### Compact File Strategy:
- SKILL-compact.md: ~250-350 lines vs SKILL.md multi-file (1000+ lines)
- **Token savings:** ~60-70% reduction while keeping algorithm complete
- Forward references via comments, no embedding

---

## Gotchas to Avoid

### 1. **Frontmatter Parsing in Loops**
If you iterate over files parsing frontmatter:
- **Wrong:** Extract tags in loop, one at a time → N passes over YAML
- **Right:** Extract all tags in single awk/yq pass → 1 pass, cache result via `_yaml_cache`

### 2. **Missing Archive Stubs**
After archiving processed docs:
- Don't leave dangling references in docs/solutions/
- Either delete original, or create minimal stub file with redirect comment

### 3. **Category Mismatch**
YAML `category: performance` but file lives in `docs/solutions/ui-bugs/`:
- Violates interwatch signal: "category mismatch"
- Always validate frontmatter matches directory structure
- Use `categorize_by_frontmatter()` not directory name

### 4. **Duplicate Synthesis Entries**
Two separate synthesis agents create docs/solutions entries on same topic:
- Apply intersynth dedup Rule 1: "Same topic → Merge, credit all agents"
- Use fuzzy title matching (Levenshtein < 0.3, or 3+ shared keywords)

### 5. **SKILL-Compact Staleness**
SKILL.md updated but SKILL-compact.md not regenerated:
- Interwatch signal: file mod time mismatch
- Add pre-commit hook: `if SKILL.md modified, require SKILL-compact.md update`
- Or: auto-regenerate SKILL-compact.md from SKILL.md template

---

## Reference Files from Ecosystem

### Synthesis & Multi-Agent Orchestration
- `interflux/docs/spec/core/synthesis.md` — 5 dedup rules, convergence tracking, structured verdicts
- `intersynth/hooks/lib-verdict.sh` — verdict library functions
- `intersynth/CLAUDE.md` — synthesis agent pattern

### Knowledge & Archival
- `interknow/config/knowledge/README.md` — provenance format, decay rules
- `interknow/CLAUDE.md` — temporal decay (10 reviews), archival workflow
- `interknow/config/knowledge/archive/` — example archived entries

### Document Indexing & Parsing
- `interlearn/scripts/index-solutions.sh` — YAML frontmatter extraction (reference implementation)
- `interlearn/docs/solutions/patterns/awk-sub-pattern-fallthrough-20260221.md` — awk gotcha + fix

### Token Reduction & Compaction
- `interflux/skills/flux-drive/SKILL-compact.md` — compact skill pattern (250-350 lines)
- `flux-drive-spec/core/synthesis.md` — two-tier collection (structured index vs prose)

### Drift Detection
- `interwatch/CLAUDE.md` — signal-based scoring for doc freshness
- `tool-time/` — tool usage analytics (meta: shows which docs are actually used)

---

## Recommendations for Your Plan

### Before Starting:
1. **Read intersynth's verdict library** — you'll use this for synthesis orchestration
2. **Review the awk gotcha** — critical for safe YAML parsing at scale
3. **Plan shared index threading** — design your `_synthesis_index` parameter early

### Phase 1 — Harvest:
- Scan `docs/research/` for accumulated compound docs (use interwatch signal-based scoring)
- Extract frontmatter (apply safe awk pattern from interlearn)
- Cache YAML parsed results in `_yaml_cache` (build once at CLI level)

### Phase 2 — Synthesize:
- Dispatch to `intersynth:synthesize-research` (one per category)
- Collect verdicts via lib-verdict.sh
- Deduplicate using flux-drive 5-rule algorithm (same file:line + same issue → merge, etc.)

### Phase 3 — Archive:
- Add `archived_from: [list of sources]` to each docs/solutions/ entry
- Move originals to `docs/research/archive/{category}/{date}/{basename}`
- Create symlinks or stub files if needed

### Phase 4 — Compact:
- For each SKILL with >500 lines, generate SKILL-compact.md (40-50% reduction)
- Extract core algorithm, scoring, dispatch logic
- Add comment-only forward references to detailed sections

### Phase 5 — Monitor:
- Configure interwatch watchables to detect:
  - Orphaned research docs (>7 days without synthesis)
  - SKILL.md / SKILL-compact.md staleness
  - Frontmatter/directory mismatches

---

## Files to Keep & Refer Back To

**Critical Learning Sources:**
- `/home/mk/projects/Demarch/interverse/tldr-swinton/docs/solutions/performance-issues/duplicated-index-builds-projectindex-20260211.md` — shared state pattern
- `/home/mk/projects/Demarch/interverse/interlearn/docs/solutions/patterns/awk-sub-pattern-fallthrough-20260221.md` — YAML parsing gotcha
- `/home/mk/projects/Demarch/interverse/interflux/docs/spec/core/synthesis.md` — 5-rule dedup algorithm
- `/home/mk/projects/Demarch/interverse/intersynth/CLAUDE.md` — verdict library pattern
- `/home/mk/projects/Demarch/interverse/interknow/CLAUDE.md` — provenance + decay + archival
- `/home/mk/projects/Demarch/interverse/interlearn/scripts/index-solutions.sh` — reference YAML parser

**Compact File Examples:**
- `/home/mk/projects/Demarch/interverse/interflux/skills/flux-drive/SKILL-compact.md` — reference implementation

---

**End of Research Document** | Compiled 2026-02-27
