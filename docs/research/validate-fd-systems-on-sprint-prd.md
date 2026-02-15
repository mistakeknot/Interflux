# Flux-Drive Systems Thinking Review: Sprint Resilience PRD

**Document:** `/root/projects/Interverse/docs/prds/2026-02-15-sprint-resilience.md`
**Reviewer:** Flux-drive Systems Thinking Agent
**Date:** 2026-02-15
**Bead:** iv-ty1f

## Review Summary

This PRD proposes a sprint workflow redesign around persistent bead state, auto-advance, and tiered brainstorming. The document shows solid correctness thinking (atomic init, locked updates, session claims) but has several systems-level blind spots around feedback loops, emergent behavior at scale, and temporal dynamics.

**Overall Assessment:** Strong implementation design, moderate systems awareness. Key gaps in feedback loop mapping, behavior-over-time analysis, and second-order effects from automation.

---

## Findings

### P1 | Lines 94-106, 111-121 | Missing Reinforcing Loop: Auto-Advance → Brittle Sprint Patterns

**Systems Thinking, Compounding Loops, Hormesis**

The auto-advance engine (F2) removes user confirmation at every phase transition, reducing friction. But there's no analysis of the reinforcing loop this creates: **auto-advance → reduced user attention to phase boundaries → degraded mental models of sprint structure → worse pause trigger design → more reliance on auto-advance**. Over time, users may lose fluency in manual sprint navigation, making the system more brittle when pause triggers fire or when bugs require manual intervention. The PRD assumes pause triggers (design ambiguity, gate failures) are comprehensive, but doesn't model what happens when the classifier misses an edge case and the sprint auto-advances into a broken state. Without controlled exposure to phase transitions (hormesis), users won't develop the tacit knowledge needed to recover from automation failures. **Question:** What feedback mechanisms preserve user mental models of sprint phases when 95% of transitions are automated? How do we ensure pause triggers evolve with actual failure modes rather than predicted ones?

---

### P1 | Lines 111-121 | Emergent Behavior: Complexity Classifier → Feature Shaping Pressure

**Simple Rules, Emergence, Schelling Traps**

The tiered brainstorming feature (F3) uses description-based signals (length, ambiguity terms, pattern references) to classify complexity. This creates a **simple rule with emergent consequences**: users will learn (consciously or not) that shorter, more definitive descriptions trigger less interactive brainstorming. The PRD doesn't consider the **Schelling trap**: users converge on terse descriptions to minimize interaction, even when features genuinely need exploration. This isn't user laziness—it's rational adaptation to incentives. Over 6-12 months, this could **systematically bias the feature pipeline** toward overconfident planning (underdiscussed complexity) or artificially verbose descriptions (gaming the classifier). The override (`bd set-state complexity=complex`) exists but requires meta-awareness that the default was wrong. **Question:** What signals can detect when users are gaming the classifier? How does the system learn which descriptions SHOULD have been classified differently based on downstream outcomes (e.g., plan rewrites, extended execution time)?

---

### P2 | Lines 50-63, 172-183 | Pace Layer Mismatch: Fast State Updates, Slow Mental Synchronization

**Pace Layers, BOTG (Behavior Over Time Graph)**

The sprint bead serves as a **fast-changing state layer** (phase transitions, artifact updates, session claims), but the PRD doesn't model the **slower human synchronization layer**. At T=0 (first sprint), users actively track state. At T=3 months (20+ sprints), the statusline becomes wallpaper—users stop reading it. At T=6 months, a session crash mid-sprint means the resume hint (`Active sprint: <id> (phase: X, next: Y)`) appears in a new session, but the user's mental context is still 2 phases behind. The correctness safeguards (atomic init, locked updates) ensure bead state integrity, but don't address **human desync**. The PRD assumes statusline visibility solves this (F5), but doesn't model the **attention decay curve** or the **cognitive load of re-contextualizing** after interruptions. **Question:** What does sprint resumption look like at T=6 months when a user has 3 active sprints and hasn't touched any in 2 weeks? How does the system scaffold re-entry beyond a one-line hint?

---

### P2 | Lines 94-106 | Second-Order Effect: Pause Triggers → Gate Pressure & Definition Drift

**Causal Graph, Bullwhip Effect**

The auto-advance engine pauses for "P0/P1 gate failure, test failure, quality gate findings" (line 99). This creates a **causal feedback loop**: if gates become the primary pause trigger, then **gate strictness becomes the de facto UX tuning knob**. Development teams may pressure for looser gates to reduce interruptions, or conversely, gate definitions may drift to match "things we actually want to pause for" rather than "correctness invariants." This is a **bullwhip effect**: small changes in pause frequency amplify into large shifts in gate policy. The PRD doesn't acknowledge that gates now serve dual purposes (correctness enforcement AND flow control), which may create **conflicting selection pressures**. A gate that's "too sensitive" for auto-advance but "necessary for correctness" has no good resolution. **Question:** How do we disentangle gate correctness from flow control? Should there be a separate class of "review triggers" distinct from quality gates?

---

### P2 | Lines 6, 16-26 | Missing Failure Mode: Session Claim Deadlock & Recovery Blindness

**Systems Thinking, Hysteresis**

The session claim mechanism (60-min TTL, `active_session` field) prevents concurrent resume, but the PRD doesn't model **what happens when the claiming session dies without releasing**. The 60-min TTL is a backstop, but creates **hysteresis**: if a user's session crashes at minute 5, they're locked out for 55 minutes unless they manually intervene (unclear how—`bd set-state active_session=null`?). The PRD says "ephemeral phase state" is the problem being solved (line 6), but the session claim **reintroduces ephemeral state** in a different form. The correctness section (lines 172-183) mentions "write-then-verify" but doesn't address the UX of a stuck claim. At T=6 months with 10 users, this will manifest as "I can't resume my sprint and I don't know why." **Question:** What's the self-serve recovery path when a session claim is stuck? Should the statusline show "claimed by session X (started 58 min ago)" so users know to wait vs. force-release? Can `sprint_claim()` detect stale sessions and auto-reclaim?

---

### P3 | Lines 111-121 | Cognitive Trap: Complexity Override as a Confession of Ignorance

**Schelling Traps, Over-Adaptation**

The override mechanism (`bd set-state complexity=complex`) allows users to correct misclassifications, but psychologically, using it is **a confession that your description was unclear**. Users may avoid the override to save face, especially in shared/visible contexts (if sprint beads are browsable by teammates). This is a **Schelling trap**: the path of least social friction is to accept the wrong classification and work around it (e.g., force a collaborative dialogue by asking vague questions mid-brainstorm). Over time, this trains the system on bad data: the classifier never learns from its mistakes because corrections are socially costly. **Question:** Can the system infer misclassification from downstream signals (e.g., brainstorm duration, number of rewrites) and retrain? Should the override be framed as "request deeper brainstorming" rather than "correct the AI's mistake"?

---

### P3 | Lines 28-45, 50-63 | Crumple Zone Risk: Sprint Bead as Overloaded Abstraction

**Crumple Zones, Simple Rules**

The sprint bead now serves **four roles**: (1) epic parent for feature beads, (2) phase state tracker, (3) artifact manifest, (4) session lock. This is efficient (one bead, no phase children), but creates a **crumple zone risk**: when something goes wrong, it's hard to isolate which layer failed. If `sprint_artifacts` JSON is malformed, does that break phase transitions? If `active_session` is stale, does that block artifact updates? The PRD's correctness safeguards (atomic init, locked updates) treat the bead as a monolith, but don't model **partial failure modes**. A simpler rule might be: "beads are immutable; edits create new versions with backlinks." The current design optimizes for **update convenience** at the cost of **failure locality**. **Question:** What happens when one state field is corrupted—does the entire sprint become unrecoverable? Should there be a `sprint-repair` command that rewrites bead state from artifact headers + git history?

---

### P3 | Lines 16-26, 165-170 | Non-Goal Deserves Scrutiny: "No Multi-User Sprints"

**Emergence, BOTG**

The non-goals section explicitly excludes "concurrent users on the same sprint bead" (line 169). This is fine for T=0, but at T=1 year, when Clavain is used by small teams, the **emergent behavior** will be users creating identical sprints in separate sessions and manually merging results. The PRD doesn't acknowledge this as a **predictable workaround**, which means it will happen in an unstructured way (copy-paste between terminals, ad-hoc Slack syncs). The session claim mechanism already exists (lines 24, 60), so the foundation for turn-taking is there. **Question:** What does "multi-user sprint" usage look like in the wild today (if any)? If it's already happening informally, is the non-goal creating more friction than it prevents? Should the design at least acknowledge the emergence risk and provide migration hooks for future multi-user support?

---

## Systems Lenses Applied

1. **Systems Thinking** — Feedback loops, causal chains, interconnections (P1 auto-advance loop, P2 gate pressure)
2. **Compounding Loops** — Reinforcing/balancing dynamics (P1 automation brittleness loop)
3. **BOTG (Behavior Over Time Graph)** — T=0, T=6mo, T=2yr projections (P2 pace layer mismatch, P3 multi-user emergence)
4. **Simple Rules** — Emergent behavior from simple classifiers (P1 complexity classifier gaming)
5. **Bullwhip Effect** — Amplification of small changes (P2 gate definition drift)
6. **Hysteresis** — State persistence after cause removed (P2 session claim deadlock)
7. **Causal Graph** — Second/third-order effects (P2 pause triggers → gate policy shifts)
8. **Schelling Traps** — Convergence on suboptimal equilibria (P1 terse descriptions, P3 override avoidance)
9. **Crumple Zones** — Failure absorption boundaries (P3 sprint bead overload)
10. **Pace Layers** — Fast/slow change rates (P2 state updates vs. mental sync)
11. **Hormesis** — Controlled stress builds resilience (P1 loss of manual sprint fluency)

---

## Recommendations

1. **Add a feedback loop audit section** to the PRD: map intended loops (auto-advance → speed, complexity classifier → effort), predict unintended loops (automation → mental model decay, classifier → description gaming), and specify mitigations.

2. **Model behavior over time** for key features: What does auto-advance look like at sprint #50? What does complexity classification accuracy look like after 6 months of user adaptation? Add telemetry hooks to track these.

3. **Design for graceful degradation**: If session claim is stuck, statusline shows "Sprint locked by crashed session—run `/sprint-recover <id>` to reclaim." If complexity classifier misfires, let users inline-escalate ("This looks simple but I need help") without leaving the flow.

4. **Separate concerns in the sprint bead**: Consider artifact manifest as a separate linked bead, or use bead tags/labels for phase state rather than overloading the body. Makes failure modes more debuggable.

5. **Acknowledge emergence risks in non-goals**: "Multi-user sprints are explicitly out of scope for Phase 1-3, but we expect informal workarounds (shared screen, copy-paste) to emerge. Telemetry will track how often sprints are cloned/duplicated as a leading indicator for future multi-user demand."

---

## Conclusion

This PRD has strong implementation rigor but would benefit from explicit systems thinking. The correctness safeguards handle state integrity well, but don't model human-system feedback loops, emergent user behavior, or long-term adaptation dynamics. Adding behavior-over-time projections, feedback loop maps, and mitigation strategies for the P1/P2 findings would significantly strengthen the design's resilience to second-order effects.
