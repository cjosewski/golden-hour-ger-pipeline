# Treatment & Interventions

> **Status**: Draft
> **Author**: game-designer
> **Last Updated**: 2026-07-15
> **Last Verified**: 2026-07-15
> **Implements Pillar**: Pillar 1 (Clinical truth under pressure), Pillar 3 (Doctrine, not heroics)

## Summary

The trainee's warm-zone life-threat intervention verb set — **tourniquet
application, wound packing + pressure dressing, chest seal, needle
decompression, NPA/OPA airway adjuncts, supplemental O2, recovery position,
and drag/carry extraction** — each mapped 1:1 to a Pulse Physiology Engine
action call. Full workups, spinal immobilization rituals, and IV fluids are
explicitly out of scope for this system (they belong to a later cold-zone
phase, not modeled in the POC).

> **Quick reference** — Layer: `Core` · Priority: `MVP` · Key deps: `Casualty Model, Patient Assessment, VR Interaction & Locomotion, Pulse Physiology Integration`

## Overview

This is where the trainee's hands do the actual life-saving work — but only
the work that real warm-zone doctrine permits. Every intervention here is
scoped to life threats, ordered by MARCH, and produces a real physiological
response because it drives an actual Pulse action, not a scripted animation.

Key facts driving this design:
- **Verb set (warm-zone, life-threats-only scope)**: tourniquet application; wound packing (hemostatic or plain gauze) plus pressure dressing; chest seal (vented preferred) for open/sucking chest wounds; needle decompression (2nd intercostal space) for tension pneumothorax; NPA/OPA airway adjuncts; supplemental oxygen; recovery position; drag/carry extraction to the Casualty Collection Point.
- Full head-to-toe workups, spinal immobilization rituals, and IV fluid resuscitation wait for the cold zone / evacuation phase — performing them in the warm zone is a scored doctrine violation, not a blocked action (see `triage-system.md` Edge Cases for the pattern).
- Every intervention maps 1:1 to a Pulse Physiology Engine action call (tourniquet → hemorrhage-cessation action, needle decompression → pneumothorax-relief action, etc.) — this system defines the trainee-facing interaction, `pulse-physiology-integration.md` defines the simulated effect.
- Interactions are **procedural-sequence based** (grab, place, gesture, confirm) and scored on decision correctness and sequence, **not fine motor technique** — VR without haptics does not reliably teach physical skill, which is exactly why this scope boundary is stated explicitly (see Anti-Pillar 2 in `game-concept.md`).

## Player Fantasy

Your hands do exactly what your training taught them, in the right order,
under pressure — and the patient responds because the physiology underneath
is real, not because a scripted animation played.

## Detailed Design

### Core Rules

- Verb set (see Summary/Overview above) is exhaustive for the POC's warm-zone scope; no additional interventions are modeled.
- Each intervention verb has a defined MARCH-order relevance: tourniquet application and wound packing (hemostatic or plain gauze) + pressure dressing are **M — Massive hemorrhage** tier; chest seal and needle decompression are **R — Respiration** tier (they treat the two respiratory life threats — open/sucking chest wound and tension pneumothorax — not hemorrhage); NPA/OPA airway adjuncts are **A — Airway** tier; recovery position is **A — Airway** tier for unconscious casualties. These four MARCH tiers are kept distinct — M and R are never blurred under one combined label.
- [To be designed] — exact interaction mechanic per verb, success/failure conditions, and how partial/incorrect application (e.g., a tourniquet applied too loosely) is represented, if at all, given the explicit no-fine-motor-scoring boundary.

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
| Casualty Model | This depends on Casualty Model | Interventions apply against the casualty's injury loadout and physiology component |
| Patient Assessment | This depends on Patient Assessment | Assessment findings determine which interventions are contextually relevant |
| VR Interaction & Locomotion | This depends on VR Interaction & Locomotion | Intervention verbs are hand interactions |
| Pulse Physiology Integration | This depends on Pulse Physiology Integration | Every intervention maps 1:1 to a Pulse action call |
| Triage System | Triage System depends on this | Hemorrhage-controlled and other SALT-question inputs are set by successful interventions here |
| Scoring & Debrief | Scoring & Debrief depends on this | Intervention correctness/sequence and time-to-first-tourniquet are scored from this system's output |

## Tuning Knobs

| Parameter | Current Value | Safe Range | Effect of Increase | Effect of Decrease |
|-----------|--------------|------------|-------------------|-------------------|
| Tourniquet application pass window | ≤120s | 60–180s | More forgiving | Stricter, closer to expert benchmarks |
| [To be designed] — per-intervention success windows for wound packing, chest seal, needle decompression, NPA/OPA | | | | |

## Visual/Audio Requirements

| Event | Visual Feedback | Audio Feedback | Priority |
|-------|----------------|---------------|----------|
| Intervention applied successfully | Visible attachment/change on casualty model (tourniquet visible on limb, dressing visible on wound, etc.) | Physiology-appropriate response (e.g., bleeding audibly/visually slows) | High |
| Intervention attempted outside warm-zone scope | [To be designed] | [To be designed] | Medium |

## Game Feel

### Feel Reference

Should feel like Stop-the-Bleed practical training — deliberate, procedural
hand motions with a clear sense of "did I do the steps," not a twitch-timing
minigame. NOT gamified with combo meters or score popups mid-action.

### Input Responsiveness

| Action | Max Input-to-Response Latency (ms) | Frame Budget (at 90fps PC VR — POC target) | Notes |
|--------|-----------------------------------|------------------------|-------|
| Tourniquet grab/place/tighten sequence | [To be designed] | [To be designed] | A 72fps Quest budget is deferred to the Alpha milestone, feasibility-gated |
| Wound packing / dressing application | [To be designed] | [To be designed] | A 72fps Quest budget is deferred to the Alpha milestone, feasibility-gated |

### Animation Feel Targets

[To be designed]

### Impact Moments

| Impact Type | Duration (ms) | Effect Description | Configurable? |
|-------------|--------------|-------------------|---------------|
| Successful intervention confirmation | [To be designed] | Haptic pulse distinct from a failed/incomplete attempt | Yes |

### Weight and Responsiveness Profile

- **Weight**: Deliberate and procedural — each step should feel like it matters, without simulating fine muscle tension (explicitly out of scope).
- **Player control**: High — trainee can pause or redo a step.
- **Snap quality**: [To be designed]
- **Acceleration model**: N/A
- **Failure texture**: An incomplete or wrong-order intervention should read as a clear, fair sequencing mistake, correctable in the moment where possible, and always addressed in debrief.

### Feel Acceptance Criteria

- [ ] Playtesters can complete the tourniquet sequence without needing a tutorial prompt open after their first attempt
- [ ] [To be designed]

## UI Requirements

| Information | Display Location | Update Frequency | Condition |
|-------------|-----------------|-----------------|-----------|
| Intervention step progress (e.g., "tourniquet: place → tighten → secure") | World-space, attached to the casualty or the trainee's hand | On each step | Only during an active intervention |

## Cross-References

| This Document References | Target GDD | Specific Element Referenced | Nature |
|--------------------------|-----------|----------------------------|--------|
| "Interventions apply against injury loadout and physiology" | `design/gdd/casualty-model.md` | Injury loadout, physiology component | Data dependency |
| "Findings determine contextually relevant interventions" | `design/gdd/patient-assessment.md` | Assessment findings | Data dependency |
| "Every intervention maps to a Pulse action call" | `design/gdd/pulse-physiology-integration.md` | Intervention → action mapping | Rule dependency |
| "Hemorrhage-controlled feeds SALT question (d)" | `design/gdd/triage-system.md` | Ground-truth category derivation input | Data dependency |
| "Warm-zone scope enforcement" | `design/gdd/scene-zone-director.md` | Zone-gated permitted actions | Rule dependency |
| "Treatment interactions must respect the treatment-lock and raised interaction volumes" | `design/gdd/vr-interaction-locomotion.md` | Treatment-lock / kneel-and-treat interaction-volume rules | Rule dependency |
| "Intervention events feed the casualty's acute-pain model" | `design/gdd/casualty-facial-animation.md` | Stage 3 acute-pain input (intervention events) | Data dependency |

## Acceptance Criteria

- [ ] GIVEN a casualty has an active uncontrolled hemorrhage, WHEN the trainee successfully applies a tourniquet, THEN the casualty's physiology reflects hemorrhage cessation and `hemorrhage_controlled` becomes true for the SALT decision tree
- [ ] GIVEN a tension pneumothorax casualty, WHEN the trainee successfully performs needle decompression, THEN respiratory distress physiology improves within a defined time window — [To be designed]
- [ ] GIVEN the trainee is in the warm zone, WHEN they attempt an intervention outside warm-zone scope, THEN the action is logged as a scored doctrine violation
- [ ] Performance: System update completes within [X]ms — [To be designed]
- [ ] No hardcoded values in implementation — pass windows and success conditions are data-driven per the Tuning Knobs table

## Open Questions

| Question | Owner | Deadline | Resolution |
|----------|-------|----------|-----------|
| Exact interaction mechanic per intervention verb | game-designer | Before Detailed Design is finalized | [To be designed] |
| Whether partial/incorrect application is represented at all, given the explicit no-fine-motor-scoring boundary | game-designer | Before Detailed Design is finalized | [To be designed] |
| Does the current Pulse Blueprint API surface every needed action (wound packing vs. pressure-dressing differentiation, partial tourniquet effectiveness)? | unreal-specialist | Week-1 technical spike | [To be designed] |

## Build Agents

The Engineering pair builds the tourniquet verb (W3). Verifier evidence
confirms the treatment response is a real physiology action call, not a
scripted number change. Mapped in the compiled GDD's build-time agent
plan (§12.1).
