# Exploration: interlearn and interwatch

## Overview

This document provides a thorough analysis of two companion plugins in the Interverse ecosystem that manage discovery and freshness of project documentation:

1. **interlearn** — Cross-repo institutional knowledge index (discovery layer)
2. **interwatch** — Documentation freshness monitoring (freshness layer)

These are essential for the synthesis pipeline because interlearn surfaces what documentation exists across the monorepo, while interwatch determines which docs are stale and need regeneration before synthesis begins.

---

## PART 1: INTERLEARN — Discovery & Indexing Layer

### Architecture Overview

**interlearn** is a shell-only Claude Code plugin with minimal complexity: one bash script, one skill with 3 modes, and one SessionEnd hook. It has no MCP server, no Python runtime, and no compiled binary.

**Core purpose:** Build a cross-repo index of solution documentation in `docs/solutions/` across the Interverse monorepo, enabling unified search and audit of documentation coverage against closed beads.

### Components

```
interlearn/
├── .claude-plugin/
│   └── plugin.json                  # Manifest (v0.1.0)
├── scripts/
│   └── index-solutions.sh           # Deterministic indexer (219 lines)
├── skills/
│   └── interlearn/
│       └── SKILL.md                 # 3 sub-skills: index, search, audit
├── hooks/
│   ├── hooks.json                   # SessionEnd registration
│   └── session-end.sh               # Background index refresh trigger
└── AGENTS.md                        # Development guide
```

### 1. INDEX BUILDING: scripts/index-solutions.sh

**What it does:**
- Scans `docs/solutions/*.md` across the Interverse monorepo (starting from argument `$1`)
- Parses YAML frontmatter from each file with schema tolerance
- Extracts module identity from filesystem path (not frontmatter)
- Generates two outputs:
  - `docs/solutions/INDEX.md` — human-readable markdown table
  - `docs/solutions/index.json` — machine-readable index keyed by file path

**Key algorithm:**

1. **File discovery:** `find "$ROOT" -path "*/docs/solutions/*.md"` with exclusions
2. **Exclusion rules:**
   - Exact blacklist: `INDEX.md`, `README.md`, `TEMPLATE.md`
   - Suffix blacklist: `.tmp`, `.bak`
   - All-caps filename heuristic (e.g., `README`, `LICENSE`)
3. **Frontmatter parsing:** Per-file extraction with schema heterogeneity handling
4. **Module identity:** Derived from path, not frontmatter
   - Paths like `interverse/interflux/docs/solutions/foo.md` → module `interflux`
   - Fallback to `interverse` if module can't be determined
5. **Metadata normalization:**
   - `title` — frontmatter title → first `#` heading → filename fallback
   - `date` — tries `date_resolved`, `created`, `date` in order
   - `problem_type` — tries `problem_type`, then `category`; adds fallback from directory name
   - `severity` — direct field if present
   - `tags` — supports inline YAML array and indented list format
6. **JSON output:** Per-doc JSONL emission, then sorted aggregate with metadata
7. **Grouping:** `by_module` map in final JSON with timestamp metadata

**Output structure (index.json):**
```json
{
  "generated": "2026-02-27T15:30:00Z",
  "total_count": 42,
  "by_module": {
    "interflux": [
      {
        "path": "interverse/interflux/docs/solutions/foo.md",
        "module": "interflux",
        "title": "Solving X Problem",
        "date": "2026-02-20",
        "problem_type": "architecture",
        "severity": "high",
        "tags": ["cache", "async"]
      }
    ]
  }
}
```

**Output structure (INDEX.md):**
```markdown
# Solutions Index

Generated: 2026-02-27T15:30:00Z
Total documents: 42

## interflux (12 docs)

| Document | Type | Severity | Date | Tags |
|----------|------|----------|------|------|
| Solving X Problem | architecture | high | 2026-02-20 | cache, async |
```

### 2. SESSIONEND HOOK: hooks/session-end.sh

**Registration:** `hooks/hooks.json` registers this as a SessionEnd handler with 10-second timeout.

**What it does:**
- Fires automatically when a Claude Code session ends
- Detects if the session was inside the Interverse monorepo
- Triggers background index rebuild (fire-and-forget)
- Fail-open: indexing errors never block session teardown

**Execution flow:**

1. **Defensive setup:** `set -u` + `trap 'exit 0' ERR` — all errors silently return 0
2. **Runtime gate:** Checks `command -v jq` — exits early if jq unavailable
3. **Input parsing:** `CWD=$(echo "$INPUT" | jq -r '.cwd // empty')` — extracts cwd from JSON stdin
4. **Monorepo detection:** `find_interverse_root()` function
   - Fast-path check: `/root/projects/Interverse` (known location)
   - Fallback: Walk parent directories looking for `.beads/`, `plugins/`, `hub/` markers
   - Returns empty string if not found (hook exits silently)
5. **Script path resolution:** `SCRIPT_DIR` + `INDEXER="$SCRIPT_DIR/scripts/index-solutions.sh"`
6. **Executable check:** `[ -x "$INDEXER" ] || exit 0` — ensures indexer exists
7. **Background invocation:** `bash "$INDEXER" "$INTERVERSE_ROOT" </dev/null >/dev/null 2>&1 &`
   - Redirects all I/O to `/dev/null`
   - Runs detached (ampersand background)
   - No wait or status checking

**Key design principle:** Fail-open. The hook never blocks session teardown, never logs errors, never exits non-zero.

### 3. SKILL: skills/interlearn/SKILL.md

**Three sub-skills** accessible via `/interlearn:<mode>`:

#### `/interlearn:index` — Rebuild cross-repo index

1. Run indexer: `bash /root/projects/Interverse/plugins/interlearn/scripts/index-solutions.sh /root/projects/Interverse`
2. Read `docs/solutions/index.json`
3. Report:
   - Total document count
   - Per-module breakdown
   - Documents with missing frontmatter fields
   - Top 5 modules by count
4. List any docs with missing fields (so developer can fix)

#### `/interlearn:search <query>` — Search solution docs

**Two-phase search:**

**Phase 1 — Structured (via index.json):**
- Read `docs/solutions/index.json`
- Search across `title`, `tags`, `problem_type`, `module`, `path` fields
- Ranking: exact tag match > title match > path match
- Return up to 5 matches from Phase 1

**Phase 2 — Full-text fallback (if Phase 1 < 5 matches):**
- Grep across all `*/docs/solutions/*.md`
- Exclude meta-docs: `INDEX.md`, `README.md`, `TEMPLATE.md`, all-caps filenames

**Presentation:**
- Show up to 10 matches, sorted by relevance
- For each: module, title, date, severity, tags, file path
- Read top 3 matches and provide 2-3 sentence summary of key insight from each
- Format like `learnings-researcher` agent: concise, actionable

#### `/interlearn:audit` — Reflect coverage audit

Audit whether closed beads have corresponding solution documentation:

1. Get closed beads: `cd /root/projects/Interverse && bd list --status=closed`
2. For each closed bead, check two sources:
   - Sprint artifact: `bd state "<bead-id>" sprint_artifacts` — look for `reflect` key
   - Solution doc: grep `index.json` for bead ID (some docs have `bead:` in frontmatter)
3. Report:
   - Total closed beads
   - Count with reflect artifacts
   - Count with solution docs mentioning their bead ID
   - Coverage ratio (at least one of above / total)
   - List of beads with NO reflect and NO solution doc (knowledge gaps)
4. Suggest which beads would benefit most from solution doc based on title/description

### 4. Key Design Decisions (Do Not Re-Ask)

1. **Shell-only implementation** — No MCP server, daemon, or compiled binary for this phase
2. **Path is canonical module identity** — Frontmatter `module:` is too inconsistent; derive from filesystem
3. **Schema-tolerant parsing** — Handles `problem_type` vs `category`, multiple date keys
4. **Fail-open hook behavior** — Session teardown never fails because indexing failed
5. **No auto-commit** — Writes artifacts but humans decide when to commit
6. **Monorepo detection** — 3-marker heuristic: `.beads/` + `plugins/` + `hub/`
7. **Interverse root hardcoded** — `/root/projects/Interverse` for operational reliability in current environment

---

## PART 2: INTERWATCH — Freshness & Drift Detection Layer

### Architecture Overview

**interwatch** is a doc freshness monitoring system that abstracts the pattern: "has something changed in the project that makes this document outdated?"

**Core purpose:** Detect drift in watched documents (roadmap, PRD, AGENTS.md, etc.), score confidence on whether refresh is needed, and dispatch to generator plugins (interpath or interdoc) for regeneration.

### Components

```
interwatch/
├── .claude-plugin/
│   └── plugin.json                  # Manifest (v0.1.7)
├── skills/
│   └── doc-watch/
│       ├── SKILL.md                 # Orchestrator
│       ├── SKILL-compact.md         # Single-file algorithm (if exists)
│       ├── phases/
│       │   ├── detect.md            # Signal evaluation
│       │   ├── assess.md            # Confidence scoring
│       │   └── refresh.md           # Generator dispatch
│       └── references/
│           ├── watchables.md        # Watchable registry format
│           ├── signals.md           # Signal catalog
│           └── confidence-tiers.md  # Confidence tier definitions
├── config/
│   └── watchables.yaml              # Default watched documents registry
├── commands/
│   ├── watch.md                     # Run drift scan
│   ├── status.md                    # Show current drift scores
│   └── refresh.md                   # Force refresh a specific doc
├── hooks/
│   └── lib-watch.sh                 # Bash utility library (not a hook)
└── AGENTS.md                        # Development guide
```

### 1. WATCHABLES: Declaration & Discovery

**What is a watchable?**

A document that can be monitored for drift. Declared in `config/watchables.yaml` with:
- `name` — unique identifier (e.g., `roadmap`)
- `path` — relative path to document (e.g., `docs/roadmap.md`)
- `generator` — skill to invoke for regeneration (e.g., `interpath:artifact-gen`)
- `generator_args` — arguments passed to generator
- `signals` — list of drift signals to monitor (see below)
- `staleness_days` — days before doc is considered stale

**Example from config/watchables.yaml:**
```yaml
watchables:
  - name: roadmap
    path: docs/roadmap.md
    generator: interpath:artifact-gen
    generator_args: { type: roadmap }
    signals:
      - type: bead_closed
        weight: 2
        description: "Closed bead may affect roadmap phasing"
      - type: version_bump
        weight: 3
        description: "Version bump likely means shipped work"
    staleness_days: 7
```

**Discovery process:**

1. Load defaults: `config/watchables.yaml` from plugin directory
2. Load project overrides: `.interwatch/watchables.yaml` from project root
3. Merge: Project overrides win for same-named watchables
4. Filter: Skip watchables whose path doesn't exist in current project

### 2. SIGNALS: Drift Detection Events

**Signal catalog** from `signals.md`:

| Signal | Detection Method | Cost | Weight Range |
|--------|-----------------|------|--------------|
| `bead_closed` | `bd list --status=closed` vs. last scan | Free | 1-3 |
| `bead_created` | `bd list --status=open` vs. last scan | Free | 1-2 |
| `version_bump` | plugin.json version vs. doc header | Free | 2-3 |
| `component_count_changed` | glob count vs. doc claims | Free | 2-3 |
| `file_renamed` | `git diff --name-status` since doc mtime | Free | 2-3 |
| `file_deleted` | `git diff --name-status` since doc mtime | Free | 2-3 |
| `file_created` | `git diff --name-status` since doc mtime | Free | 1-2 |
| `commits_since_update` | `git rev-list --count` since doc mtime | Free | 1 |
| `brainstorm_created` | `find docs/brainstorms/ -newer $DOC` | Free | 1 |
| `companion_extracted` | plugin cache search for new companions | Free | 2-3 |
| `research_completed` | new flux-drive summaries since doc mtime | Free | 1-2 |
| `roadmap_bead_coverage` | `scripts/audit-roadmap-beads.sh --json` | Free | 2-3 |

**Two signal categories:**

- **Deterministic** — produce **Certain** confidence when they fire (doc is objectively wrong)
  - `version_bump` (version mismatch)
  - `component_count_changed` (count mismatch)

- **Probabilistic** — contribute to weighted score but don't guarantee drift
  - All others (beads closed might be relevant, might not)

### 3. DETECTION PHASE: Signal Evaluation

**From phases/detect.md:**

For each watchable, evaluate its configured signals:

#### Bead lifecycle signals (snapshot delta):

**bead_closed & bead_created:**
- Compare current `bd list --status=closed` count against baseline in `.interwatch/last-scan.json`
- Only the *change* since last scan triggers drift (not total count)
- First run: fallback to capped total count (conservative)

#### Version signal (deterministic):

**version_bump:**
```bash
plugin_version=$(python3 -c "import json; print(json.load(open('.claude-plugin/plugin.json'))['version'])" 2>/dev/null || echo "unknown")
doc_version=$(head -10 "$DOC_PATH" 2>/dev/null | grep -oP 'Version:\s*\K[\d.]+' || echo "unknown")
if [ "$plugin_version" != "$doc_version" ]; then echo "DRIFT"; fi
```

#### Component count signal (deterministic):

**component_count_changed:**
```bash
actual_skills=$(ls skills/*/SKILL.md 2>/dev/null | wc -l | tr -d ' ')
actual_commands=$(ls commands/*.md 2>/dev/null | wc -l | tr -d ' ')
# Compare against counts parsed from doc
```

#### File lifecycle signals (git-based):

**file_renamed / file_deleted / file_created:**
```bash
doc_mtime=$(stat -c %Y "$DOC_PATH" 2>/dev/null || echo 0)
doc_commit=$(git log -1 --format=%H --until="@$doc_mtime" 2>/dev/null || echo "HEAD~20")
git diff --name-status "$doc_commit"..HEAD -- skills/ commands/ agents/ 2>/dev/null
```

#### Commit count signal:

**commits_since_update:**
```bash
git rev-list --count HEAD --since="@$doc_mtime" 2>/dev/null || echo 0
```

#### Brainstorm signal:

**brainstorm_created:**
```bash
find docs/brainstorms/ -name "*.md" -newer "$DOC_PATH" 2>/dev/null | wc -l | tr -d ' '
```

#### Companion extraction signal:

**companion_extracted:**
Check plugin cache for companion plugins not mentioned in the doc.

**Output from detection phase:**

```
watchable: roadmap
path: docs/roadmap.md
signals:
  bead_closed: 3 (weight 2, score 6)
  version_bump: 0 (weight 3, score 0)
  brainstorm_created: 1 (weight 1, score 1)
total_score: 7
```

### 4. ASSESSMENT PHASE: Confidence Scoring

**From phases/assess.md:**

#### Drift score computation:

```
drift_score = sum(signal_weight * signal_count for each signal)
```

Additionally check **staleness**: days since doc mtime vs. watchable's `staleness_days` threshold.

#### Confidence tiers:

| Score | Staleness | Confidence | Color |
|-------|-----------|------------|-------|
| 0 | < threshold | **Green** — current | Green |
| 1-2 | < threshold | **Low** — minor drift | Blue |
| 3-5 | any | **Medium** — moderate drift | Yellow |
| 6+ | any | **High** — significant drift | Orange |
| any | > threshold | **High** — stale | Orange |
| deterministic signal | any | **Certain** — version/count mismatch | Red |

**Deterministic signals (Certain confidence):**
- `version_bump` mismatch detected
- `component_count_changed` mismatch detected

These are factual contradictions — doc is objectively wrong.

**Example assessment output:**
```
watchable: roadmap
drift_score: 7
staleness_days: 3
staleness_threshold: 7
confidence: High
recommendation: Auto-refresh with brief note
```

### 5. REFRESH PHASE: Generator Dispatch

**From phases/refresh.md:**

#### Action matrix by confidence:

| Confidence | Action |
|------------|--------|
| **Certain** | Auto-refresh silently. Apply result. Record in history. |
| **High** | Auto-refresh. Tell user: "Refreshed [doc] — [reason]." |
| **Medium** | Show drift summary. AskUserQuestion: "Drift detected. Refresh now?" |
| **Low** | Report only: "[doc] has minor drift. No action needed." |
| **Green** | Skip — no drift detected. |

#### Generator invocation:

Each watchable has a `generator` field specifying the plugin to invoke:

- `interpath:artifact-gen` — product artifacts (roadmap, PRD, vision, changelog, status)
- `interdoc:interdoc` — code documentation (AGENTS.md, CLAUDE.md)

Invoked via Skill tool:
```
Skill(skill: "[generator]", args: "[generator_args]")
```

Example for roadmap:
```
Skill(skill: "interpath:artifact-gen", args: "Generate a roadmap artifact")
```

#### Diff review before applying:

1. Read current doc
2. Generate new version
3. Compare for significant changes
4. If trivial changes (whitespace, dates only): apply silently even for Medium confidence
5. If substantial changes: follow confidence-based action matrix

#### State management:

After invoking a generator, always record the refresh to prevent false positives on next scan:

```bash
python3 scripts/interwatch-scan.py --record-refresh <watchable-name>
```

This resets bead count baselines for the refreshed doc so next scan sees zero delta.

### 6. HELPER LIBRARY: hooks/lib-watch.sh

**What it is:** Bash utility library (sourced, not executed) providing signal detection primitives for interwatch skills.

**Key functions:**

```bash
# File timestamp utilities
_watch_file_mtime <path>           # Returns file mtime as epoch seconds (or 0)
_watch_file_date <path>            # Converts mtime to YYYY-MM-DD (or "unknown")
_watch_staleness_days <path>       # Computes age in days from now (or 999)

# Version detection
_watch_doc_version <path>          # Parses "Version: X.Y.Z" from first 10 lines
_watch_plugin_version              # Reads .claude-plugin/plugin.json version

# Git history
_watch_commits_since <epoch>       # Returns commit count on HEAD after timestamp
_watch_file_changes <doc_path>     # Last commit at/before doc mtime, diffs skills/commands/agents/hooks vs HEAD

# Project state
_watch_newer_brainstorms <doc_path> # Counts docs/brainstorms/*.md newer than the doc
_watch_roadmap_bead_coverage [roadmap_path] # Runs scripts/audit-roadmap-beads.sh --json

# Key design:
# - Minimal side effects
# - Resilient fallbacks (return 0, "unknown", 999 on failure)
# - Filesystem timestamps + git history + beads coverage as observability primitives
```

### 7. SKILLS & COMMANDS

#### `/interwatch:doc-watch` — Orchestrator skill

Orchestrates drift detection workflow:

1. Load watchables from `config/watchables.yaml`
2. For each watchable: evaluate signals (phase/detect.md)
3. Compute confidence tier (phase/assess.md)
4. Take action based on confidence (phase/refresh.md)

Supports three modes (set by invoking command):
- **scan** — detect + assess only (no refresh)
- **status** — show current drift scores from last scan
- **refresh** — force refresh of specific watchable regardless of score

#### Commands in commands/:

**watch.md** — Run drift scan
- Load watchables
- Evaluate signals for each
- Display results as table with confidence tiers
- For Medium/High/Certain: suggest or auto-invoke generator

**status.md** — Show current drift scores
- Display last scan results without re-scanning
- Show which docs need attention

**refresh.md** — Force refresh specific doc
- Accepts doc name argument
- Bypasses detection and assessment
- Directly invokes generator
- Updates state

### 8. Key Design Decisions (Do Not Re-Ask)

1. **Namespace:** `interwatch:` (companion to Clavain)
2. **Watchables registry:** Declarative `config/watchables.yaml` (not code-based)
3. **Confidence tiers:** Certain (auto-fix) → High (auto-fix+note) → Medium (suggest) → Low (report)
4. **State tracking:** Per-project in `.interwatch/` (gitignored)
   - `drift.json` — current drift scores per watchable
   - `history.json` — refresh history (when, what, confidence)
   - `last-scan.json` — snapshot for change detection
5. **Generator-agnostic:** Calls interpath for product docs, interdoc for code docs
6. **No hooks:** Drift detection is on-demand, not event-driven (unlike interlearn's SessionEnd hook)

---

## PART 3: Integration Points with Synthesis Pipeline

### How interlearn Feeds the Synthesis Pipeline

1. **Discovery:** `/interlearn:index` builds `docs/solutions/index.json` at monorepo root
   - Maps module → array of solution documents
   - Enables synthesis pipeline to know what institutional knowledge exists
   - Session-end hook keeps index warm (background rebuild)

2. **Search:** Synthesis pipeline can query `index.json` to find prior solutions relevant to current problem
   - Structured search: title, tags, problem_type, module, path
   - Full-text fallback if structured search yields < 5 results

3. **Audit:** `/interlearn:audit` checks coverage of closed beads against solution docs
   - Identifies knowledge gaps (closed work without documentation)
   - Informs whether to surface a "undocumented lessons" warning before synthesis begins

### How interwatch Feeds the Synthesis Pipeline

1. **Freshness detection:** Before synthesis begins, synthesis pipeline should check:
   ```
   /interwatch:watch
   ```
   - Evaluates all watched docs (roadmap, PRD, AGENTS.md, etc.)
   - Returns confidence tier for each
   - Medium/High/Certain confidence means doc is stale before synthesis starts

2. **Selective regeneration:** If interwatch reports High/Certain drift on a watched doc:
   - Synthesis pipeline should invoke the appropriate generator first
   - Example: If AGENTS.md has Certain drift (file_deleted), run `interdoc:interdoc` first
   - Ensures synthesis works from current docs, not stale ones

3. **Baselines for signal detection:** interwatch's `.interwatch/last-scan.json` tracks:
   - Bead count baselines (to detect deltas, not total counts)
   - Allows synthesis to understand "what changed since last refresh"

### Data Flow Summary

```
Synthesis Pipeline
├─ Start session
├─ Query: /interlearn:index (warm cache)
│         docs/solutions/index.json available?
├─ Query: /interlearn:search <problem> (find prior work)
│         Returns up to 10 relevant solution docs
├─ Query: /interwatch:watch (check staleness)
│         Which product docs are stale?
├─ If High/Certain drift on AGENTS.md:
│   └─ Invoke interdoc:interdoc (regenerate first)
├─ If High/Certain drift on roadmap/PRD:
│   └─ Invoke interpath:artifact-gen (regenerate first)
└─ Proceed with synthesis using fresh docs + indexed solutions
```

---

## PART 4: State & Persistence

### interlearn State

- **Location:** `docs/solutions/` (monorepo root)
- **Files:**
  - `INDEX.md` — human-readable markdown table
  - `index.json` — machine-readable JSON keyed by path
- **Persistence:** Writes on-demand (skill) and session-end (hook), no auto-commit
- **Lifecycle:** Index files are checked into git (developer commits manually)

### interwatch State

- **Location:** `.interwatch/` (per-project, gitignored)
- **Files:**
  - `drift.json` — current drift scores per watchable
  - `history.json` — refresh history (when, what, confidence)
  - `last-scan.json` — bead count baselines + doc mtimes for delta detection
- **Persistence:** Written by `--save-state` (on scan) and `--record-refresh <name>` (after refresh)
- **Lifecycle:** Per-project state, not committed to git

---

## PART 5: Error Handling & Resilience

### interlearn

- **Fail-open hook:** Session teardown never blocked by indexing errors
- **Schema tolerance:** Missing or inconsistent frontmatter fields don't break the index
- **Module identity fallback:** Defaults to `interverse` if module can't be derived from path
- **Missing metadata fallback:** Title → first heading → filename; date → multiple keys tried
- **Graceful degradation:** If index doesn't exist, `/interlearn:search` runs the indexer first

### interwatch

- **Signal evaluation resilience:** Each signal has fallback values
  - `bd` unavailable: fallback to 0 count
  - `git` unavailable: fallback to HEAD~20 or no-diff
  - File mtime unavailable: fallback to epoch 0
  - Plugin version unavailable: fallback to "unknown"
- **Deterministic signal gates:** Only fire if both sides of comparison are available
- **State corruption recovery:** Next scan treats missing baselines as "first run" (conservative estimates)

---

## PART 6: Integration with Other Plugins

### interpath (Product artifact generator)

- **Called by:** interwatch when watching roadmap/PRD/vision
- **Generator reference:** `interpath:artifact-gen`
- **Args:** `{ type: roadmap }`, `{ type: prd }`, etc.
- **Data flow:** interwatch detects drift → calls interpath → interpath regenerates artifact

### interdoc (Code documentation generator)

- **Called by:** interwatch when watching AGENTS.md
- **Generator reference:** `interdoc:interdoc`
- **Data flow:** interwatch detects drift → calls interdoc → interdoc regenerates code docs

### interflux (Synthesis orchestrator)

- **Uses interlearn for:** Discovery of solution docs across monorepo
- **Uses interwatch for:** Freshness checking before synthesis begins
- **Workflow:** interflux queries both to understand current state before synthesis

---

## PART 7: Critical Patterns & Conventions

### interlearn

1. **Module identity from path, not frontmatter** — ensures consistent grouping
2. **No auto-commit** — manual commit gives developer control over what's committed
3. **Session-end indexing** — keeps index warm without explicit invocation
4. **Schema tolerance** — heterogeneous frontmatter doesn't break the system

### interwatch

1. **Snapshot delta for bead signals** — only detects *change* since last scan, not total state
2. **State reset after refresh** — `--record-refresh` prevents false positives on next scan
3. **Deterministic vs. probabilistic signals** — version/count are Certain; beads/commits are suggestive
4. **Staleness as override** — doc can be Green on signals but High on staleness
5. **Generator-agnostic** — interwatch doesn't care how doc is regenerated, just that it is

---

## PART 8: For the Synthesis Pipeline

### What the synthesis pipeline needs to know:

1. **Before synthesis starts:**
   - Call `/interlearn:index` or check if `docs/solutions/index.json` exists (SessionEnd hook keeps it warm)
   - Call `/interwatch:watch` to see which product docs are stale

2. **During synthesis preparation:**
   - Query `index.json` to surface relevant prior solutions
   - Use interwatch confidence tiers to decide: should I regenerate AGENTS.md first?

3. **Tradeoff decisions:**
   - **Time cost:** interwatch scans are ~fast (git log, find, bd list) but not zero
   - **Accuracy:** Probabilistic signals (beads closed) are suggestions, not guarantees
   - **Staleness threshold:** Default is 7 days for roadmap, 14 for PRD/AGENTS, 30 for vision
   - **Can customize:** Project can override `watchables.yaml` in `.interwatch/watchables.yaml`

4. **Plugin interface:**
   - interlearn: `/interlearn:index`, `/interlearn:search`, `/interlearn:audit`
   - interwatch: `/interwatch:watch`, `/interwatch:status`, `/interwatch:refresh`
   - Both are skills, called via Skill tool, not commands

---

## Summary

**interlearn** is the **discovery layer** — it indexes what documentation exists across the monorepo and keeps that index warm via SessionEnd hook. The synthesis pipeline uses it to find prior solutions relevant to the current problem.

**interwatch** is the **freshness layer** — it detects drift in watched documents (roadmap, PRD, AGENTS.md, etc.) using signal-based scoring and dispatches to generators (interpath, interdoc) for regeneration. The synthesis pipeline uses it to ensure working from current docs before synthesis begins.

Together, these two plugins provide the necessary **context awareness** for the synthesis pipeline: *what exists* (interlearn) and *what's stale* (interwatch).
