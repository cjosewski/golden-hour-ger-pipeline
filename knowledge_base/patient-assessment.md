# Patient Assessment

> **Status**: Draft
> **Author**: game-designer
> **Last Updated**: 2026-07-15
> **Last Verified**: 2026-07-15
> **Implements Pillar**: Pillar 1 (Clinical truth under pressure), Pillar 2 (The face is a vital sign)

## Summary

Patient Assessment provides the **MARCH-ordered examine verbs** — check
breathing, check radial pulse/capillary refill, check mental status, check
for major hemorrhage, expose the chest — that read a casualty's ground-truth
physiology and facial state. This system does not decide a triage category;
it decides **what the trainee has learned**, and feeds that directly into
`triage-system.md`'s decision tree.

> **Quick reference** — Layer: `Core` · Priority: `MVP` · Key deps: `Casualty Model, VR Interaction & Locomotion, Voice Command System`

## Overview

Assessment is the diagnostic half of the core loop — before the trainee can
sort or treat anyone, they have to find out what's actually wrong. This
system defines the vocabulary of clinical questions the trainee can ask a
casualty, by hand or by voice, and what they learn from each one.

Key facts driving this design:
- Assessment sequence follows **MARCH** (Massive hemorrhage → Airway → Respiration → Circulation → Head injury/Hypothermia) — the TECC/TCCC standard that supersedes ABC for penetrating trauma because exsanguination kills faster than airway compromise.
- Examine verb set: check breathing, check radial pulse / capillary refill, check mental status ("squeeze my hand" / follows commands), check for major hemorrhage, expose the chest for respiratory-distress signs.
- Casualty facial expression (pain, consciousness, respiratory distress, pallor) is itself a required, readable-at-distance assessment input per Pillar 2 — not flavor animation.
- Findings from this system are the direct input to `triage-system.md`'s SALT decision tree; this system owns "what did the trainee learn," triage owns "what does that mean."

## Player Fantasy

Your hands and eyes are trained instruments — a raised wrist, a glance at the
chest, a question asked out loud tells you what's actually wrong, before you
decide what to do about it.

## Detailed Design

### Core Rules

[To be designed] — the MARCH-order examine verb list above is the seed; exact interaction mechanics per verb remain open

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
| Casualty Model | This depends on Casualty Model | Examine verbs read ground-truth physiology and mobility state |
| VR Interaction & Locomotion | This depends on VR Interaction & Locomotion | Examine verbs are hand interactions |
| Voice Command System | This depends on Voice Command System | Examine verbs are also voice-triggerable |
| Triage System | Triage System depends on this | SALT decision tree consumes this system's assessment findings as direct input |

## Tuning Knobs

| Parameter | Current Value | Safe Range | Effect of Increase | Effect of Decrease |
|-----------|--------------|------------|-------------------|-------------------|
| [To be designed] | | | | |

## Visual/Audio Requirements

| Event | Visual Feedback | Audio Feedback | Priority |
|-------|----------------|---------------|----------|
| Examine verb performed (e.g., pulse check) | [To be designed] | Casualty vocal response appropriate to physiology state | Medium |

## Game Feel

### Feel Reference

[To be designed]

### Input Responsiveness

| Action | Max Input-to-Response Latency (ms) | Frame Budget (at 90fps PC VR — POC target) | Notes |
|--------|-----------------------------------|------------------------|-------|
| Examine-verb hand interaction | [To be designed] | [To be designed] | A 72fps Quest budget is deferred to the Alpha milestone, feasibility-gated |

### Animation Feel Targets

[To be designed]

### Impact Moments

[To be designed]

### Weight and Responsiveness Profile

[To be designed]

### Feel Acceptance Criteria

- [ ] [To be designed]

## UI Requirements

| Information | Display Location | Update Frequency | Condition |
|-------------|-----------------|-----------------|-----------|
| Assessment findings collected so far for the current casualty | World-space panel near the casualty | On each examine-verb use | Only while actively assessing |

## Cross-References

| This Document References | Target GDD | Specific Element Referenced | Nature |
|--------------------------|-----------|----------------------------|--------|
| "Examine verbs read ground-truth physiology" | `design/gdd/casualty-model.md` | Ground-truth physiology and mobility state | Data dependency |
| "Findings feed the SALT decision tree" | `design/gdd/triage-system.md` | Individual assessment decision-tree inputs | Data dependency |
| "Facial expression is a required assessment input" | `design/gdd/casualty-facial-animation.md` | Pain/consciousness/respiratory-distress readable state | Data dependency |

## Acceptance Criteria

- [ ] GIVEN a trainee performs a pulse check on a casualty, WHEN the check resolves, THEN the trainee-visible result matches the casualty's current ground-truth physiology state
- [ ] GIVEN a trainee performs an examine verb via voice, WHEN via hand-interaction on the same casualty, THEN both produce identical findings
- [ ] Performance: System update completes within [X]ms — [To be designed]
- [ ] No hardcoded values in implementation — examine-verb thresholds are data-driven

## Open Questions

| Question | Owner | Deadline | Resolution |
|----------|-------|----------|-----------|
| Exact interaction mechanic per examine verb (grab-and-hold vs. gesture vs. gaze+confirm) | game-designer | Before Detailed Design is finalized | [To be designed] |
| Which UE input/interaction framework implements the examine-verb set? | ue-blueprint-specialist | Phase 3 (Technical Setup) | → ADR (Phase 3) — not a GDD-time decision |

## Build Agents

Engineering pair builds the two proof-of-concept assessment verbs during W3, with verifier evidence confirming both verbs return live physiology values at the W5 gate. Mapped in the compiled GDD's build-time agent plan (§12.1).
