# Scoring & Debrief

> **Status**: Draft
> **Author**: game-designer
> **Last Updated**: 2026-07-15
> **Last Verified**: 2026-07-15
> **Implements Pillar**: Pillar 4 (Safe to fail, hard to master)

## Summary

Everything the trainee does is logged: triage accuracy vs. ground truth,
time-to-first-tourniquet, per-casualty outcomes, and doctrine violations.
The POC delivers a **score + summary screen** at scenario end. A full
**timeline-replay after-action review (AAR)** is specified in this document
as the target capability but is explicitly **scheduled for a later
milestone**, not built in the POC. Scoring's MVP dependency set is Triage
System and Treatment & Interventions only — Incident Command & Comms
(METHANE scoring) is Vertical Slice tier, not MVP, so it is **not** an MVP
hard dependency; the POC's score + summary screen functions completely
without it (see `systems-index.md` Dependency Map). Per product-owner
direction (2026-07-16), the trainee's locomotion mode (controller-smooth,
teleport, room-scale, or Omni treadmill) is also logged per session, since
scores are not blindly comparable across modes — see Tuning Knobs and Open
Questions.

> **Quick reference** — Layer: `Feature/Presentation` · Priority: `MVP` · Key deps: `Triage System, Treatment & Interventions`

## Overview

Debrief is where the actual learning happens in serious-game training —
more than the moment-to-moment play itself. This system exists to turn every
logged action into an honest, specific, non-punishing account of what the
trainee did well and what they'd do differently.

Key facts driving this design:
- Logged metrics: triage accuracy with under-triage (<5%) and over-triage (<50%) rates against ACS Committee on Trauma acceptable benchmarks, time-per-patient, time-to-first-tourniquet (≤120s pass window), LSI correctness/sequence, and doctrine violations (hot-zone entry, warm-zone over-treatment, CPR-on-traumatic-arrest-in-MCI). METHANE report completeness is an **additional** metric, logged only if Incident Command & Comms (Vertical Slice tier) is built — it is not part of the POC/MVP metric set.
- The POC delivers a score + summary screen at scenario end — not a full replay.
- Full timeline-replay AAR (any-participant-POV, the reference bar set by DHS S&T EDGE) is specified here as a target capability, explicitly scheduled for a later milestone per `game-concept.md` Scope Tiers.
- Debrief framing should follow a structured model (e.g., PEARLS: reactions → description → analysis → summary) rather than a raw stat dump, to protect Pillar 4.
- Per product-owner direction (2026-07-16): locomotion mode (see `vr-interaction-locomotion.md`'s four first-class modes) is recorded per session. Omni-mode sessions are vigorous physical exertion, so late-scenario fatigue is accounted for when interpreting a score, and a trainee's first-ever Omni treadmill session is not scored at all (acclimation, not assessment).

## Player Fantasy

Seeing your performance laid out honestly — what you got right, what you'd
do differently — is the moment the training actually sticks.

## Detailed Design

### Core Rules

[To be designed] — the logged-metrics list above, now including per-session
locomotion mode (per product-owner direction (2026-07-16)), is the seed

### States and Transitions

[To be designed]

### Interactions with Other Systems

[To be designed]

## Formulas

[To be designed]

## Edge Cases

| Scenario | Expected Behavior | Rationale |
|----------|------------------|-----------|
| [To be designed] | | |

## Dependencies

| System | Direction | Nature of Dependency |
|--------|-----------|---------------------|
| Triage System | This depends on Triage System | Under-triage/over-triage rates and time-per-patient are computed from triage call data |
| Treatment & Interventions | This depends on Treatment & Interventions | Intervention correctness/sequence and time-to-first-tourniquet are computed from intervention data |
| Incident Command & Comms | Optional dependency (Vertical Slice only, not an MVP hard dependency) | If Incident Command & Comms is later built, METHANE completeness becomes an additional scored metric; the POC's MVP score + summary screen functions completely without it |
| VR Interaction & Locomotion | This depends on VR Interaction & Locomotion | Per-session locomotion mode is logged and used to contextualize scores (per product-owner direction (2026-07-16)) |
| Duty-of-Care Flow | Duty-of-Care Flow depends on this | The debrief step sequences into decompression |

## Tuning Knobs

| Parameter | Current Value | Safe Range | Effect of Increase | Effect of Decrease |
|-----------|--------------|------------|-------------------|-------------------|
| Under-triage acceptable rate | <5% | [To be designed] | Stricter pass bar | More forgiving pass bar |
| Over-triage acceptable rate | <50% | [To be designed] | Stricter pass bar | More forgiving pass bar |
| Tourniquet pass window | ≤120s | 60–180s | More forgiving | Stricter |
| First-ever Omni treadmill session scored? | No — acclimation only | [To be designed] | | |

## Visual/Audio Requirements

| Event | Visual Feedback | Audio Feedback | Priority |
|-------|----------------|---------------|----------|
| Scenario ends, summary screen presents | World-space summary panel with per-casualty outcomes and benchmark comparisons | [To be designed] | High |

## Game Feel

### Feel Reference

Should feel like a supportive after-action debrief with a training officer —
specific, honest, non-judgmental. NOT like a report-card grade reveal or a
"you failed" screen.

### Input Responsiveness

[To be designed]

### Animation Feel Targets

[To be designed]

### Impact Moments

[To be designed]

### Weight and Responsiveness Profile

[To be designed]

### Feel Acceptance Criteria

- [ ] No playtester describes the summary screen as punishing or shaming
- [ ] [To be designed]

## UI Requirements

| Information | Display Location | Update Frequency | Condition |
|-------------|-----------------|-----------------|-----------|
| Score/summary screen (triage accuracy, time-to-first-tourniquet, per-casualty outcomes, doctrine violations) | World-space panel presented at scenario end | Once, at scenario end | After scenario completes or is stopped |

## Cross-References

| This Document References | Target GDD | Specific Element Referenced | Nature |
|--------------------------|-----------|----------------------------|--------|
| "Under/over-triage rates computed from triage call data" | `design/gdd/triage-system.md` | Triage call + ground-truth-at-tagging-time data | Data dependency |
| "Time-to-first-tourniquet computed from intervention data" | `design/gdd/treatment-interventions.md` | Intervention timestamp data | Data dependency |
| "METHANE completeness computed from report data (optional, Vertical Slice only)" | `design/gdd/incident-command-comms.md` | METHANE element checklist data | Data dependency |
| "Debrief sequences into decompression" | `design/gdd/duty-of-care-flow.md` | Session flow ordering | State trigger |
| "Locomotion mode is recorded per session" | `design/gdd/vr-interaction-locomotion.md` | Movement-intent mode selection | Data dependency |
| "Casualty expression-decision trace feeds the later-milestone after-action review" | `design/gdd/casualty-facial-animation.md` | Expression-decision traceability (Determinism rule); POC logs the trace, full AAR is later-milestone | Data dependency |

## Acceptance Criteria

- [ ] GIVEN a completed scenario, WHEN the summary screen presents, THEN it shows triage accuracy, time-to-first-tourniquet, per-casualty outcomes, and any doctrine violations
- [ ] GIVEN the trainee stops the scenario early via the duty-of-care exit, WHEN they do so, THEN a partial summary reflecting completed actions is still presented (no unhandled state)
- [ ] Performance: Summary computation completes within [X]ms of scenario end — [To be designed]
- [ ] No hardcoded values in implementation — benchmark thresholds are data-driven per the Tuning Knobs table

## Open Questions

| Question | Owner | Deadline | Resolution |
|----------|-------|----------|-----------|
| Exact debrief framing/structure (PEARLS vs. another model) | game-designer | Before Detailed Design is finalized | [To be designed] |
| Scope and technical approach for the later-milestone timeline-replay AAR | game-designer / unreal-specialist | Post-POC, before Vertical Slice | → ADR (Phase 3), not a POC-time decision |
| Data storage/session-log persistence approach | ue-blueprint-specialist | Phase 3 (Technical Setup) | → ADR (Phase 3) — not a GDD-time decision |
| How should late-scenario fatigue in Omni-mode sessions be weighted or annotated when interpreting a score, and what non-comparability caveat is shown alongside cross-mode scores? | game-designer | Before Detailed Design is finalized | [To be designed] |

## Build Agents

- Engineering pair builds the session-event log and end card (W3/W5).
- Verifier evidence confirms the end card shows real logged numbers.

Mapped in the compiled GDD's build-time agent plan (§12.1).
