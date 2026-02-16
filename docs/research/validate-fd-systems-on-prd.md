# Flux-Drive Systems Thinking Review: Interlens Flux Agents PRD

**Document:** `/root/projects/Interverse/docs/prds/2026-02-15-interlens-flux-agents.md`
**Reviewer:** fd-systems (Systems Thinking Lens Agent)
**Date:** 2026-02-15
**Mode:** Codebase-aware (Interverse monorepo context)

## Summary

This PRD proposes adding 5 cognitive lens agents to the interflux review pipeline, delivered in phases. The document shows strong systems awareness in its phased structure and risk mitigation, but exhibits several blind spots around feedback loops, temporal dynamics, and emergent behavior at scale. The most critical gap is the absence of any analysis of how lens agents will **interact with each other and with technical agents** — treating agent composition as simple aggregation rather than a complex adaptive system.

## Findings

### P1 | FD-SYS-001 | "Features → F1b: Create Remaining 4 Agents" | Agent Interaction Feedback Loops Entirely Missing

The PRD specifies 5 lens agents covering overlapping cognitive domains (systems/decisions/people/resilience/perception) but provides **zero analysis of inter-agent feedback loops**. Line 68 states "No lens overlap between agents (each lens appears in exactly one agent's key list)" — this prevents literal lens duplication but ignores that **cognitive frames are not orthogonal**.

**Systems Thinking + Causal Graph lenses reveal:** A finding from `fd-systems` about "feedback loops" in a PRD will prime `fd-decisions` to flag decision quality issues in those same loops, which will then cause `fd-people` to identify power dynamics in the decision structure, creating a **reinforcing feedback loop** where agents amplify each other's pattern-matching in certain sections while leaving other sections under-reviewed. The synthesis deduplication logic (F4, line 96) only addresses identical lens findings — it cannot detect when 3 agents flag the same underlying issue through different cognitive frames.

**Missing:** Behavior-over-time analysis of multi-agent review convergence. What happens at T=0 (first review), T=10 (agents calibrated on same corpus), T=100 (agents have reviewed each other's outputs via flux-drive-on-flux-drive)? Does the system converge to a stable analytical stance or exhibit preferential attachment to certain frames?

**Recommendation:** Add F4b (Phase 1) acceptance criterion: "Synthesis detects and flags **causal clustering** — when 3+ findings from different agents reference the same document section, synthesis must explicitly test whether they are independent concerns or different projections of the same root issue."

---

### P1 | FD-SYS-002 | "Risks → Actionability risk" | Cobra Effect Trap in Success Metrics

Lines 21-22 define the Phase 0 success gate as "At least 2/3 test runs produce findings the author says they'd act on." This metric creates a **perverse incentive structure** that will bias agent development toward findings that are **immediately legible and confirmatory** rather than revealing true blind spots.

**Cobra Effect + Over-Adaptation lenses reveal:** Authors preferentially "act on" findings that align with existing mental models (confirmation bias) or are easy to implement (availability bias). An fd-systems agent that produces 5 findings — 3 obvious ones the author already half-knew + 2 genuinely novel frame-shifts — will pass the gate because 3/5 > 2/3. Over time, agent prompt refinement will **optimize for obviousness**, not insight depth. This is a classic cobra effect: measuring "actionability" produces agents that tell people what they want to hear.

**Missing:** Counterfactual reasoning. The PRD doesn't specify how to distinguish "I'd act on this because it caught a real blind spot" from "I'd act on this because it's low-hanging fruit."

**Recommendation:** Replace binary "act on it" gate with a structured rubric: (1) Did this finding reveal something you **hadn't considered**? (2) Would ignoring this finding create **second-order consequences**? (3) Does this finding require **changing your mental model** vs. just tweaking implementation? Require 2+ "changed mental model" findings per test, not just 2+ "I'd act on it."

---

### P2 | FD-SYS-003 | "Phase 0 → F2: Triage Pre-filter" | Hysteresis in Agent Activation Rules

Lines 73-76 define pre-filter rules that exclude lens agents from code reviews but include them for `.md` and `.txt` files. This creates a **sharp boundary** that ignores **document-code hysteresis**: many system design decisions are encoded partially in prose (architecture docs, PRDs) and partially in code structure.

**Hysteresis + Pace Layers lenses reveal:** A PRD proposing a new feedback loop might pass through fd-systems review, but when the engineer implements it in code, fd-systems is excluded. If the implementation subtly violates the intended loop structure (e.g., delays that cause oscillation), **no agent will flag the divergence** because fd-systems doesn't see code and fd-correctness doesn't see the original intent. The system has hysteresis — the review outcome depends on **which artifact you review and in what order**.

**Missing:** Temporal composition rules. How should flux-drive handle a PR containing both a design doc (`.md`) and implementation (`.go`)? Does it route both to fd-systems and fd-architecture, or only the architecture agent?

**Recommendation:** Add a Phase 2 feature for **multi-artifact reviews**: when INPUT_TYPE=directory contains both prose and code, run lens agents on prose AND allow them to request "intent-implementation alignment check" — a lightweight scan where fd-systems gets to see the code structure (not line-by-line) and flag divergence from stated design.

---

### P2 | FD-SYS-004 | "Features → F3: Interlens MCP Wiring" | Bullwhip Effect in Lens Retrieval

Lines 85-89 describe conditional MCP integration: agents call `search_lenses` and `detect_thinking_gaps` if MCP is available, otherwise fall back to hardcoded lenses. This creates a **two-mode system** where review depth varies wildly based on environment state, amplifying small differences in setup.

**Bullwhip Effect lens reveals:** If MCP is down, an agent reviews a document with 12/288 lenses and produces 3 findings. The author assumes "cognitive review found 3 issues, document is pretty solid." Two weeks later, another agent reviews a related document **with MCP up**, uses 40 lenses, and produces 15 findings on the same conceptual domain. Author now questions whether the first review was thorough. This **erodes trust** in the lens agent system because outcomes vary by 5x based on infrastructure state, not document quality.

**Missing:** Fallback parity strategy. The PRD doesn't specify how to select the "hardcoded key lenses" (line 51 mentions 12 lenses but no selection criteria beyond "curated from Systems Dynamics + Emergence + Resilience frames"). Are these lenses sufficient for 80% coverage, or do they create systematic blind spots?

**Recommendation:** Add F3b acceptance criterion: "Conduct empirical lens coverage analysis — review 10 diverse Interverse documents with (1) full MCP, (2) hardcoded 12 lenses. Measure finding overlap. If overlap < 60%, expand hardcoded set or add a **review confidence score** to synthesis output indicating 'fallback mode, limited lens set.'"

---

### P2 | FD-SYS-005 | "Phased Delivery" | Pace Layer Mismatch Between Development and Learning

The PRD front-loads all structural decisions (5 agents, domain boundaries, severity mapping) in Phase 0-1, but defers all **behavioral tuning** to implicit future iteration. This creates a **pace layer mismatch**: infrastructure evolves fast (Phase 0 → 1 → 2), but agent prompt quality evolves through **slow empirical learning** (months of review corpus accumulation).

**Pace Layers + Behavior Over Time Graph lenses reveal:** At T=0 (Phase 0), the team commits to 5 specific domain boundaries (systems/decisions/people/resilience/perception). At T=3mo (Phase 1 deployed), agents have reviewed 50 documents and the team realizes that "resilience" and "systems" lenses have 40% thematic overlap, producing redundant findings. But the **agent structure is now ossified** — changing domain boundaries would break triage scoring, synthesis deduplication, and user mental models. The system becomes **locked in to a suboptimal partition** because structure was decided before behavior was observed.

**Missing:** Learning phase before scaling. The PRD jumps from 1 agent (F1) to 5 agents (F1b) with no intermediate observation period.

**Recommendation:** Revise phased delivery: Phase 0 keeps F1 (fd-systems only). Add Phase 0.5: "Deploy fd-systems for 20 reviews, analyze finding distribution and cross-domain spillover. Use this data to **re-derive** domain boundaries for the other 4 agents empirically, rather than using the current top-down frame consolidation."

---

### P3 | FD-SYS-006 | "Features → F4: Severity Guidance" | Missing Reflexive Loop (Agent-on-Agent Review)

Lines 95-98 specify that synthesis treats "cognitive P1/P2/P3 identically to technical P1/P2/P3" and deduplicates by lens name. This equality assumption **prevents meta-learning**: the system cannot distinguish between "lens agents are systematically over-flagging" and "this document has deep cognitive gaps."

**Compounding Loops + Causal Graph lenses reveal:** If lens agents systematically inflate severity (e.g., flagging P1 for every missing frame), their findings will **dominate synthesis** and drown out technical findings. Conversely, if lens agents are too conservative, cognitive gaps will be invisible. The PRD has no **reflexive feedback mechanism** for calibrating lens agent severity against technical agent severity or against each other.

**Missing:** The PRD doesn't mention flux-drive reviewing its own output (agent-on-agent review), which is the natural calibration mechanism for a multi-agent system.

**Opportunity:** Add a Phase 2 feature for **meta-review**: once per quarter, run fd-systems on a sample of its own prior reviews to check for "same lens applied to similar sections produces wildly different severities" (calibration drift). This closes the reflexive loop and enables **system-level learning**, not just agent-level learning.

---

### P3 | FD-SYS-007 | "Non-goals → Domain profile for interlens" | Schelling Trap in Cross-Domain Universality

Line 111 explicitly states lens agents are "cross-domain (apply to all document reviews)" and rejects domain-specific profiles. This universality assumption creates a **Schelling trap**: lens agents will converge toward **generic cognitive frameworks** that apply everywhere but provide shallow insight, rather than developing domain-adapted heuristics.

**Schelling Traps + Simple Rules lenses reveal:** An fd-systems agent reviewing a Go microservice PRD vs. a Bubble Tea TUI PRD will apply identical "feedback loops / emergence / causal graph" lenses. But **feedback loop patterns in distributed systems** (network partitions, eventual consistency, cascading failures) are structurally different from **feedback loop patterns in interactive UIs** (render-event-state loops, input lag, visual coherence). A universal agent will flag "consider feedback loops" in both — true but shallow. A domain-adapted agent would flag "in distributed systems, consider split-brain scenarios" vs. "in TUIs, consider render-input phase misalignment."

**Trade-off:** Domain adaptation improves insight depth but increases maintenance burden (5 agents × N domains = explosion). The PRD's universality choice is **defensible** for Phase 0-1, but the non-goal framing suggests this is permanent.

**Recommendation:** Soften the non-goal to "Domain profiles deferred to Phase 3+ pending empirical evidence of domain-specific lens patterns." Add a Phase 2 logging feature: agents tag each finding with the **document domain** (inferred from CLAUDE.md or file path). After 100 reviews, analyze whether certain lenses cluster in certain domains, creating an **empirical basis** for future domain specialization.

---

### P3 | FD-SYS-008 | "Risks → Demand risk" | Crumple Zone Missing

Lines 123-124 identify demand risk ("no validated user demand") and mitigate with Phase 0's success gate. However, the **crumple zone** — what happens if Phase 0 **barely passes** but Phase 1 **fails at scale** — is unspecified.

**Crumple Zones lens reveals:** Phase 0 tests on 3 documents with manual interpretation. Phase 1 deploys 5 agents into production flux-drive, where reviews are automated and synthesis is algorithmic. If lens agents produce **marginal value at small scale but negative value at large scale** (e.g., cognitive overload, alert fatigue, synthesis conflicts), the system has no intermediate safety layer. Users go from "interesting experiment" to "this is unusable" with no gradual degradation path.

**Missing:** Partial deployment strategy. The PRD assumes Phase 0 success → full Phase 1 deployment. No provision for "Phase 1 opt-in" or "Phase 1 limited domains."

**Recommendation:** Add a Phase 1.5 acceptance criterion: "Deploy lens agents to flux-drive but make them **opt-in via --enable-cognitive flag** for first 50 reviews. Monitor synthesis quality metrics (user-reported signal/noise ratio, finding actionability). Require >= 70% positive feedback before making cognitive agents default-enabled." This creates a crumple zone between experimental validation and full production.

---

## Cognitive Frame Coverage Assessment

| Frame Category | Coverage | Notes |
|----------------|----------|-------|
| **Systems Thinking** | ✅ Strong | Phased delivery, success gates, risk mitigation show causal reasoning |
| **Feedback Loops** | ❌ Blind Spot | No analysis of agent-agent interaction loops (FD-SYS-001) |
| **Emergence** | ⚠️ Partial | Acknowledges cognitive overload (line 125) but doesn't model emergent multi-agent behavior |
| **Temporal Dynamics** | ⚠️ Partial | Phased structure shows T=0/T=1 thinking, but missing T=6mo/T=2yr behavioral projections (FD-SYS-005) |
| **Unintended Consequences** | ⚠️ Partial | Identifies some risks but misses cobra effects in success metrics (FD-SYS-002) |
| **Causal Reasoning** | ✅ Strong | Clear dependency chains, blocked-by relationships |
| **Hysteresis** | ❌ Missed | Document-code review boundary creates path-dependence (FD-SYS-003) |
| **Bullwhip Effect** | ❌ Missed | MCP availability variance amplifies review inconsistency (FD-SYS-004) |

## Strengths (What NOT to Change)

1. **Phased delivery with kill gate (Phase 0 → 1)** — excellent application of fail-fast principle
2. **Explicit non-goals** — prevents scope creep
3. **Dependency tracking** — clear prerequisite chains
4. **Separation of concerns** — lens agents in interflux, knowledge base in interlens (good architectural partitioning)

## Meta-Observation

This PRD is **self-exemplifying**: it proposes creating fd-systems to review documents for systems thinking gaps, yet **exhibits systems thinking gaps itself**. This is not a criticism — it's evidence that cognitive blind spots are real and that lens agents could provide value. The irony is that fd-systems reviewing its own PRD produces 8 actionable findings, validating the core premise.

## Recommendations Summary

| ID | Phase | Action |
|----|-------|--------|
| FD-SYS-001 | Phase 1 (F4b) | Add causal clustering detection to synthesis |
| FD-SYS-002 | Phase 0 | Replace binary success gate with structured insight rubric |
| FD-SYS-003 | Phase 2 | Add multi-artifact review mode for prose+code alignment |
| FD-SYS-004 | Phase 1 (F3b) | Empirical lens coverage analysis, add review confidence score |
| FD-SYS-005 | Phase 0.5 (new) | Add 20-review learning phase before scaling to 5 agents |
| FD-SYS-006 | Phase 2 | Add meta-review (agent-on-agent) calibration mechanism |
| FD-SYS-007 | Phase 2 | Log finding-domain pairs to build empirical basis for specialization |
| FD-SYS-008 | Phase 1.5 (new) | Add opt-in deployment crumple zone before default-enabling |

## Conclusion

The PRD demonstrates strong **structural systems thinking** (phasing, gates, dependencies) but weak **behavioral systems thinking** (feedback loops, emergence, temporal dynamics). This is a common pattern: teams apply systems thinking to **project structure** but not to **system behavior over time**. The most critical insight is FD-SYS-001 — the absence of any agent interaction model. A multi-agent cognitive review system is a **complex adaptive system**, not a set of independent modules. Treating it as the latter will produce emergent behaviors (finding amplification, frame lock-in, severity inflation) that are not addressed in the current design.

**Overall assessment:** The PRD is **sufficient to build Phase 0** (single agent, hardcoded lenses), but **insufficient to safely scale to Phase 1** (5 agents, MCP integration) without addressing inter-agent feedback dynamics. Recommend proceeding with Phase 0 as written, then **mandatory** systems analysis before Phase 1 greenlight.
